import streamlit as st
import pandas as pd
import numpy as np
import datetime
from dateutil.relativedelta import relativedelta
import altair as alt

def run(load_data_func):
    # 🚀 CSS 주입: 전반적인 글자 크기 상향 및 Metric 가독성 강화
    st.markdown("""
        <style>
            html, body, [class*="css"]  { font-size: 1.1rem; }
            [data-testid="stMetricLabel"] { font-size: 1.3rem !important; font-weight: bold !important; color: #31333F !important; }
            [data-testid="stMetricValue"] { font-size: 2.2rem !important; }
            [data-testid="stMetricDelta"] { font-size: 1.1rem !important; font-weight: 500 !important; }
            .stCaption { font-size: 1.1rem !important; line-height: 1.5 !important; color: #555 !important; }
            button[data-baseweb="tab"] { font-size: 1.2rem !important; }
        </style>
    """, unsafe_allow_html=True)

    st.title("📈 판매 현황 및 수요 예측")
    st.markdown("과거 데이터를 **계절성 지수 평활법**으로 분석하여 성과를 확인하고 향후 수요를 예측합니다.")

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
        df_sales_raw['일자'] = pd.to_datetime(df_sales_raw['일자'], errors='coerce')
        df_sales_raw['수량'] = pd.to_numeric(df_sales_raw['수량'].astype(str).str.replace(',', ''), errors='coerce').fillna(0)
        df_sales_raw['공급가액'] = pd.to_numeric(df_sales_raw['공급가액'].astype(str).str.replace(',', ''), errors='coerce').fillna(0)
        df_sales_raw = df_sales_raw.dropna(subset=['일자'])
        
        df_sales = pd.merge(df_sales_raw, df_item_master, on='품목코드', how='inner')
        df_sales['환산수량'] = df_sales['수량'] / df_sales['박스입수']
        df_sales['월_dt'] = df_sales['일자'].dt.to_period('M').dt.to_timestamp()
        df_sales['월'] = df_sales['일자'].dt.strftime('%Y년 %m월')

        # ==========================================
        # 2. 사이드바 설정
        # ==========================================
        st.sidebar.markdown("### 🔍 조회 조건")
        brand_list = ["전체보기"] + sorted(list(df_sales['브랜드'].unique()))
        selected_brand = st.sidebar.selectbox("1. 브랜드 선택", brand_list)
        
        product_df = df_sales if selected_brand == "전체보기" else df_sales[df_sales['브랜드'] == selected_brand]
        product_list = ["전체보기"] + sorted(list(product_df['공식품목명'].unique()))
        selected_product = st.sidebar.selectbox("2. 품목 선택", product_list)
        
        st.sidebar.markdown("---")
        view_mode = st.sidebar.radio("3. 분석 모드", ["월별 현황", "일별 현황", "🔮 수요 예측"], index=0)

        # 공통 필터링
        filtered_df = df_sales.copy()
        if selected_brand != "전체보기":
            filtered_df = filtered_df[filtered_df['브랜드'] == selected_brand]
        if selected_product != "전체보기":
            filtered_df = filtered_df[filtered_df['공식품목명'] == selected_product]

        # ==========================================
        # 3. 날짜 설정 및 필터
        # ==========================================
        today = datetime.date.today()
        if view_mode == "일별 현황":
            if "trend_start_date" not in st.session_state: st.session_state.trend_start_date = today - relativedelta(months=3)
            start_date = st.sidebar.date_input("시작일", key="trend_start_date")
            end_date = st.sidebar.date_input("종료일", value=today)
            mask = (filtered_df['일자'].dt.date >= start_date) & (filtered_df['일자'].dt.date <= end_date)
            display_df = filtered_df.loc[mask].copy()
            date_range_str = f"{start_date.strftime('%Y년 %m월 %d일')} ~ {end_date.strftime('%Y년 %m월 %d일')}"
        elif view_mode == "월별 현황":
            month_list = sorted(list(df_sales['월'].unique()))
            start_month = st.sidebar.selectbox("시작 월", month_list, index=max(0, len(month_list)-12))
            end_month = st.sidebar.selectbox("종료 월", month_list, index=len(month_list)-1)
            display_df = filtered_df[(filtered_df['월'] >= start_month) & (filtered_df['월'] <= end_month)]
            date_range_str = f"{start_month} ~ {end_month}"
        else:
            display_df = filtered_df

        if display_df.empty:
            st.warning("선택하신 조건에 데이터가 없습니다.")
            return

        # ==========================================
        # 4. KPI 표시
        # ==========================================
        total_amount = display_df['공급가액'].sum()
        total_qty = display_df['수량'].sum()
        
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("💰 총 판매액", f"{int(total_amount):,} 원")
        
        if view_mode == "일별 현황":
            diff = (end_date - start_date).days + 1
            c2.metric("📅 분석 기간", f"{diff} 일", date_range_str, delta_color="off")
            c3.metric("💸 일평균 판매액", f"{int(total_amount/diff if diff>0 else 0):,} 원")
        elif view_mode == "월별 현황":
            d1 = pd.to_datetime(start_month, format='%Y년 %m월')
            d2 = pd.to_datetime(end_month, format='%Y년 %m월')
            diff = (d2.year - d1.year) * 12 + (d2.month - d1.month) + 1
            c2.metric("📅 분석 기간", f"{diff} 개월", date_range_str, delta_color="off")
            c3.metric("💸 월평균 판매액", f"{int(total_amount/diff if diff>0 else 0):,} 원")
        else:
            c2.metric("📊 데이터 기준", "최근 12개월")
            c3.metric("🏷️ 브랜드", selected_brand)

        c4.metric("📦 총 판매수량", f"{int(total_qty):,} 개")
        st.markdown("---")

        # ==========================================
        # 5. 메인 시각화
        # ==========================================
        common_axis_config = alt.Axis(labelFontSize=15, titleFontSize=17, labelAngle=0)

        if view_mode in ["월별 현황", "일별 현황"]:
            st.subheader(f"📉 {selected_product if selected_product != '전체보기' else '전체'} 판매 추이")
            t_line1, t_line2 = st.tabs(["💰 매출액 흐름", "📦 판매수량 흐름"])
            group_key = '월' if view_mode == "월별 현황" else '일자'
            trend_data = display_df.groupby(group_key)[['공급가액', '수량']].sum().reset_index()
            
            with t_line1:
                chart_l1 = alt.Chart(trend_data).mark_line(point=True, color="#2E86C1").encode(
                    x=alt.X(f'{group_key}:{"T" if view_mode=="일별 현황" else "N"}', title='', axis=common_axis_config),
                    y=alt.Y('공급가액:Q', title='매출액 (원)', axis=common_axis_config)
                ).properties(height=350)
                st.altair_chart(chart_l1, use_container_width=True)
            with t_line2:
                chart_l2 = alt.Chart(trend_data).mark_line(point=True, color="#28B463").encode(
                    x=alt.X(f'{group_key}:{"T" if view_mode=="일별 현황" else "N"}', title='', axis=common_axis_config),
                    y=alt.Y('수량:Q', title='수량 (개)', axis=common_axis_config)
                ).properties(height=350)
                st.altair_chart(chart_l2, use_container_width=True)

            # 🚀 [로직 변경 핵심] 브랜드가 '전체보기'일 때는 브랜드별로 집계
            if selected_brand == "전체보기":
                st.subheader("📊 브랜드별 판매 현황")
                group_field = '브랜드'
                tab_names = ["📋 브랜드명 순", "💰 매출액 순위", "📦 박스 순위"]
            else:
                st.subheader(f"📊 {selected_brand} 품목별 상세 순위")
                group_field = '공식품목명'
                tab_names = ["📋 제품명 순", "💰 매출액 순위", "📦 박스 순위"]

            tab_name, tab_amt, tab_qty = st.tabs(tab_names)
            prod_summary = display_df.groupby([group_field])[['공급가액', '환산수량']].sum().reset_index()
            chart_height = max(400, len(prod_summary) * 45)
            y_axis_large = alt.Axis(labelLimit=500, labelFontSize=17, title='', labelPadding=20, offset=0)

            with tab_name:
                c = alt.Chart(prod_summary).mark_bar(color="#95A5A6").encode(
                    x=alt.X('공급가액:Q', title='매출액', axis=common_axis_config),
                    y=alt.Y(f'{group_field}:N', sort='ascending', axis=y_axis_large)
                ).configure_view(strokeWidth=0).properties(height=chart_height)
                st.altair_chart(c, use_container_width=True)
            with tab_amt:
                c = alt.Chart(prod_summary).mark_bar(color="#E74C3C").encode(
                    x=alt.X('공급가액:Q', title='매출액', axis=common_axis_config),
                    y=alt.Y(f'{group_field}:N', sort='-x', axis=y_axis_large)
                ).configure_view(strokeWidth=0).properties(height=chart_height)
                st.altair_chart(c, use_container_width=True)
            with tab_qty:
                c = alt.Chart(prod_summary).mark_bar(color="#F39C12").encode(
                    x=alt.X('환산수량:Q', title='박스', axis=common_axis_config),
                    y=alt.Y(f'{group_field}:N', sort='-x', axis=y_axis_large)
                ).configure_view(strokeWidth=0).properties(height=chart_height)
                st.altair_chart(c, use_container_width=True)

        elif view_mode == "🔮 수요 예측":
            # (수요 예측 부분 유지)
            st.subheader("🔮 향후 3개월 수요 예측 분석")
            monthly_data = filtered_df.groupby('월_dt')['수량'].sum().reset_index()
            monthly_data = monthly_data.set_index('월_dt').asfreq('MS').fillna(0)
            
            if len(monthly_data) < 12:
                st.warning("정확한 분석을 위해 12개월 이상의 데이터가 필요합니다.")
            else:
                seasonal_profile = filtered_df.groupby(filtered_df['일자'].dt.month)['수량'].sum()
                seasonal_index = seasonal_profile / seasonal_profile.mean()
                recent_avg = monthly_data['수량'].tail(3).mean()
                
                current_month_start = datetime.datetime.now().replace(day=1, hour=0, minute=0, second=0)
                forecast_results = []
                for i in range(1, 4):
                    target_date = current_month_start + relativedelta(months=i)
                    weight = seasonal_index.get(target_date.month, 1.0)
                    forecast_results.append({'월_dt': target_date, '예측수량': recent_avg * weight})
                
                forecast_df = pd.DataFrame(forecast_results)
                combined_plot = pd.concat([
                    monthly_data.tail(12).reset_index().rename(columns={'수량': '값', '월_dt': '날짜'}),
                    forecast_df.rename(columns={'예측수량': '값', '월_dt': '날짜'})
                ])

                chart = alt.Chart(combined_plot).mark_line(point=True).encode(
                    x=alt.X('날짜:T', title='연월', axis=alt.Axis(format='%y년 %m월', labelFontSize=15)),
                    y=alt.Y('값:Q', title='수량', axis=common_axis_config)
                ).properties(height=400)
                st.altair_chart(chart, use_container_width=True)

                st.markdown("### 📋 월별 예상 수요 요약")
                avg_box_unit = filtered_df['박스입수'].mean() if not filtered_df.empty else 1
                cols = st.columns(3)
                for i, row in enumerate(forecast_df.itertuples()):
                    with cols[i]:
                        st.metric(f"📅 {row.월_dt.strftime('%m월 %d일')}", f"{int(row.예측수량):,} 개")
                        st.caption(f"📦 약 **{row.예측수량/avg_box_unit:.1f} 박스** (필요량)")
                
                total_est = sum(forecast_df['예측수량'])
                st.success(f"✅ 3개월 총 예상 필요량: 약 **{int(total_est):,}** 개 (**약 {total_est/avg_box_unit:.1f} 박스**)")

        with st.expander("🔍 상세 판매 기록 보기"):
            def format_qty_display(qty, box_unit):
                if box_unit <= 1: return f"{int(qty):,} 개"
                return f"{qty/box_unit:.1f} 박스"
            show_df = display_df[['일자', '브랜드', '공식품목명', '수량', '박스입수', '공급가액']].copy()
            show_df['일자'] = show_df['일자'].dt.strftime('%Y년 %m월 %d일')
            show_df['환산수량'] = show_df.apply(lambda r: format_qty_display(r['수량'], r['박스입수']), axis=1)
            st.dataframe(show_df.sort_values(by='일자', ascending=False), use_container_width=True)

    except Exception as e:
        st.error(f"오류 발생: {e}")
