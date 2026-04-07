import streamlit as st
import pandas as pd
import altair as alt

def run():
    try:
        with open("sales_trend.css", "r", encoding="utf-8") as f:
            st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)
    except FileNotFoundError:
        pass

    st.title("💳 채권(미수금) 현황 분석기")
    st.markdown("이카운트에서 다운로드한 **[월별채권증감내역]** 엑셀 또는 CSV 파일을 아래에 올려주세요.")

    # 1. 파일 업로드 존 
    uploaded_file = st.file_uploader("엑셀/CSV 파일 업로드", type=['csv', 'xlsx', 'xls'])

    if uploaded_file is None:
        st.info("👆 분석할 파일을 업로드해 주세요.")
        return

    try:
        # 2. 파일 로딩 및 인코딩 자동 처리
        if uploaded_file.name.endswith('.csv'):
            try:
                df_raw = pd.read_csv(uploaded_file, encoding='utf-8')
            except UnicodeDecodeError:
                uploaded_file.seek(0)
                df_raw = pd.read_csv(uploaded_file, encoding='cp949') 
        else:
            df_raw = pd.read_excel(uploaded_file)

        # 3. 이카운트 양식 자동 인식 및 정제 마법
        header_idx = df_raw[df_raw.apply(lambda r: r.astype(str).str.contains('거래처명').any(), axis=1)].index
        if len(header_idx) > 0:
            df_raw.columns = df_raw.iloc[header_idx[0]]
            df = df_raw.iloc[header_idx[0]+1:].reset_index(drop=True)
        else:
            st.error("올바른 이카운트 양식이 아닙니다. '거래처명' 열이 포함된 파일을 올려주세요.")
            return

        if '거래처명' not in df.columns or '구분' not in df.columns:
            st.error("데이터에 '거래처명' 또는 '구분' 열이 없습니다.")
            return

        # 🚀 [추가] 담당자 컬럼 찾기 (이름이 '담당자' 또는 '담당자명'일 경우 대비)
        manager_col = next((c for c in df.columns if '담당자' in str(c)), None)
        
        # 빈 셀 채우기 (엑셀 병합 해제 효과)
        df['거래처명'] = df['거래처명'].ffill()
        if manager_col:
            df[manager_col] = df[manager_col].ffill() # 담당자도 아래로 꽉꽉 채워줍니다.
            
        df = df.dropna(subset=['구분']) 

        month_cols = [c for c in df.columns if '20' in str(c) and ('/' in str(c) or '-' in str(c))]
        if not month_cols:
            st.error("월별 데이터 열을 찾을 수 없습니다.")
            return

        # 🚀 담당자 유무에 따라 데이터를 묶는 기준(id_vars)을 다르게 설정
        id_vars_list = ['거래처명', '구분']
        if manager_col:
            id_vars_list.insert(1, manager_col)

        df_melt = df.melt(id_vars=id_vars_list, value_vars=month_cols, var_name='기준월', value_name='금액')
        df_melt['금액'] = pd.to_numeric(df_melt['금액'].astype(str).str.replace(',', ''), errors='coerce').fillna(0)
        
        pivot_idx = ['거래처명', '기준월']
        if manager_col:
            pivot_idx.insert(1, manager_col)
            
        df_pivot = df_melt.pivot_table(index=pivot_idx, columns='구분', values='금액', aggfunc='sum').reset_index()
        
        for col in ['잔액', '매출', '수금', '미회수액']:
            if col not in df_pivot.columns:
                df_pivot[col] = 0

        # 🚀 [추가] DSO (매출채권회수일수) 계산
        def calc_dso(row):
            if row['매출'] > 0:
                return int((row['잔액'] / row['매출']) * 30)
            elif row['잔액'] > 0:
                return 9999 # 당월 매출이 없는데 잔액이 있는 악성/장기 채권
            return 0
            
        df_pivot['DSO'] = df_pivot.apply(calc_dso, axis=1)


        # 4. 사이드바 필터 UI
        st.sidebar.markdown("### 🔍 분석 조건")
        
        month_list = sorted(list(df_pivot['기준월'].unique()), reverse=True)
        selected_month = st.sidebar.selectbox("1. 기준월 선택", month_list)
        
        # 🚀 [추가] 담당자 필터 (담당자 열이 있을 때만 화면에 표시)
        selected_manager = "전체보기"
        if manager_col:
            manager_list = ["전체보기"] + sorted(list(df_pivot[manager_col].dropna().unique()))
            selected_manager = st.sidebar.selectbox("2. 담당자 선택", manager_list)
        
        trader_list = sorted(list(df_pivot['거래처명'].unique()))
        selected_traders = st.sidebar.multiselect("3. 거래처 검색 (선택)", options=trader_list, default=[], placeholder="전체 보기")

        st.sidebar.markdown("---")
        st.sidebar.markdown("### ⚠️ 위험 채권 필터")

        # 🚀 [추가] DSO 및 잔액 필터
        hide_zero = st.sidebar.checkbox("✅ 잔액 0원 거래처 숨기기", value=True)
        
        # DSO 슬라이더 (0일 ~ 120일 이상)
        min_dso = st.sidebar.slider(
            "최소 회수일수(DSO) 기준", 
            min_value=0, max_value=120, value=0, step=15,
            help="설정한 일수보다 회수가 오래 걸리는(돈이 묶인) 거래처만 필터링합니다. (0 = 전체 보기)"
        )


        # 5. 필터 적용 로직
        display_df = df_pivot[df_pivot['기준월'] == selected_month].copy()
        
        if manager_col and selected_manager != "전체보기":
            display_df = display_df[display_df[manager_col] == selected_manager]
            
        if selected_traders:
            display_df = display_df[display_df['거래처명'].isin(selected_traders)]
            
        if hide_zero:
            display_df = display_df[display_df['잔액'] > 0]
            
        if min_dso > 0:
            # 설정한 DSO 이상이거나, 장기미수(9999)인 거래처만 표시
            display_df = display_df[display_df['DSO'] >= min_dso]


        # 6. 상단 KPI 카드
        total_balance = display_df['잔액'].sum()
        total_sales = display_df['매출'].sum()
        total_collection = display_df['수금'].sum()
        debtor_count = len(display_df[display_df['잔액'] > 0])
        
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("🚨 잔액 보유 거래처", f"{debtor_count} 곳")
        c2.metric("💰 총 미수금 잔액", f"{int(total_balance / 10000):,}만 원", f"실제: {int(total_balance):,} 원", delta_color="off")
        c3.metric("📈 당월 매출", f"{int(total_sales / 10000):,}만 원")
        c4.metric("📥 당월 수금", f"{int(total_collection / 10000):,}만 원")
        st.markdown("---")

        if display_df.empty:
            st.success("🎉 선택한 조건에 해당하는 위험/미수금 거래처가 없습니다!")
            return

        # 7. 미수금 상위 거래처 차트
        st.subheader(f"📊 [{selected_month}] 미수금 잔액 상위 거래처 (TOP 10)")
        
        top10_df = display_df.sort_values('잔액', ascending=False).head(10)
        y_ax = alt.Axis(labelLimit=300, labelFontSize=14, title='', labelPadding=10)
        
        rank_chart = alt.Chart(top10_df).mark_bar(size=25, cornerRadius=5, color="#E74C3C", opacity=0.9).encode(
            x=alt.X('잔액:Q', title='미수금 잔액 (원)'), 
            y=alt.Y('거래처명:N', sort='-x', axis=y_ax),
            tooltip=['거래처명', alt.Tooltip('잔액', format=','), alt.Tooltip('매출', format=','), alt.Tooltip('수금', format=',')]
        )
        
        text_label = rank_chart.mark_text(align='left', dx=5, fontSize=13, fontWeight='bold', color='#555').encode(
            text=alt.Text('잔액:Q', format=',')
        )
        st.altair_chart((rank_chart + text_label).properties(height=350), use_container_width=True)

        # 8. 상세 내역 표 
        st.markdown("---")
        st.subheader("📋 채권 상세 내역표")
        
        # 보여줄 컬럼 동적 구성 (담당자 유무에 따라)
        cols_to_show = ['거래처명']
        if manager_col: cols_to_show.append(manager_col)
        
        if '이월잔액' in display_df.columns: cols_to_show.append('이월잔액')
        cols_to_show.extend(['매출', '수금', '잔액', 'DSO'])
        
        show_df = display_df[cols_to_show].copy()
        
        # DSO 포맷팅 (9999 -> 장기미수 경고 문구로 변경)
        show_df['회수일수(DSO)'] = show_df['DSO'].apply(lambda x: "🚨장기미수(당월매출無)" if x == 9999 else f"{x} 일")
        show_df = show_df.drop(columns=['DSO'])

        # 숫자 포맷팅 (콤마)
        for col in show_df.columns:
            if col not in ['거래처명', manager_col, '회수일수(DSO)']:
                show_df[col] = show_df[col].apply(lambda x: f"{int(x):,}")

        # 잔액 기준으로 내림차순 정렬
        show_df = show_df.sort_values(by='잔액', ascending=False, key=lambda x: x.str.replace(',', '').astype(float))
        
        st.dataframe(show_df, use_container_width=True, hide_index=True)

    except Exception as e:
        st.error(f"파일을 분석하는 중 오류가 발생했습니다: {e}")
