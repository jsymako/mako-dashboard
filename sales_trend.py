import streamlit as st
import pandas as pd
import datetime
from dateutil.relativedelta import relativedelta
import altair as alt

def run(load_data_func):
    st.title("📈 판매 현황 및 트렌드 분석")
    st.markdown("매출액과 판매량을 브랜드 및 품목별로 심도 있게 분석합니다.")

    try:
        # 1. 데이터 불러오기
        df_sales = load_data_func("sales_record")
        df_item = load_data_func("ecount_item_data") 
        
        # --- [데이터 전처리: 판매 기록] ---
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

        # 월별 그룹핑을 위한 '월(YYYY-MM)' 컬럼 생성
        df_sales['월'] = df_sales['일자'].dt.strftime('%Y-%m')

        # --- [데이터 전처리: 품목 정보 매칭] ---
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

        # ==========================================
        # 2. 사이드바: 브랜드 및 보기 방식 설정
        # ==========================================
        st.sidebar.markdown("### 🔍 조회 조건")
        
        brand_list = ["전체보기"] + sorted(list(df_sales['브랜드'].unique()))
        selected_brand = st.sidebar.selectbox("1. 브랜드 선택", brand_list)
        
        st.sidebar.markdown("---")
        view_mode = st.sidebar.radio("2. 보기 방식", ["일별 현황", "월별 현황"])

        # ==========================================
        # 3. 사이드바: 날짜 조건 세팅
        # ==========================================
        today = datetime.date.today()
        
        if view_mode == "일별 현황":
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
            start_date = st.sidebar.date_input("시작일", key="trend_start_date", format="YYYY-MM-DD")
            end_date = st.sidebar.date_input("종료일", key="trend_end_date", format="YYYY-MM-DD")
            
            mask = (df_sales['일자'].dt.date >= start_date) & (df_sales['일자'].dt.date <= end_date)

        else:
            st.sidebar.markdown("### 📅 달(Month) 범위 설정")
            month_list = sorted(list(df_sales['월'].unique()))
            
            if not month_list:
                st.warning("데이터가 없습니다.")
                return

            default_start_idx = len(month_list) - 4 if len(month_list) >= 4 else 0
            start_month = st.sidebar.selectbox("시작 월", month_list, index=default_start_idx)
            end_month = st.sidebar.selectbox("종료 월", month_list, index=len(month_list)-1)
            
            start_date_m = pd.to_datetime(start_month + '-01').date()
            end_date_m = (pd.to_datetime(end_month + '-01') + relativedelta(months=1, days=-1)).date()
            mask = (df_sales['일자'].dt.date >= start_date_m) & (df_sales['일자'].dt.date <= end_date_m)

        # ==========================================
        # 4. 필터 적용 및 KPI 계산
        # ==========================================
        filtered_df = df_sales.loc[mask].copy()
        if selected_brand != "전체보기":
            filtered_df = filtered_df[filtered_df['브랜드'] == selected_brand]

        if filtered_df.empty:
            st.warning("선택하신 조건에 맞는 판매 데이터가 없습니다.")
            return

        total_amount = filtered_df['공급가액'].sum()
        total_qty = filtered_df['수량'].sum()
        
        col1, col2, col3, col4 = st.columns(4)
        
        if view_mode == "일별 현황":
            total_days = (end_date - start_date).days + 1
            daily_avg_amount = total_amount / total_days if total_days > 0 else 0
            date_range_str = f"{start_date.strftime('%Y-%m-%d')} ~ {end_date.strftime('%Y-%m-%d')}"
            
            col1.metric("💰 총 판매액", f"{int(total_amount):,} 원")
            col2.metric("📅 분석 기간", f"{total_days} 일", date_range_str, delta_color="off")
            col3.metric("💸 일평균 판매액", f"{int(daily_avg_amount):,} 원")
            col4.metric("📦 총 판매수량", f"{int(total_qty):,} 개")
        else:
            diff_months = (pd.to_datetime(end_month).year - pd.to_datetime(start_month).year) * 12 + (pd.to_datetime(end_month).month - pd.to_datetime(start_month).month) + 1
            monthly_avg_amount = total_amount / diff_months if diff_months > 0 else 0
            date_range_str = f"{start_month} ~ {end_month}"
            
            col1.metric("💰 총 판매액", f"{int(total_amount):,} 원")
            col2.metric("📅 분석 기간", f"{diff_months} 개월", date_range_str, delta_color="off")
            col3.metric("💸 월평균 판매액", f"{int(monthly_avg_amount):,} 원")
            col4.metric("📦 총 판매수량", f"{int(total_qty):,} 개")
        
        st.markdown("---")

        # ==========================================
        # 5. 추이 차트
        # ==========================================
        if view_mode == "일별 현황":
            st.subheader("📉 일별 판매 추이")
            tab1, tab2 = st.tabs(["💰 매출액 흐름", "📦 판매수량 흐름"])
            daily_trend = filtered_df.groupby('일자')[['공급가액', '수량']].sum().reset_index()
            daily_trend.set_index('일자', inplace=True)
            with tab1: st.line_chart(daily_trend['공급가액'], color="#2E86C1")
            with tab2: st.line_chart(daily_trend['수량'], color="#28B463")
        else:
            st.subheader("📉 월별 판매 추이")
            tab1, tab2 = st.tabs(["💰 매출액 흐름", "📦 판매수량 흐름"])
            monthly_trend = filtered_df.groupby('월')[['공급가액', '수량']].sum().reset_index()
            monthly_trend.set_index('월', inplace=True)
            with tab1: st.line_chart(monthly_trend['공급가액'], color="#2E86C1")
            with tab2: st.line_chart(monthly_trend['수량'], color="#28B463")

        # ==========================================
        # 6. 전체 품목 상세 현황 (가로 막대 그래프 개선)
        # ==========================================
        title_text = f"📊 {selected_brand} 품목별 상세 현황" if selected_brand != "전체보기" else "📊 전체 품목별 상세 현황"
        st.subheader(title_text)
        
        tab_name, tab_amt, tab_qty = st.tabs(["📋 제품명 순", "💰 매출액 순위", "📦 환산수량(박스) 순위"])
        
        prod_summary = filtered_df.groupby('품목명')[['공급가액', '환산수량']].sum().reset_index()
        
        # 🚀 [개선 1] 글자가 커졌으므로 줄 간격(높이)을 더 넉넉하게 (30 -> 40)
        chart_height = max(400, len(prod_summary) * 40)

        # 🚀 [개선 2] 제품명 영역 너비(labelLimit)를 500px로 대폭 확장, 글자 크기(labelFontSize) 키움
        y_axis_config = alt.Axis(
            labelLimit=500,    # 제품명이 길어도 잘리지 않게 너비 확보
            labelFontSize=15,   # 제품명 글자 크기 확대
            titleFontSize=16,   # 축 제목 크기 확대
            labelPadding=10     # 막대와 글자 사이 간격
        )

        with tab_name:
            chart_name = alt.Chart(prod_summary).mark_bar(color="#95A5A6").encode(
                x=alt.X('공급가액:Q', title='총 매출액 (원)'),
                y=alt.Y('품목명:N', sort='ascending', title='', axis=y_axis_config)
            ).properties(height=chart_height)
            st.altair_chart(chart_name, use_container_width=True)

        with tab_amt:
            chart_amt = alt.Chart(prod_summary).mark_bar(color="#E74C3C").encode(
                x=alt.X('공급가액:Q', title='총 매출액 (원)'),
                y=alt.Y('품목명:N', sort='-x', title='', axis=y_axis_config)
            ).properties(height=chart_height)
            st.altair_chart(chart_amt, use_container_width=True)

        with tab_qty:
            chart_qty = alt.Chart(prod_summary).mark_bar(color="#F39C12").encode(
                x=alt.X('환산수량:Q', title='환산수량 (박스)'),
                y=alt.Y('품목명:N', sort='-x', title='', axis=y_axis_config)
            ).properties(height=chart_height)
            st.altair_chart(chart_qty, use_container_width=True)

        # ==========================================
        # 7. 표: 데이터 상세
        # ==========================================
        with st.expander("🔍 선택된 기간의 상세 판매 기록 보기 (엑셀 형태)"):
            display_df = filtered_df[['일자', '브랜드', '품목명', '수량', '박스입수', '공급가액']].copy()
            display_df['일자'] = display_df['일자'].dt.strftime('%Y-%m-%d')
            display_df['환산수량'] = display_df.apply(lambda r: format_qty_display(r['수량'], r['박스입수']), axis=1)
            display_df['공급가액(원)'] = display_df['공급가액'].apply(lambda x: f"{int(x):,}")
            
            display_df = display_df[['일자', '브랜드', '품목명', '환산수량', '공급가액(원)']]
            st.dataframe(display_df.sort_values(by='일자', ascending=False), use_container_width=True)

    except Exception as e:
        st.error(f"데이터 분석 중 오류가 발생했습니다: {e}")
