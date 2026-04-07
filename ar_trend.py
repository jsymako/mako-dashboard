import streamlit as st
import pandas as pd
import altair as alt
import io

def run():
    # CSS 스타일 적용 (기존 톤앤매너 유지)
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
                df_raw = pd.read_csv(uploaded_file, encoding='cp949') # 국내 엑셀 CSV 표준
        else:
            df_raw = pd.read_excel(uploaded_file)

        # 3. 이카운트 양식 자동 인식 및 정제 마법 🚀
        # '거래처명'이 있는 행을 자동으로 찾아서 진짜 헤더(제목)로 지정합니다.
        header_idx = df_raw[df_raw.apply(lambda r: r.astype(str).str.contains('거래처명').any(), axis=1)].index
        if len(header_idx) > 0:
            df_raw.columns = df_raw.iloc[header_idx[0]]
            df = df_raw.iloc[header_idx[0]+1:].reset_index(drop=True)
        else:
            st.error("올바른 이카운트 양식이 아닙니다. '거래처명' 열이 포함된 파일을 올려주세요.")
            return

        # 빈 거래처명 채우기 (아래로 끌어내리기 - 엑셀 병합 해제 효과)
        if '거래처명' not in df.columns or '구분' not in df.columns:
            st.error("데이터에 '거래처명' 또는 '구분' 열이 없습니다.")
            return
            
        df['거래처명'] = df['거래처명'].ffill()
        df = df.dropna(subset=['구분']) # 구분이 없는 빈 줄 제거

        # 날짜(월) 컬럼만 쏙 골라내기 (예: '2025/01', '2026/02' 등)
        month_cols = [c for c in df.columns if '20' in str(c) and ('/' in str(c) or '-' in str(c))]
        if not month_cols:
            st.error("월별 데이터 열을 찾을 수 없습니다.")
            return

        # 세로로 길게 풀었다가(Melt), 가로로 예쁘게 재조립(Pivot) 합니다.
        df_melt = df.melt(id_vars=['거래처명', '구분'], value_vars=month_cols, var_name='기준월', value_name='금액')
        df_melt['금액'] = pd.to_numeric(df_melt['금액'].astype(str).str.replace(',', ''), errors='coerce').fillna(0)
        
        # 거래처 + 기준월 별로 [매출, 수금, 잔액] 열 생성!
        df_pivot = df_melt.pivot_table(index=['거래처명', '기준월'], columns='구분', values='금액', aggfunc='sum').reset_index()
        
        # 필수 컬럼(잔액, 매출, 수금) 안전망
        for col in ['잔액', '매출', '수금', '미회수액']:
            if col not in df_pivot.columns:
                df_pivot[col] = 0

        # 4. 사이드바 필터 UI (기존 d1.png 다이얼로그 역할)
        st.sidebar.markdown("### 🔍 분석 조건")
        
        # 기준월 선택
        month_list = sorted(list(df_pivot['기준월'].unique()), reverse=True)
        selected_month = st.sidebar.selectbox("1. 기준월 선택", month_list)
        
        # 잔액 필터
        hide_zero = st.sidebar.checkbox("✅ 잔액 0원 거래처 숨기기", value=True)
        
        # 거래처 검색 필터
        trader_list = sorted(list(df_pivot['거래처명'].unique()))
        selected_traders = st.sidebar.multiselect("2. 특정 거래처 검색", options=trader_list, default=[], placeholder="전체 보기")

        st.sidebar.markdown("---")

        # 필터 적용
        display_df = df_pivot[df_pivot['기준월'] == selected_month].copy()
        
        if hide_zero:
            # 잔액이 0보다 큰(돈을 받아야 하는) 곳만 남김
            display_df = display_df[display_df['잔액'] > 0]
            
        if selected_traders:
            display_df = display_df[display_df['거래처명'].isin(selected_traders)]

        # 5. 상단 KPI 카드
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

        # 데이터가 없으면 종료
        if display_df.empty:
            st.success("🎉 선택한 조건에 해당하는 미수금 잔액이 없습니다!")
            return

        # 6. 미수금 상위 거래처 차트
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

        # 7. 상세 내역 표 (기존 d2.png 결과 화면 역할)
        st.markdown("---")
        st.subheader("📋 채권 상세 내역표")
        
        # 표에 보여줄 컬럼만 정리하고 보기 좋게 포맷팅
        show_df = display_df[['거래처명', '이월잔액', '매출', '수금', '기타할인등차액', '잔액']].copy() if '이월잔액' in display_df.columns else display_df[['거래처명', '매출', '수금', '잔액']].copy()
        
        # 숫자 포맷팅 (콤마)
        for col in show_df.columns:
            if col != '거래처명':
                show_df[col] = show_df[col].apply(lambda x: f"{int(x):,}")

        # 잔액 기준으로 정렬
        show_df = show_df.sort_values(by='잔액', ascending=False, key=lambda x: x.str.replace(',', '').astype(float))
        
        st.dataframe(show_df, use_container_width=True, hide_index=True)

    except Exception as e:
        st.error(f"파일을 분석하는 중 오류가 발생했습니다: {e}")
