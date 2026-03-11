import streamlit as st
import pandas as pd
import numpy as np
import datetime
from dateutil.relativedelta import relativedelta
import altair as alt

def run(load_data_func):
    st.title("📈 판매 현황 및 수요 예측")
    # 🚀 사용 알고리즘 명시
    st.markdown("과거 데이터를 **지수 평활법(Exponential Smoothing)**으로 분석하여 성과를 확인하고 향후 3개월 수요를 예측합니다.")

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
        
        # 마스터 데이터와 결합
        df_sales = pd.merge(df_sales_raw, df_item_master, on='품목코드', how='inner')
        df_sales['환산수량'] = df_sales['수량'] / df_sales['박스입수']
        df_sales['월_dt'] = df_sales['일자'].dt.to_period('M').dt.to_timestamp() # 분석용 시계열 데이터
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

        # ==========================================
        # 3. 데이터 필터링
        # ==========================================
        filtered_df = df_sales.copy()
        if selected_brand != "전체보기":
            filtered_df = filtered_df[filtered_df['브랜드'] == selected_brand]
        if selected_product != "전체보기":
            filtered_df = filtered_df[filtered_df['공식품목명'] == selected_product]

        # ==========================================
        # 4. 분석 모드별 시각화
        # ==========================================
        if view_mode == "월별 현황":
            month_list = sorted(list(df_sales['월'].unique()))
            start_month = st.sidebar.selectbox("시작 월", month_list, index=max(0, len(month_list)-12))
            end_month = st.sidebar.selectbox("종료 월", month_list, index=len(month_list)-1)
            display_df = filtered_df[(filtered_df['월'] >= start_month) & (filtered_df['월'] <= end_month)]
            
            trend_data = display_df.groupby('월')[['공급가액', '수량']].sum()
            st.subheader(f"📉 {selected_product if selected_product != '전체보기' else '전체'} 월별 흐름")
            t1, t2 = st.tabs(["💰 매출액", "📦 수량"])
            with t1: st.line_chart(trend_data['공급가액'], color="#2E86C1")
            with t2: st.line_chart(trend_data['수량'], color="#28B463")

        elif view_mode == "일별 현황":
            today = datetime.date.today()
            start_date = st.sidebar.date_input("시작일", today - relativedelta(months=3))
            end_date = st.sidebar.date_input("종료일", today)
            display_df = filtered_df[(filtered_df['일자'].dt.date >= start_date) & (filtered_df['일자'].dt.date <= end_date)]
            
            trend_data = display_df.groupby('일자')[['공급가액', '수량']].sum()
            st.subheader(f"📉 {selected_product if selected_product != '전체보기' else '전체'} 일별 흐름")
            t1, t2 = st.tabs(["💰 매출액", "📦 수량"])
            with t1: st.line_chart(trend_data['공급가액'], color="#2E86C1")
            with t2: st.line_chart(trend_data['수량'], color="#28B463")

        # 🚀 [수요 예측 모드: 향후 3개월 월별 예측]
        elif view_mode == "🔮 수요 예측":
            st.subheader("🔮 향후 3개월 수요 예측 분석")
            st.info("과거 데이터를 기반으로 이번 달을 제외한 **다음 달부터 3개월간**의 예상 수요를 분석합니다.")
            
            # 월별 합계 데이터 준비 (최소 6개월 이상의 데이터 권장)
            monthly_data = filtered_df.groupby('월_dt')['수량'].sum().reset_index()
            monthly_data = monthly_data.set_index('월_dt').asfreq('MS').fillna(0)
            
            if len(monthly_data) < 4:
                st.warning("예측을 위한 월별 데이터가 부족합니다. (최소 4개월 이상의 기록 필요)")
            else:
                # 지수 평활법 함수 (Alpha 0.4 적용: 최근 트렌드 중시)
                def exp_smoothing_monthly(series, extra_periods, alpha=0.4):
                    n = len(series)
                    forecasts = np.zeros(n + extra_periods + 1) # 이번달(평균) + 미래
                    val = series[0]
                    for i in range(1, n):
                        val = alpha * series[i] + (1 - alpha) * val
                    return [val] * extra_periods

                # 예측 계산 (다음 달부터 3개월)
                forecast_values = exp_smoothing_monthly(monthly_data['수량'].values, 3)
                
                # 예측 기간 설정 (이번 달 말일 기준 다음 달 초부터)
                current_month_start = datetime.datetime.now().replace(day=1, hour=0, minute=0, second=0, microsecond=0)
                future_months = [current_month_start + relativedelta(months=i) for i in range(1, 4)]
                
                forecast_df = pd.DataFrame({
                    '월_dt': future_months,
                    '예측수량': forecast_values
                })

                # 차트용 데이터 결합 (최근 12개월 + 미래 3개월)
                plot_past = monthly_data.tail(12).reset_index().rename(columns={'수량': '실제판매량'})
                plot_future = forecast_df.rename(columns={'예측수량': '예측판매량'})
                combined_plot = pd.concat([plot_past, plot_future])

                chart = alt.Chart(combined_plot).mark_line(point=True).encode(
                    x=alt.X('월_dt:T', title='연월'),
                    y=alt.Y('실제판매량:Q', title='수량'),
                    color=alt.value("#2E86C1")
                ) + alt.Chart(combined_plot).mark_line(strokeDash=[5,5], point=True).encode(
                    x='월_dt:T',
                    y='예측판매량:Q',
                    color=alt.value("#E74C3C")
                )
                st.altair_chart(chart.properties(height=400), use_container_width=True)

                # 📦 결과 요약 및 박스 수량 표시
                st.markdown("### 📋 월별 예상 수요 요약")
                
                # 가중 평균 박스입수 계산 (품목이 '전체보기'일 경우를 대비)
                avg_box_unit = filtered_df['박스입수'].mean() if not filtered_df.empty else 1
                
                cols = st.columns(3)
                for i, row in enumerate(forecast_df.itertuples()):
                    month_str = row.월_dt.strftime('%Y년 %m월')
                    est_qty = int(row.예측수량)
                    est_box = est_qty / avg_box_unit
                    
                    with cols[i]:
                        st.metric(f"📅 {month_str}", f"{est_qty:,} 개")
                        st.caption(f"📦 약 **{est_box:.1f} 박스** (입수량 기준)")

                st.success(f"✅ 향후 3개월 총 예상 필요량: 약 **{int(sum(forecast_values)):,}** 개 (**약 {sum(forecast_values)/avg_box_unit:.1f} 박스**)")

        # 5. 상세 데이터 (공통 하단)
        if not filtered_df.empty and view_mode != "🔮 수요 예측":
            with st.expander("🔍 상세 판매 기록 보기"):
                def format_qty_display(qty, box_unit):
                    if box_unit <= 1: return f"{int(qty):,} 개"
                    boxes = qty / box_unit
                    return f"{boxes:.1f} 박스" if boxes < 10 else f"{int(boxes):,} 박스"
                
                display_df = filtered_df[['일자', '브랜드', '공식품목명', '수량', '박스입수', '공급가액']].copy()
                display_df['환산수량'] = display_df.apply(lambda r: format_qty_display(r['수량'], r['박스입수']), axis=1)
                st.dataframe(display_df.sort_values(by='일자', ascending=False), use_container_width=True)

    except Exception as e:
        st.error(f"오류 발생: {e}")
