import streamlit as st
import pandas as pd
import numpy as np
import datetime
from dateutil.relativedelta import relativedelta
import altair as alt

def run(load_data_func):
    # 🚀 글자 크기 극대화 및 스타일 보정
    st.markdown("""
        <style>
            html, body, [class*="css"]  { font-size: 1.2rem !important; }
            [data-testid="stMetricLabel"] { 
                font-size: 1.8rem !important; 
                font-weight: 800 !important; 
                color: #1E1E1E !important; 
            }
            [data-testid="stMetricValue"] { font-size: 3.0rem !important; }
            /* 박스 환산 표시 글자 크기 대폭 확대 */
            .stCaption { 
                font-size: 1.8rem !important; 
                line-height: 1.5 !important; 
                color: #007BFF !important; 
                font-weight: 800 !important;
                background-color: #f0f8ff;
                padding: 10px;
                border-radius: 8px;
                border: 1px solid #d1e9ff;
            }
            .stAlert p { font-size: 1.7rem !important; font-weight: 800 !important; }
        </style>
    """, unsafe_allow_html=True)

    st.title("📈 판매 현황 및 수요 예측")

    try:
        # 1. 데이터 불러오기
        df_sales_raw = load_data_func("sales_record")
        df_item = load_data_func("ecount_item_data") 
        
        box_col_name = df_item.columns[3] 
        df_item_master = df_item[['품목코드', '이름', '브랜드', box_col_name]].copy()
        df_item_master.rename(columns={'이름': '공식품목명', box_col_name: '박스입수'}, inplace=True)
        df_item_master['박스입수'] = pd.to_numeric(df_item_master['박스입수'], errors='coerce').fillna(1)
        
        df_sales_raw['일자'] = pd.to_datetime(df_sales_raw['일자'], errors='coerce')
        df_sales_raw['수량'] = pd.to_numeric(df_sales_raw['수량'].astype(str).str.replace(',', ''), errors='coerce').fillna(0)
        df_sales_raw['공급가액'] = pd.to_numeric(df_sales_raw['공급가액'].astype(str).str.replace(',', ''), errors='coerce').fillna(0)
        
        df_sales = pd.merge(df_sales_raw, df_item_master, on='품목코드', how='inner')
        df_sales['환산수량'] = df_sales['수량'] / df_sales['박스입수']
        df_sales['월_dt'] = df_sales['일자'].dt.to_period('M').dt.to_timestamp()
        df_sales['월'] = df_sales['일자'].dt.strftime('%Y년 %m월')

        # 2. 사이드바 설정
        brand_list = ["전체보기"] + sorted(list(df_sales['브랜드'].unique()))
        selected_brand = st.sidebar.selectbox("1. 브랜드 선택", brand_list)
        product_df = df_sales if selected_brand == "전체보기" else df_sales[df_sales['브랜드'] == selected_brand]
        product_list = ["전체보기"] + sorted(list(product_df['공식품목명'].unique()))
        selected_product = st.sidebar.selectbox("2. 품목 선택", product_list)
        view_mode = st.sidebar.radio("3. 분석 모드", ["월별 현황", "일별 현황", "🔮 수요 예측"], index=2)

        filtered_df = df_sales.copy()
        if selected_brand != "전체보기":
            filtered_df = filtered_df[filtered_df['브랜드'] == selected_brand]
        if selected_product != "전체보기":
            filtered_df = filtered_df[filtered_df['공식품목명'] == selected_product]

        if view_mode == "🔮 수요 예측":
            st.subheader("🔮 향후 3개월 수요 예측 분석")
            monthly_data = filtered_df.groupby('월_dt')['수량'].sum().reset_index()
            monthly_data = monthly_data.set_index('월_dt').asfreq('MS').fillna(0)
            
            if len(monthly_data) < 12:
                st.warning("데이터가 부족합니다.")
            else:
                seasonal_profile = filtered_df.groupby(filtered_df['일자'].dt.month)['수량'].sum()
                seasonal_index = seasonal_profile / seasonal_profile.mean()
                recent_avg = monthly_data['수량'].tail(3).mean()
                
                # 예측 계산 및 출력
                current_month_start = datetime.datetime.now().replace(day=1)
                forecast_results = []
                for i in range(1, 4):
                    target_date = current_month_start + relativedelta(months=i)
                    weight = seasonal_index.get(target_date.month, 1.0)
                    forecast_results.append({'월_dt': target_date, '예측수량': recent_avg * weight})
                
                forecast_df = pd.DataFrame(forecast_results)

                # 🚀 박스 계산 로직 수정 (단일 품목이면 해당 박스입수 사용, 전체면 가중평균 지양)
                if selected_product != "전체보기":
                    box_unit = filtered_df['박스입수'].iloc[0]
                else:
                    # 전체보기일 때는 전체 평균보다는 데이터 내의 비중을 고려해야 하나, 
                    # 대표님 피드백대로 1일 때 '개'로 표시되도록 처리
                    box_unit = filtered_df['박스입수'].mean()

                st.markdown("### 📋 월별 예상 수요 요약")
                cols = st.columns(3)
                for i, row in enumerate(forecast_df.itertuples()):
                    with cols[i]:
                        # 🚀 날짜 생략하고 '00월'만 표시
                        st.metric(f"{row.월_dt.strftime('%m월')}", f"{int(row.예측수량):,} 개")
                        
                        # 🚀 박스입수가 1이면 '개', 아니면 '박스' (글자 크기는 CSS로 상향)
                        if box_unit <= 1:
                            st.caption(f"📦 약 **{int(row.예측수량):,} 개**")
                        else:
                            st.caption(f"📦 약 **{row.예측수량/box_unit:.1f} 박스**")
                
                total_est = sum(forecast_df['예측수량'])
                total_box_str = f"{int(total_est):,} 개" if box_unit <= 1 else f"{total_est/box_unit:.1f} 박스"
                st.success(f"✅ 3개월 총 예상 필요량: 약 {int(total_est):,} 개 (약 {total_box_str})")

        # (나머지 시각화 코드 및 테이블 출력 부분은 동일하게 유지)

    except Exception as e:
        st.error(f"오류 발생: {e}")
