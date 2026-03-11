import streamlit as st
import pandas as pd
import datetime
from dateutil.relativedelta import relativedelta
import altair as alt

def run(load_data_func):
    st.title("📈 판매 현황 및 트렌드 분석")
    st.markdown("매출액과 판매량을 브랜드 및 개별 품목별로 심도 있게 분석합니다.")

    try:
        # 1. 데이터 불러오기
        df_sales_raw = load_data_func("sales_record")
        df_item = load_data_func("ecount_item_data") 
        
        # --- [데이터 전처리: 품목 정보] ---
        box_col_name = df_item.columns[3] 
        df_item_master = df_item[['품목코드', '이름', '브랜드', box_col_name]].copy()
        df_item_master.rename(columns={'이름': '공식품목명', box_col_name: '박스입수'}, inplace=True)
        df_item_master['박스입수'] = pd.to_numeric(df_item_master['박스입수'], errors='coerce').fillna(1)
        
        # --- [데이터 전처리: 판매 기록] ---
        df_sales_raw.columns = df_sales_raw.columns.str.strip()
        if '일자' not in df_sales_raw.columns or '품목코드' not in df_sales_raw.columns:
            st.error("🚨 시트 제목('일자', '품목코드')을 확인해주세요.")
            return

        df_sales_raw['일자'] = pd.to_datetime(df_sales_raw['일자'], errors='coerce')
        df_sales_raw['수량'] = pd.to_numeric(df_sales_raw['수량'].astype(str).str.replace(',', ''), errors='coerce').fillna(0)
        df_sales_raw['공급가액'] = pd.to_numeric(df_sales_raw['공급가액'].astype(str).str.replace(',', ''), errors='coerce').fillna(0)
        df_sales_raw = df_sales_raw.dropna(subset=['일자'])
        df_sales_raw = df_sales_raw[df_sales_raw['수량'] > 0] 

        if '품목명' in df_sales_raw.columns:
            df_sales_raw = df_sales_raw.drop(columns=['품목명'])
            
        # ecount_item_data에 등록된 품목만 분석 (inner join)
        df_sales = pd.merge(df_sales_raw, df_item_master, on='품목코드', how='inner')
        df_sales['환산수량'] = df_sales['수량'] / df_sales['박스입수']
        df_sales['월'] = df_sales['일자'].dt.strftime('%Y-%m')

        def format_qty_display(qty, box_unit):
            if box_unit <= 1: return f"{int(qty):,} 개"
            boxes = qty / box_unit
            return f"{boxes:.1f} 박스" if boxes < 10 else f"{int(boxes):,} 박스"

        # ==========================================
        # 2. 사이드바: 브랜드 & 품목 연동 필터
        # ==========================================
        st.sidebar.markdown("### 🔍 조회 조건")
        brand_list = ["전체보기"] + sorted(list(df_sales['브랜드'].unique()))
        selected_brand = st.sidebar.selectbox("1. 브랜드 선택", brand_list)
        
        if selected_brand == "전체보기":
            product_df = df_sales
        else:
            product_df = df_sales[df_sales['브랜드'] == selected_brand]
        
        product_list = ["전체보기"] + sorted(list(product_df['공식품목명'].unique()))
        selected_product = st.sidebar.selectbox("2. 품목 선택", product_list)
        
        st.sidebar.markdown("---")
        view_mode = st.sidebar.radio("3. 보기 방식", ["일별 현황", "월별 현황"])

        # ==========================================
        # 3. 사이드바: 날짜 조건
        # ==========================================
        today = datetime.date.today()
        if view_mode == "일별 현황":
            if "trend_start_date" not in st.session_state: st.session_state.trend_start_date = today - relativedelta(months=3)
            if "trend_end_date" not in st.session_state: st.session_state.trend_end_date = today
            start_date = st.sidebar.date_input("시작일", key="trend_start_date", format="YYYY-MM-DD")
            end_date = st.sidebar.date_input("종료일", key="trend_end_date", format="YYYY-MM-DD")
            mask = (df_sales['일자'].dt.date >= start_date) & (df_sales['일자'].dt.date <= end_date)
            date_range_str = f"{start_date} ~ {end_date}"
        else:
            month_list = sorted(list(df_sales['월'].unique()))
            if not month_list: return
            start_month = st.sidebar.selectbox("시작 월", month_list, index=max(0, len(month_list)-4))
            end_month = st.sidebar.selectbox("종료 월", month_list, index=len(month_list)-1)
            start_date_m = pd.to_datetime(start_month + '-01').date()
            end_date_m = (pd.to_datetime(end_month + '-01') + relativedelta(months=1, days=-1)).date()
            mask = (df_sales['일자'].dt.date >= start_date_m) & (df_sales['일자'].dt.date <= end_date_m)
            date_range_str = f"{start_month} ~ {end_month}"

        # ==========================================
        # 4. 필터 적용 및 KPI
        # ==========================================
        filtered_df = df_sales.loc[mask].copy()
        if selected_brand != "전체보기":
            filtered_df = filtered_df[filtered_df['브랜드'] == selected_brand]
        if selected_product != "전체보기":
            filtered_df = filtered_df[filtered_df['공식품목명'] == selected_product]

        if filtered_df.empty:
            st.warning("선택하신 조건에 맞는 데이터가 없습니다.")
            return

        total_amount = filtered_df['공급가액'].sum()
        total_qty = filtered_df['수량'].sum()
        
        col1, col2, col3, col4 = st.columns(4)
        col1.metric("💰 총 판매액", f"{int(total_amount):,} 원")
        
        if view_mode == "일별 현황":
            total_days = (end_date - start_date).days + 1
            col2.metric("📅 분석 기간", f"{total_days} 일", date_range_str, delta_color="off")
            col3.metric("💸 일평균 판매액", f"{int(total_amount / total_days if total_days > 0 else 0):,} 원")
        else:
            diff_months = (pd.to_datetime(end_month).year - pd.to_datetime(start_month).year) * 12 + (pd.to_datetime(end_month).month - pd.to_datetime(start_month).month) + 1
            col2.metric("📅 분석 기간", f"{diff_months} 개월", date_range_str, delta_color="off")
            col3.metric("💸 월평균 판매액", f"{int(total_amount / diff_months if diff_months > 0 else 0):,} 원")
        
        col4.metric("📦 총 판매수량", f"{int(total_qty):,} 개")
        st.markdown("---")

        # ==========================================
        # 5. 🚀 추이 차트 (탭 부활)
        # ==========================================
        st.subheader(f"📉 {selected_product if selected_product != '전체보기' else '전체'} 판매 추이")
        tab_line_amt, tab_line_qty = st.tabs(["💰 매출액 흐름", "📦 판매수량 흐름"])
        
        if view_mode == "일별 현황":
            trend_data = filtered_df.groupby('일자')[['공급가액', '수량']].sum()
        else:
            trend_data = filtered_df.groupby('월')[['공급가액', '수량']].sum()
            
        with tab_line_amt:
            st.line_chart(trend_data['공급가액'], color="#2E86C1")
        with tab_line_qty:
            st.line_chart(trend_data['수량'], color="#28B463")

        # ==========================================
        # 6. 품목별 상세 현황 (수평 막대 차트)
        # ==========================================
        st.subheader(f"📊 {selected_brand} 품목별 상세 현황")
        tab_name, tab_amt, tab_qty = st.tabs(["📋 제품명 순", "💰 매출액 순위", "📦 환산수량(박스) 순위"])
        
        prod_summary = filtered_df.groupby(['품목코드', '공식품목명'])[['공급가액', '환산수량']].sum().reset_index()
        chart_height = max(400, len(prod_summary) * 40)
        y_axis_config = alt.Axis(labelLimit=500, labelFontSize=15, title='')

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

        # 7. 상세 데이터
        with st.expander("🔍 상세 판매 기록 보기"):
            display_df = filtered_df[['일자', '브랜드', '공식품목명', '수량', '박스입수', '공급가액']].copy()
            display_df['환산수량'] = display_df.apply(lambda r: format_qty_display(r['수량'], r['박스입수']), axis=1)
            st.dataframe(display_df.sort_values(by='일자', ascending=False), use_container_width=True)

    except Exception as e:
        st.error(f"오류 발생: {e}")
