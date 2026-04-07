import streamlit as st
import pandas as pd
import altair as alt

def run():
    # 담당자 코드 -> 이름 매핑 (하드코딩)
    MANAGER_MAP = {
        "001": "001:이계성",
        "002": "002:이계흥",
        "004": "004:황일용",
        "00026": "00026:신의명",
        "007": "007:정상영",
        "009": "009:이경옥"
    }
    # 지정하신 순서대로 리스트 생성
    MANAGER_ORDER = ["001:이계성", "002:이계흥", "004:황일용", "00026:신의명", "007:정상영", "009:이경옥"]

    try:
        with open("sales_trend.css", "r", encoding="utf-8") as f:
            st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)
    except FileNotFoundError:
        pass

    st.title("💳 채권(미수금) 현황 분석기")
    st.markdown("이카운트에서 다운로드한 **[월별채권증감내역]** 파일을 올려주세요.")

    uploaded_file = st.file_uploader("엑셀/CSV 파일 업로드", type=['csv', 'xlsx', 'xls'])

    if uploaded_file is None:
        st.info("👆 분석할 파일을 업로드해 주세요.")
        return

    try:
        # 1. 데이터 로딩
        if uploaded_file.name.endswith('.csv'):
            try:
                df_raw = pd.read_csv(uploaded_file, encoding='utf-8')
            except UnicodeDecodeError:
                uploaded_file.seek(0)
                df_raw = pd.read_csv(uploaded_file, encoding='cp949') 
        else:
            df_raw = pd.read_excel(uploaded_file)

        # 2. 이카운트 양식 정제
        header_idx = df_raw[df_raw.apply(lambda r: r.astype(str).str.contains('거래처명').any(), axis=1)].index
        if len(header_idx) > 0:
            df_raw.columns = df_raw.iloc[header_idx[0]]
            df = df_raw.iloc[header_idx[0]+1:].reset_index(drop=True)
        else:
            st.error("올바른 이카운트 양식이 아닙니다.")
            return

        manager_col = next((c for c in df.columns if '담당자' in str(c)), None)
        df['거래처명'] = df['거래처명'].ffill()
        
        if manager_col:
            df[manager_col] = df[manager_col].ffill().astype(str).str.strip()
            # 🚀 [매핑 적용] 담당자 코드를 "코드:이름" 형태로 변환
            df[manager_col] = df[manager_col].apply(lambda x: MANAGER_MAP.get(x, f"{x}:미등록"))
            
        df = df.dropna(subset=['구분']) 
        month_cols = [c for c in df.columns if '20' in str(c) and ('/' in str(c) or '-' in str(c))]

        id_vars_list = ['거래처명', '구분']
        if manager_col: id_vars_list.insert(1, manager_col)

        df_melt = df.melt(id_vars=id_vars_list, value_vars=month_cols, var_name='기준월', value_name='금액')
        df_melt['금액'] = pd.to_numeric(df_melt['금액'].astype(str).str.replace(',', ''), errors='coerce').fillna(0)
        
        pivot_idx = ['거래처명', '기준월']
        if manager_col: pivot_idx.insert(1, manager_col)
        df_pivot = df_melt.pivot_table(index=pivot_idx, columns='구분', values='금액', aggfunc='sum').reset_index()
        
        for col in ['잔액', '매출', '수금']:
            if col not in df_pivot.columns: df_pivot[col] = 0

        # DSO 계산 로직
        def calc_dso(row):
            if row['매출'] > 0: return int((row['잔액'] / row['매출']) * 30)
            elif row['잔액'] > 0: return 9999 
            return 0
        df_pivot['DSO'] = df_pivot.apply(calc_dso, axis=1)

        # 3. 사이드바 필터 (d1.png 역할)
        st.sidebar.markdown("### 🔍 분석 조건")
        month_list = sorted(list(df_pivot['기준월'].unique()), reverse=True)
        selected_month = st.sidebar.selectbox("1. 기준월 선택", month_list)
        
        # 🚀 [필터 순서 고정] 하드코딩한 순서대로 필터에 표시
        selected_manager = "전체보기"
        if manager_col:
            available_managers = [m for m in MANAGER_ORDER if m in df_pivot[manager_col].unique()]
            manager_options = ["전체보기"] + available_managers
            selected_manager = st.sidebar.selectbox("2. 담당자 선택", manager_options)
        
        st.sidebar.markdown("---")
        st.sidebar.markdown("### ⚠️ 위험 채권 필터")
        hide_zero = st.sidebar.checkbox("✅ 잔액 0원 거래처 숨기기", value=True)
        min_dso = st.sidebar.slider("최소 회수일수(DSO) 기준", 0, 120, 0, step=15)

        # 필터 적용
        display_df = df_pivot[df_pivot['기준월'] == selected_month].copy()
        if manager_col and selected_manager != "전체보기":
            display_df = display_df[display_df[manager_col] == selected_manager]
        if hide_zero:
            display_df = display_df[display_df['잔액'] > 0]
        if min_dso > 0:
            display_df = display_df[display_df['DSO'] >= min_dso]

        # 4. 상단 KPI 및 차트
        total_balance = display_df['잔액'].sum()
        total_sales = display_df['매출'].sum()
        c1, c2, c3 = st.columns(3)
        c1.metric("💰 총 미수금", f"{int(total_balance / 10000):,}만 원")
        c2.metric("📈 당월 매출", f"{int(total_sales / 10000):,}만 원")
        c3.metric("🚨 대상 업체수", f"{len(display_df)} 곳")
        
        st.markdown("---")
        
        # 5. 미수금 상위 차트
        top10 = display_df.sort_values('잔액', ascending=False).head(10)
        rank_chart = alt.Chart(top10).mark_bar(size=25, cornerRadius=5, color="#E74C3C").encode(
            x=alt.X('잔액:Q', title='미수금 (원)'),
            y=alt.Y('거래처명:N', sort='-x', axis=alt.Axis(labelLimit=300)),
            tooltip=['거래처명', alt.Tooltip('잔액', format=',')]
        )
        st.altair_chart(rank_chart, use_container_width=True)

        # 6. 상세 리포트 (d2.png 역할)
        st.subheader("📋 채권 상세 리포트")
        cols = ['거래처명']
        if manager_col: cols.append(manager_col)
        cols.extend(['매출', '수금', '잔액', 'DSO'])
        
        show_df = display_df[cols].copy()
        show_df['DSO'] = show_df['DSO'].apply(lambda x: "🚨장기(매출無)" if x == 9999 else f"{x}일")
        
        # 숫자 콤마 표시
        for c in ['매출', '수금', '잔액']:
            show_df[c] = show_df[c].apply(lambda x: f"{int(x):,}")
            
        st.dataframe(show_df.sort_values('잔액', ascending=False), use_container_width=True, hide_index=True)

    except Exception as e:
        st.error(f"오류: {e}")
