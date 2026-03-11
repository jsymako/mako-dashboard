import streamlit as st
import pandas as pd
import numpy as np
import datetime
from dateutil.relativedelta import relativedelta
import altair as alt

def run(load_data_func):
    # 🚀 [전체 스타일 최적화] 텍스트 크기 상향 및 박스 수량 강조
    st.markdown("""
        <style>
            html, body, [class*="css"]  { font-size: 1.2rem !important; }
            /* 메인 제목 (00월) */
            [data-testid="stMetricLabel"] { 
                font-size: 1.8rem !important; 
                font-weight: 800 !important; 
                color: #1E1E1E !important; 
            }
            /* 메인 수치 (박스 수량) */
            [data-testid="stMetricValue"] { 
                font-size: 3.2rem !important; 
                color: #007BFF !important;
            }
            /* 보조 수치 (낱개 수량) */
            .stCaption { 
                font-size: 1.7rem !important; 
                line-height: 1.6 !important; 
                color: #444 !important; 
                font-weight: 700 !important;
                background-color: #f8f9fa;
                padding: 10px 15px;
                border-radius: 8px;
                border: 1px solid #dee2e6;
                margin-top: 5px;
            }
            .stAlert p { font-size: 1.6rem !important; font-weight: 800 !important; }
            button[data-baseweb="tab"] { font-size: 1.4rem !important; font-weight: 600 !important; }
        </style>
    """, unsafe_allow_html=True)

    st.title("📈 판매 현황 및 수요 예측")
    st.markdown("과거 데이터를 **계절성 지수 평활법**으로 분석하여 성과를 확인하고 향후 수요를 예측합니다.")

    try:
        # 1. 데이터 로드 및 전처리
        df_sales_raw = load_data_func("sales_record")
        df_item = load_data_func("ecount_item_data") 
        
        box_col_name = df_item.columns[3] 
        df_item_master = df_item[['품목코드', '이름', '브랜드', box_col_name]].copy()
        df_item_master.rename(columns={'이름': '공식품목명', box_col_name: '박스입수'}, inplace=True)
        df_item_master['박스입수'] = pd.to_numeric(df_item_master['박스입수'], errors='coerce').fillna(1)
        
        df_sales_raw.columns = df_sales_raw.columns.str.strip()
        df_sales_raw['일자'] = pd.to_datetime(df_sales_raw['일자'], errors='coerce')
        df_sales_raw['수량'] = pd.to_numeric(df_sales_raw['수량'].astype(str).str.replace(',', ''), errors='coerce').fillna(0)
        df_sales_raw['공급가액'] = pd.to_numeric(df_sales_raw['공급가액'].astype(str).str.replace(',', ''), errors='coerce').fillna(0)
        df_sales_raw = df_sales_raw.dropna(subset=['일자'])
        
        # 공식 데이터 결합
        df_sales = pd.merge(df_sales_raw, df_item_master, on='품목코드', how='inner')
        df_sales['환산수량'] = df_sales['수량'] / df_sales['박스입수']
        df_sales['월_dt'] = df_sales['일자'].dt.to_period('M').dt.to_timestamp()
        df_sales['월'] = df_sales['일자'].dt.strftime('%Y년 %m월')

        # 2. 사이드바 필터
        st.sidebar.markdown("### 🔍 조회 조건")
        brand_list = ["전체보기"] + sorted(list(df_sales['브랜드'].unique()))
        selected_brand = st.sidebar.selectbox("1. 브랜드 선택", brand_list)
        
        prod_df = df_sales if selected_brand == "전체보기" else df_sales[df_sales['브랜드'] == selected_brand]
        product_list = ["전체보기"] + sorted(list(prod_df['공식품목명'].unique()))
        selected_product = st.sidebar.selectbox("2. 품목 선택", product_list)
        
        st.sidebar.markdown("---")
        view_mode = st.sidebar.radio("3. 분석 모드", ["월별 현황", "일별 현황", "🔮 수요 예측"], index=0)

        # 3. 데이터 필터링 적용
        filtered_df = df_sales.copy()
        if selected_brand != "전체보기":
            filtered_df = filtered_df[filtered_df['브랜드'] == selected_brand]
        if selected_product != "전체보기":
            filtered_df = filtered_df[filtered_df['공식품목명'] == selected_product]

        # 4. 모드별 날짜 세팅 및 KPI
        today = datetime.date.today()
        if view_mode == "일별 현황":
            if "trend_start_date" not in st.session_state: st.session_state.trend_start_date = today - relativedelta(months=3)
            start_date = st.sidebar.date_input("시작일", key="trend_start_date")
            end_date = st.sidebar.date_input("종료일", value=today)
            display_df = filtered_df[(filtered_df['일자'].dt.date >= start_date) & (filtered_df['일자'].dt.date <= end_date)]
            date_range_str = f"{start_date.strftime('%Y년 %m월 %d일')} ~ {end_date.strftime('%Y년 %m월 %d일')}"
            diff_val = (end_date - start_date).days + 1
            avg_label = "💸 일평균 판매액"
        elif view_mode == "월별 현황":
            month_list = sorted(list(df_sales['월'].unique()))
            start_month = st.sidebar.selectbox("시작 월", month_list, index=max(0, len(month_list)-12))
            end_month = st.sidebar.selectbox("종료 월", month_list, index=len(month_list)-1)
            display_df = filtered_df[(filtered_df['월'] >= start_month) & (filtered_df['월'] <= end_month)]
            date_range_str = f"{start_month} ~ {end_month}"
            d1, d2 = pd.to_datetime(start_month, format='%Y년 %m월'), pd.to_datetime(end_month, format='%Y년 %m월')
            diff_val = (d2.year - d1.year) * 12 + (d2.month - d1.month) + 1
            avg_label = "💸 월평균 판매액"
        else:
            display_df = filtered_df
            diff_val = 0

        # KPI 상단 노출
        if not display_df.empty:
            c1, c2, c3, c4 = st.columns(4)
            c1.metric("💰 총 판매액", f"{int(display_df['공급가액'].sum()):,} 원")
            if view_mode != "🔮 수요 예측":
                c2.metric("📅 분석 기간", f"{diff_val}{'일' if view_mode=='일별 현황' else '개월'}", date_range_str, delta_color="off")
                c3.metric(avg_label, f"{int(display_df['공급가액'].sum()/diff_val if diff_val>0 else 0):,} 원")
            else:
                c2.metric("📊 기준", "최근 12개월")
                c3.metric("🏷️ 브랜드", selected_brand)
            c4.metric("📦 총 판매수량", f"{int(display_df['수량'].sum()):,} 개")
            st.markdown("---")

        # 5. 메인 분석 시각화
        common_axis = alt.Axis(labelFontSize=15, titleFontSize=17, labelAngle=0)

        if view_mode in ["월별 현황", "일별 현황"]:
            st.subheader(f"📉 {selected_product if selected_product != '전체보기' else '전체'} 판매 추이")
            t1, t2 = st.tabs(["💰 매출액 흐름", "📦 판매수량 흐름"])
            grp = '월' if view_mode == "월별 현황" else '일자'
            trend = display_df.groupby(grp)[['공급가액', '수량']].sum().reset_index()
            with t1: st.line_chart(trend.set_index(grp)['공급가액'], color="#2E86C1")
            with t2: st.line_chart(trend.set_index(grp)['수량'], color="#28B463")

            # 상세 순위 차트
            st.subheader(f"📊 상세 순위")
            tab_n, tab_a, tab_q = st.tabs(["📋 이름 순", "💰 매출액 순", "📦 박스 순"])
            group_field = '브랜드' if selected_brand == "전체보기" else '공식품목명'
            sum_df = display_df.groupby([group_field])[['공급가액', '환산수량']].sum().reset_index()
            y_ax = alt.Axis(labelLimit=500, labelFontSize=17, title='', labelPadding=20)

            with tab_n:
                st.altair_chart(alt.Chart(sum_df).mark_bar(color="#95A5A6").encode(x='공급가액:Q', y=alt.Y(f'{group_field}:N', sort='ascending', axis=y_ax)).properties(height=max(400, len(sum_df)*45)), use_container_width=True)
            with tab_a:
                st.altair_chart(alt.Chart(sum_df).mark_bar(color="#E74C3C").encode(x='공급가액:Q', y=alt.Y(f'{group_field}:N', sort='-x', axis=y_ax)).properties(height=max(400, len(sum_df)*45)), use_container_width=True)
            with tab_q:
                st.altair_chart(alt.Chart(sum_df).mark_bar(color="#F39C12").encode(x='환산수량:Q', y=alt.Y(f'{group_field}:N', sort='-x', axis=y_ax)).properties(height=max(400, len(sum_df)*45)), use_container_width=True)

        elif view_mode == "🔮 수요 예측":
            st.subheader("🔮 향후 3개월 수요 예측 분석")
            m_data = filtered_df.groupby('월_dt')['수량'].sum().reset_index().set_index('월_dt').asfreq('MS').fillna(0)
            
            if len(m_data) < 12:
                st.warning("12개월 이상의 데이터가 필요합니다.")
            else:
                seasonal_idx = filtered_df.groupby(filtered_df['일자'].dt.month)['수량'].sum() / (filtered_df.groupby(filtered_df['일자'].dt.month)['수량'].sum().mean())
                recent_avg = m_data['수량'].tail(3).mean()
                cur_start = datetime.datetime.now().replace(day=1)
                forecast_res = []
                for i in range(1, 4):
                    t_date = cur_start + relativedelta(months=i)
                    forecast_res.append({'월_dt': t_date, '예측수량': recent_avg * seasonal_idx.get(t_date.month, 1.0)})
                f_df = pd.DataFrame(forecast_res)
                
                comb = pd.concat([m_data.tail(12).reset_index().rename(columns={'수량':'값','월_dt':'날'}), f_df.rename(columns={'예측수량':'값','월_dt':'날'})])
                st.altair_chart(alt.Chart(comb).mark_line(point=True).encode(x=alt.X('날:T', axis=alt.Axis(format='%y년 %m월')), y='값:Q').properties(height=350), use_container_width=True)

                st.markdown("### 📋 월별 예상 수요 요약")
                cols = st.columns(3)
                b_unit = filtered_df['박스입수'].iloc[0] if selected_product != "전체보기" else filtered_df['박스입수'].mean()

                for i, row in enumerate(f_df.itertuples()):
                    with cols[i]:
                        main_v = f"{row.예측수량/b_unit:.1f} 박스" if b_unit > 1 else f"{int(row.예측수량):,} 개"
                        sub_v = f"낱개: {int(row.예측수량):,} 개" if b_unit > 1 else ""
                        st.metric(f"{row.월_dt.strftime('%m월')}", main_v)
                        if sub_v: st.caption(sub_v)
                
                total_f = sum(f_df['예측수량'])
                total_box_str = f"{total_f/b_unit:.1f} 박스" if b_unit > 1 else f"{int(total_f):,} 개"
                st.success(f"✅ 3개월 총 예상 필요량: 약 {total_box_str} ({int(total_f):,} 개)")

    except Exception as e:
        st.error(f"오류 발생: {e}")
