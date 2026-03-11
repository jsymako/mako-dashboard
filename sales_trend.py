import streamlit as st
import pandas as pd
import datetime
from dateutil.relativedelta import relativedelta

def run(load_data_func):
    st.title("📈 판매 현황 및 트렌드 분석")
    st.markdown("매출액과 판매량을 브랜드 및 품목별로 심도 있게 분석합니다.")

    try:
        # 1. 데이터 로드 및 전처리
        df_sales = load_data_func("sales_record")
        df_item = load_data_func("ecount_item_data") 
        
        df_sales.columns = df_sales.columns.str.strip()
        
        if '일자' not in df_sales.columns:
            st.error("🚨 시트 첫 줄에 '일자' 열을 찾을 수 없습니다.")
            return

        if '공급가액' not in df_sales.columns:
            df_sales['공급가액'] = 0

        df_sales['일자'] = pd.to_datetime(df_sales['일자'], errors='coerce')
        df_sales['수량'] = df_sales['수량'].astype(str).str.replace(',', '')
        df_sales['수량'] = pd.to_numeric(df_sales['수량'], errors='coerce').fillna(0)
        df_sales['공급가액'] = df_sales['공급가액'].astype(str).str.replace(',', '')
        df_sales['공급가액'] = pd.to_numeric(df_sales['공급가액'], errors='coerce').fillna(0)
        
        df_sales = df_sales.dropna(subset=['일자'])
        df_sales = df_sales[df_sales['수량'] > 0] 

        if df_sales.empty:
            st.warning("표시할 판매 데이터가 없습니다.")
            return

        # 품목 정보(브랜드, 박스입수) 병합
        box_col_name = df_item.columns[3] 
        df_item_info = df_item[['품목코드', '브랜드', box_col_name]].copy()
        df_item_info.rename(columns={box_col_name: '박스입수'}, inplace=True)
        df_item_info['박스입수'] = pd.to_numeric(df_item_info['박스입수'], errors='coerce').fillna(1)
        
        df_sales = pd.merge(df_sales, df_item_info, on='품목코드', how='left')
        df_sales['브랜드'] = df_sales['브랜드'].fillna('기타')
        df_sales['박스입수'] = df_sales['박스입수'].fillna(1)
        df_sales['환산수량'] = df_sales['수량'] / df_sales['박스입수']

        def format_qty_display(qty, box_unit):
            if box_unit <= 1: 
                return f"{int(qty):,} 개" if qty == int(qty) else f"{qty:.1f} 개"
            boxes = qty / box_unit
            return f"{boxes:.1f} 박스" if boxes < 10 else f"{int(boxes):,} 박스"

        # 2. 사이드바: 기간 설정 (단축키 포함)
        today = datetime.date.today()
        
        if "trend_start_date" not in st.session_state:
            st.session_state.trend_start_date = today - relativedelta(months=3)
        if "trend_end_date" not in st.session_state:
            st.session_state.trend_end_date = today

        st.sidebar.markdown("### ⚡ 빠른 기간 선택")
        col1, col2 = st.sidebar.columns(2)
        
        if col1.button("이번 달"):
            st.session_state.trend_start_date = today.replace(day=1)
            st.session_state.trend_end_date = today
        if col2.button("지난 달"):
            first_day_this_month = today.replace(day=1)
            last_day_last_month = first_day_this_month - datetime.timedelta(days=1)
            st.session_state.trend_start_date = last_day_last_month.replace(day=1)
            st.session_state.trend_end_date = last_day_last_month
            
        col3, col4 = st.sidebar.columns([2, 1])
        with col3:
            quick_months = st.selectbox("과거 기간", [1, 2, 3, 6, 12, 24], index=1, format_func=lambda x: f"최근 {x}개월", label_visibility="collapsed")
        with col4:
            if st.button("적용"):
                st.session_state.trend_start_date = today - relativedelta(months=quick_months)
                st.session_state.trend_end_date = today

        st.sidebar.markdown("### 📅 상세 기간 설정")
        # YYYY-MM-DD 포맷 적용으로 숫자 달력 표시, 미래 날짜 제한 해제
        start_date = st.sidebar.date_input("시작일", key="trend_start_date", format="YYYY-MM-DD")
        end_date = st.sidebar.date_input("종료일", key="trend_end_date", format="YYYY-MM-DD")

        brand_list = ["전체보기"] + sorted(list(df_sales['브랜드'].unique()))
        selected_brand = st.sidebar.selectbox("🔍 브랜드 필터", brand_list)

        # 필터 적용
        mask = (df_sales['일자'].dt.date >= start_date) & (df_sales['일자'].dt.date <= end_date)
        filtered_df = df_sales.loc[mask].copy()
        
        if selected_brand != "전체보기":
            filtered_df = filtered_df[filtered_df['브랜드'] == selected_brand]

        if filtered_df.empty:
            st.warning("선택하신 조건에 맞는 판매 데이터가 없습니다.")
            return

        # 3. 화면 상단 KPI 요약
        total_amount = filtered_df['공급가액'].sum()
        total_days = (end_date - start_date).days + 1
        daily_avg_amount = total_amount / total_days if total_days > 0 else 0
        total_qty = filtered_df['수량'].sum()

        col1, col2, col3, col4 = st.columns(4)
        col1.metric(label="💰 총 판매액", value=f"{int(total_amount):,} 원")
        col2.metric(label="📅 분석 기간", value=f"{total_days} 일")
        col3.metric(label="💸 일평균 판매액", value=f"{int(daily_avg_amount):,} 원")
        col4.metric(label="📦 총 판매수량", value=f"{int(total_qty):,} 개")
        
        st.markdown("---")

        # 4. 차트: 일별 판매 추이
        st.subheader("📉 일별 판매 추이")
        tab1, tab2 = st.tabs(["💰 매출액 흐름보기", "📦 판매수량 흐름보기"])
        
        daily_trend = filtered_df.groupby('일자')[['공급가액', '수량']].sum().reset_index()
        daily_trend.set_index('일자', inplace=True)
        
        with tab1:
            st.line_chart(daily_trend['공급가액'], color="#2E86C1")
        with tab2:
            st.line_chart(daily_trend['수량'], color="#28B463")

        # 5. 차트: 베스트셀러 TOP 10
        st.subheader("🏆 베스트셀러 TOP 10")
        tab3, tab4 = st.tabs(["💰 매출액 기준 TOP 10", "📦 환산수량(박스/개) 기준 TOP 10"])
        
        with tab3:
            top_amount = filtered_df.groupby('품목명')['공급가액'].sum().sort_values(ascending=False).head(10)
            st.bar_chart(top_amount, color="#E74C3C")
            
        with tab4:
            top_qty = filtered_df.groupby('품목명')['환산수량'].sum().sort_values(ascending=False).head(10)
            st.bar_chart(top_qty, color="#F39C12")

        # 6. 표: 데이터 상세
        with st.expander("🔍 선택된 기간의 상세 판매 기록 보기"):
            display_df = filtered_df[['일자', '브랜드', '품목명', '수량', '박스입수', '공급가액']].copy()
            display_df['일자'] = display_df['일자'].dt.strftime('%Y-%m-%d')
            display_df['환산수량'] = display_df.apply(lambda r: format_qty_display(r['수량'], r['박스입수']), axis=1)
            display_df['공급가액(원)'] = display_df['공급가액'].apply(lambda x: f"{int(x):,}")
            
            display_df = display_df[['일자', '브랜드', '품목명', '환산수량', '공급가액(원)']]
            st.dataframe(display_df.sort_values(by='일자', ascending=False), use_container_width=True)

    except Exception as e:
        st.error(f"데이터 분석 중 오류가 발생했습니다: {e}")
