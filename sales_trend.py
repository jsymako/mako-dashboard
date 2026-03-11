import streamlit as st
import pandas as pd
import datetime
from dateutil.relativedelta import relativedelta
import altair as alt

def run(load_data_func):
    st.title("📈 판매 현황 및 트렌드 분석")
    st.markdown("매출액과 판매량을 브랜드 및 품목코드별로 정확하게 분석합니다.")

    try:
        # 1. 데이터 불러오기
        df_sales_raw = load_data_func("sales_record")
        df_item = load_data_func("ecount_item_data") 
        
        # --- [데이터 전처리: 품목 정보 (Master Data)] ---
        # ecount_item_data에서 공식 이름, 브랜드, 박스입수(D열) 가져오기
        box_col_name = df_item.columns[3] 
        df_item_master = df_item[['품목코드', '품목명', '브랜드', box_col_name]].copy()
        df_item_master.rename(columns={'품목명': '공식품목명', box_col_name: '박스입수'}, inplace=True)
        df_item_master['박스입수'] = pd.to_numeric(df_item_master['박스입수'], errors='coerce').fillna(1)
        
        # --- [데이터 전처리: 판매 기록 (Raw Data)] ---
        df_sales_raw.columns = df_sales_raw.columns.str.strip()
        
        if '일자' not in df_sales_raw.columns or '품목코드' not in df_sales_raw.columns:
            st.error("🚨 시트 제목('일자', '품목코드')을 확인해주세요.")
            return

        df_sales_raw['일자'] = pd.to_datetime(df_sales_raw['일자'], errors='coerce')
        df_sales_raw['수량'] = pd.to_numeric(df_sales_raw['수량'].astype(str).str.replace(',', ''), errors='coerce').fillna(0)
        df_sales_raw['공급가액'] = pd.to_numeric(df_sales_raw['공급가액'].astype(str).str.replace(',', ''), errors='coerce').fillna(0)
        
        df_sales_raw = df_sales_raw.dropna(subset=['일자'])
        df_sales_raw = df_sales_raw[df_sales_raw['수량'] > 0] 

        # 🚀 [핵심 수정] 판매기록의 품목명은 버리고, 품목코드 기준으로 공식 정보 매칭
        # Raw Data의 품목명 컬럼을 제거하여 중복 이름 방지
        if '품목명' in df_sales_raw.columns:
            df_sales_raw = df_sales_raw.drop(columns=['품목명'])
            
        df_sales = pd.merge(df_sales_raw, df_item_master, on='품목코드', how='left')
        
        # 정보가 없는 품목(기타) 처리
        df_sales['공식품목명'] = df_sales['공식품목명'].fillna(df_sales['품목코드']) # 이름 없으면 코드라도 표시
        df_sales['브랜드'] = df_sales['브랜드'].fillna('기타')
        df_sales['박스입수'] = df_sales['박스입수'].fillna(1)
        df_sales['환산수량'] = df_sales['수량'] / df_sales['박스입수']
        df_sales['월'] = df_sales['일자'].dt.strftime('%Y-%m')

        def format_qty_display(qty, box_unit):
            if box_unit <= 1: return f"{int(qty):,} 개"
            boxes = qty / box_unit
            return f"{boxes:.1f} 박스" if boxes < 10 else f"{int(boxes):,} 박스"

        # ==========================================
        # 2. 사이드바 설정
        # ==========================================
        st.sidebar.markdown("### 🔍 조회 조건")
        brand_list = ["전체보기"] + sorted(list(df_sales['브랜드'].unique()))
        selected_brand = st.sidebar.selectbox("1. 브랜드 선택", brand_list)
        
        st.sidebar.markdown("---")
        view_mode = st.sidebar.radio("2. 보기 방식", ["일별 현황", "월별 현황"])

        today = datetime.date.today()
        if view_mode == "일별 현황":
            if "trend_start_date" not in st.session_state: st.session_state.trend_start_date = today - relativedelta(months=3)
            if "trend_end_date" not in st.session_state: st.session_state.trend_end_date = today
            
            st.sidebar.markdown("### 📅 상세 기간 설정")
            start_date = st.sidebar.date_input("시작일", key="trend_start_date", format="YYYY-MM-DD")
            end_date = st.sidebar.date_input("종료일", key="trend_end_date", format="YYYY-MM-DD")
            mask = (df_sales['일자'].dt.date >= start_date) & (df_sales['일자'].dt.date <= end_date)
        else:
            st.sidebar.markdown("### 📅 달(Month) 범위 설정")
            month_list = sorted(list(df_sales['월'].unique()))
            if not month_list: return
            start_month = st.sidebar.selectbox("시작 월", month_list, index=max(0, len(month_list)-4))
            end_month = st.sidebar.selectbox("종료 월", month_list, index=len(month_list)-1)
            start_date_m = pd.to_datetime(start_month + '-01').date()
            end_date_m = (pd.to_datetime(end_month + '-01') + relativedelta(months=1, days=-1)).date()
            mask = (df_sales['일자'].dt.date >= start_date_m) & (df_sales['일자'].dt.date <= end_date_m)

        # ==========================================
        # 3. 데이터 필터링 및 KPI
        # ==========================================
        filtered_df = df_sales.loc[mask].copy()
        if selected_brand != "전체보기":
            filtered_df = filtered_df[filtered_df['브랜드'] == selected_brand]

        if filtered_df.empty:
            st.warning("데이터가 없습니다.")
            return

        total_amount = filtered_df['공급가액'].sum()
        total_qty = filtered_df['수량'].sum()
        
        col1, col2, col3, col4 = st.columns(4)
        if view_mode == "일별 현황":
            total_days = (end_date - start_date).days + 1
            col2.metric("📅 분석 기간", f"{total_days} 일", f"{start_date} ~ {end_date}", delta_color="off")
            col3.metric("💸 일평균 판매액", f"{int(total_amount / total_days):,} 원")
        else:
            diff_months = (pd.to_datetime(end_month).year - pd.to_datetime(start_month).year) * 12 + (pd.to_datetime(end_month).month - pd.to_datetime(start_month).month) + 1
            col2.metric("📅 분석 기간", f"{diff_months} 개월", f"{start_month} ~ {end_month}", delta_color="off")
            col3.metric("💸 월평균 판매액", f"{int(total_amount / diff_months):,} 원")
        
        col1.metric("💰 총 판매액", f"{int(total_amount):,} 원")
        col4.metric("📦 총 판매수량", f"{int(total_qty):,} 개")
        
        st.markdown("---")

        # ==========================================
        # 4. 추이 및 막대 차트
        # ==========================================
        # 추이 차트
        if view_mode == "일별 현황":
            daily_trend = filtered_df.groupby('일자')[['공급가액', '수량']].sum()
            st.line_chart(daily_trend['공급가액'], color="#2E86C1")
        else:
            monthly_trend = filtered_df.groupby('월')[['공급가액', '수량']].sum()
            st.line_chart(monthly_trend['공급가액'], color="#2E86C1")

        # 🚀 [품목코드 기준 통합 집계] 🚀
        # 공식품목명을 사용하여 그룹핑 (코드가 같으면 이름도 같아짐)
        prod_summary = filtered_df.groupby(['품목코드', '공식품목명'])[['공급가액', '환산수량']].sum().reset_index()
        chart_height = max(400, len(prod_summary) * 40)
        y_axis_config = alt.Axis(labelLimit=500, labelFontSize=14, title='')

        st.subheader(f"📊 {selected_brand} 상세 현황 (코드별 합산)")
        tab_name, tab_amt, tab_qty = st.tabs(["📋 제품명 순", "💰 매출액 순위", "📦 환산수량(박스) 순위"])

        with tab_name:
            c = alt.Chart(prod_summary).mark_bar(color="#95A5A6").encode(
                x=alt.X('공급가액:Q', title='매출액'),
                y=alt.Y('공식품목명:N', sort='ascending', axis=y_axis_config)
            ).properties(height=chart_height)
            st.altair_chart(c, use_container_width=True)

        with tab_amt:
            c = alt.Chart(prod_summary).mark_bar(color="#E74C3C").encode(
                x=alt.X('공급가액:Q', title='매출액'),
                y=alt.Y('공식품목명:N', sort='-x', axis=y_axis_config)
            ).properties(height=chart_height)
            st.altair_chart(c, use_container_width=True)

        with tab_qty:
            c = alt.Chart(prod_summary).mark_bar(color="#F39C12").encode(
                x=alt.X('환산수량:Q', title='박스'),
                y=alt.Y('공식품목명:N', sort='-x', axis=y_axis_config)
            ).properties(height=chart_height)
            st.altair_chart(c, use_container_width=True)

        # 5. 상세 데이터
        with st.expander("🔍 상세 판매 기록 보기"):
            display_df = filtered_df[['일자', '브랜드', '공식품목명', '수량', '박스입수', '공급가액']].copy()
            display_df['환산수량'] = display_df.apply(lambda r: format_qty_display(r['수량'], r['박스입수']), axis=1)
            st.dataframe(display_df.sort_values(by='일자', ascending=False), use_container_width=True)

    except Exception as e:
        st.error(f"오류 발생: {e}")
