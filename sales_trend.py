import streamlit as st
import pandas as pd
import numpy as np
import datetime
from dateutil.relativedelta import relativedelta
import altair as alt

def run(load_data_func):
    st.title("📈 판매 현황 및 수요 예측")
    st.markdown("과거 데이터를 분석하여 성과를 확인하고 향후 수요를 예측합니다.")

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
        df_sales['월'] = df_sales['일자'].dt.strftime('%Y-%m')

        # ==========================================
        # 2. 사이드바 설정 (월별 현황이 기본값)
        # ==========================================
        st.sidebar.markdown("### 🔍 조회 조건")
        brand_list = ["전체보기"] + sorted(list(df_sales['브랜드'].unique()))
        selected_brand = st.sidebar.selectbox("1. 브랜드 선택", brand_list)
        
        product_df = df_sales if selected_brand == "전체보기" else df_sales[df_sales['브랜드'] == selected_brand]
        product_list = ["전체보기"] + sorted(list(product_df['공식품목명'].unique()))
        selected_product = st.sidebar.selectbox("2. 품목 선택", product_list)
        
        st.sidebar.markdown("---")
        # 🚀 순서 변경 및 월별 현황을 기본값(index=0)으로 설정
        view_mode = st.sidebar.radio("3. 분석 모드", ["월별 현황", "일별 현황", "🔮 수요 예측"], index=0)

        # ==========================================
        # 3. 날짜 및 필터 적용
        # ==========================================
        today = datetime.date.today()
        filtered_df = df_sales.copy()
        if selected_brand != "전체보기":
            filtered_df = filtered_df[filtered_df['브랜드'] == selected_brand]
        if selected_product != "전체보기":
            filtered_df = filtered_df[filtered_df['공식품목명'] == selected_product]

        if view_mode == "일별 현황":
            if "trend_start_date" not in st.session_state: st.session_state.trend_start_date = today - relativedelta(months=3)
            start_date = st.sidebar.date_input("시작일", key="trend_start_date")
            end_date = st.sidebar.date_input("종료일", value=today)
            filtered_df = filtered_df[(filtered_df['일자'].dt.date >= start_date) & (filtered_df['일자'].dt.date <= end_date)]
        
        elif view_mode == "월별 현황":
            month_list = sorted(list(df_sales['월'].unique()))
            start_month = st.sidebar.selectbox("시작 월", month_list, index=max(0, len(month_list)-12))
            end_month = st.sidebar.selectbox("종료 월", month_list, index=len(month_list)-1)
            filtered_df = filtered_df[(filtered_df['월'] >= start_month) & (filtered_df['월'] <= end_month)]

        # ==========================================
        # 4. KPI 지표 표시
        # ==========================================
        if not filtered_df.empty:
            total_amount = filtered_df['공급가액'].sum()
            total_qty = filtered_df['수량'].sum()
            
            c1, c2, c3 = st.columns(3)
            c1.metric("💰 총 판매액", f"{int(total_amount):,} 원")
            c2.metric("📦 총 판매수량", f"{int(total_qty):,} 개")
            c3.metric("🛒 분석 품목 수", f"{len(filtered_df['품목코드'].unique()):,} 종")
            st.markdown("---")

        # ==========================================
        # 5. 분석 모드별 시각화
        # ==========================================
        if view_mode in ["월별 현황", "일별 현황"]:
            group_col = '월' if view_mode == "월별 현황" else '일자'
            trend_data = filtered_df.groupby(group_col)[['공급가액', '수량']].sum()
            
            st.subheader(f"📉 {selected_product if selected_product != '전체보기' else '전체'} 판매 흐름")
            t1, t2 = st.tabs(["💰 매출액", "📦 수량"])
            with t1: st.line_chart(trend_data['공급가액'], color="#2E86C1")
            with t2: st.line_chart(trend_data['수량'], color="#28B463")

            # 하단 제품별 막대 차트
            st.subheader("📊 상세 항목별 순위")
            prod_summary = filtered_df.groupby(['공식품목명'])[['공급가액', '환산수량']].sum().reset_index()
            y_axis = alt.Axis(labelLimit=500, labelFontSize=14)
            
            c_amt = alt.Chart(prod_summary).mark_bar(color="#E74C3C").encode(
                x=alt.X('공급가액:Q', title='매출액'),
                y=alt.Y('공식품목명:N', sort='-x', axis=y_axis, title='')
            ).properties(height=max(400, len(prod_summary)*30))
            st.altair_chart(c_amt, use_container_width=True)

        # 🚀 [수요 예측 모드]
        elif view_mode == "🔮 수요 예측":
            st.subheader("🔮 향후 30일 수요 예측 분석")
            st.info("과거 1년 데이터를 기반으로 향후 30일간의 판매 추세를 시뮬레이션합니다.")
            
            # 일별 합계 데이터 준비
            daily_data = filtered_df.groupby('일자')['수량'].sum().reset_index()
            daily_data = daily_data.set_index('일자').asfreq('D').fillna(0) # 빈 날짜 채우기
            
            if len(daily_data) < 30:
                st.warning("예측을 위한 데이터가 부족합니다. (최소 30일 이상의 기록 필요)")
            else:
                # 간단한 지수 평활 예측 알고리즘 (Alpha 0.3 적용)
                def simple_exp_smoothing(series, extra_periods, alpha=0.3):
                    n = len(series)
                    forecasts = np.zeros(n + extra_periods)
                    forecasts[0] = series[0]
                    for t in range(1, n):
                        forecasts[t] = alpha * series[t-1] + (1 - alpha) * forecasts[t-1]
                    for t in range(n, n + extra_periods):
                        forecasts[t] = forecasts[t-1]
                    return forecasts[-extra_periods:]

                last_30_forecast = simple_exp_smoothing(daily_data['수량'].values, 30)
                
                # 시각화 데이터 구성
                future_dates = [daily_data.index[-1] + datetime.timedelta(days=i) for i in range(1, 31)]
                forecast_df = pd.DataFrame({'일자': future_dates, '예측수량': last_30_forecast})
                
                # 예측 결과 차트
                combined_chart_data = pd.concat([
                    daily_data.tail(60).reset_index().rename(columns={'수량': '실제판매량'}),
                    forecast_df.rename(columns={'예측수량': '예측판매량'})
                ])
                
                chart = alt.Chart(combined_chart_data).mark_line().encode(
                    x='일자:T',
                    y=alt.Y('실제판매량:Q', title='판매 수량'),
                    color=alt.value("#2E86C1")
                ) + alt.Chart(combined_chart_data).mark_line(strokeDash=[5,5]).encode(
                    x='일자:T',
                    y='예측판매량:Q',
                    color=alt.value("#E74C3C")
                )
                st.altair_chart(chart.properties(height=400), use_container_width=True)
                
                # 예측 요약 KPI
                next_month_est = int(sum(last_30_forecast))
                st.success(f"📅 **향후 30일 예상 총 수요:** 약 **{next_month_est:,}** 개 (또는 박스)")
                st.caption("※ 이 예측은 과거 패턴을 기반으로 한 통계적 수치이며, 실제 시장 상황에 따라 다를 수 있습니다.")

    except Exception as e:
        st.error(f"오류 발생: {e}")
