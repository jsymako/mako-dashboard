import streamlit as st
import pandas as pd
import numpy as np
import datetime
from dateutil.relativedelta import relativedelta
import altair as alt

def run(load_data_func):
    st.title("📈 판매 현황 및 수요 예측")
    # 🚀 알고리즘 설명 업데이트
    st.markdown("과거 1년 데이터를 **계절성 지수 평활법(Seasonal Exponential Smoothing)**으로 분석하여 향후 3개월 수요를 예측합니다.")

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
        df_sales_raw = df_sales_raw.dropna(subset=['일자'])
        
        # 데이터 결합
        df_sales = pd.merge(df_sales_raw, df_item_master, on='품목코드', how='inner')
        df_sales['환산수량'] = df_sales['수량'] / df_sales['박스입수']
        df_sales['월_dt'] = df_sales['일자'].dt.to_period('M').dt.to_timestamp()
        df_sales['월_num'] = df_sales['일자'].dt.month # 계절성 계산용 (1~12)
        df_sales['월'] = df_sales['일자'].dt.strftime('%Y-%m')

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

        # 필터링
        filtered_df = df_sales.copy()
        if selected_brand != "전체보기":
            filtered_df = filtered_df[filtered_df['브랜드'] == selected_brand]
        if selected_product != "전체보기":
            filtered_df = filtered_df[filtered_df['공식품목명'] == selected_product]

        # ==========================================
        # 3. 분석 모드별 시각화
        # ==========================================
        if view_mode == "월별 현황":
            # (기존 월별 현황 코드 유지)
            month_list = sorted(list(df_sales['월'].unique()))
            start_month = st.sidebar.selectbox("시작 월", month_list, index=max(0, len(month_list)-12))
            end_month = st.sidebar.selectbox("종료 월", month_list, index=len(month_list)-1)
            display_df = filtered_df[(filtered_df['월'] >= start_month) & (filtered_df['월'] <= end_month)]
            trend_data = display_df.groupby('월')[['수량']].sum()
            st.subheader(f"📉 월별 판매 흐름")
            st.line_chart(trend_data['수량'], color="#2E86C1")

        elif view_mode == "일별 현황":
            # (기존 일별 현황 코드 유지)
            today = datetime.date.today()
            start_date = st.sidebar.date_input("시작일", today - relativedelta(months=3))
            end_date = st.sidebar.date_input("종료일", today)
            display_df = filtered_df[(filtered_df['일자'].dt.date >= start_date) & (filtered_df['일자'].dt.date <= end_date)]
            trend_data = display_df.groupby('일자')[['수량']].sum()
            st.subheader(f"📉 일별 판매 흐름")
            st.line_chart(trend_data['수량'], color="#2E86C1")

        # 🚀 [업그레이드: 계절성 반영 수요 예측]
        elif view_mode == "🔮 수요 예측":
            st.subheader("🔮 향후 3개월 수요 예측 분석 (계절성 반영)")
            st.info("작년 동월 판매 비중을 분석하여, 다음 달부터 3개월간의 수요를 예측합니다.")
            
            # 1. 월별 데이터 집계
            monthly_data = filtered_df.groupby('월_dt')['수량'].sum().reset_index()
            monthly_data = monthly_data.set_index('월_dt').asfreq('MS').fillna(0)
            
            if len(monthly_data) < 12:
                st.warning("계절성 분석을 위해서는 최소 12개월 이상의 데이터가 필요합니다. (현재 데이터 부족)")
            else:
                # 2. 계절성 지수(Seasonal Index) 계산
                # 작년 한 해 동안 각 월이 차지하는 판매 비중 계산
                last_year_data = filtered_df[filtered_df['일자'] > (filtered_df['일자'].max() - relativedelta(years=1))]
                seasonal_profile = last_year_data.groupby(last_year_data['일자'].dt.month)['수량'].sum()
                seasonal_index = seasonal_profile / seasonal_profile.mean() # 평균 대비 비중
                
                # 3. 현재의 기초 판매 체력(Level) 계산 (최근 3개월 가중 평균)
                recent_avg = monthly_data['수량'].tail(3).mean()
                
                # 4. 미래 3개월 예측 (기초 체력 * 해당 월의 계절 비중)
                current_month_start = datetime.datetime.now().replace(day=1, hour=0, minute=0, second=0, microsecond=0)
                forecast_results = []
                for i in range(1, 4):
                    target_date = current_month_start + relativedelta(months=i)
                    month_num = target_date.month
                    weight = seasonal_index.get(month_num, 1.0) # 해당 월의 가중치
                    pred_qty = recent_avg * weight
                    forecast_results.append({'월_dt': target_date, '예측수량': pred_qty})
                
                forecast_df = pd.DataFrame(forecast_results)

                # 5. 시각화
                plot_past = monthly_data.tail(12).reset_index().rename(columns={'수량': '실제판매량'})
                plot_future = forecast_df.rename(columns={'예측수량': '예측판매량'})
                combined_plot = pd.concat([plot_past, plot_future])

                chart = alt.Chart(combined_plot).mark_line(point=True).encode(
                    x=alt.X('월_dt:T', title='연월'),
                    y=alt.Y('실제판매량:Q', title='수량(개)'),
                    color=alt.value("#2E86C1")
                ) + alt.Chart(combined_plot).mark_line(strokeDash=[5,5], point=True).encode(
                    x='월_dt:T',
                    y='예측판매량:Q',
                    color=alt.value("#E74C3C")
                )
                st.altair_chart(chart.properties(height=400), use_container_width=True)

                # 6. 결과 요약
                st.markdown("### 📋 월별 예상 수요 요약")
                avg_box_unit = filtered_df['박스입수'].mean() if not filtered_df.empty else 1
                cols = st.columns(3)
                
                for i, row in enumerate(forecast_df.itertuples()):
                    month_str = row.월_dt.strftime('%Y년 %m월')
                    est_qty = int(row.예측수량)
                    est_box = est_qty / avg_box_unit
                    with cols[i]:
                        st.metric(f"📅 {month_str}", f"{est_qty:,} 개")
                        st.caption(f"📦 약 **{est_box:.1f} 박스**")

                total_est = sum(forecast_df['예측수량'])
                st.success(f"✅ 3개월 총 예상 필요량: 약 **{int(total_est):,}** 개 (**약 {total_est/avg_box_unit:.1f} 박스**)")

    except Exception as e:
        st.error(f"오류 발생: {e}")
