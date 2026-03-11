import streamlit as st
import pandas as pd
import numpy as np
import datetime
from dateutil.relativedelta import relativedelta
import altair as alt

def run(load_data_func):
    # 🚀 [스타일 최종 보정] 레이아웃 깨짐 방지 및 글자 크기 극대화
    st.markdown("""
        <style>
            /* 전체 본문 폰트 크기 상향 */
            .main .block-container { font-size: 1.1rem; }
            
            /* Metric(지표) 상단 제목 (날짜, 분석항목) */
            [data-testid="stMetricLabel"] > div { 
                font-size: 1.6rem !important; 
                font-weight: 800 !important; 
                color: #1E1E1E !important; 
            }
            /* Metric 메인 수치 (박스 수량 및 금액) */
            [data-testid="stMetricValue"] > div { 
                font-size: 2.8rem !important; 
                font-weight: 700 !important;
            }
            /* Metric 하단 캡션 (낱개 수량 설명 등) */
            .stCaption, [data-testid="stCaptionContainer"] { 
                font-size: 1.6rem !important; 
                line-height: 1.6 !important; 
                color: #007BFF !important; 
                font-weight: 700 !important;
                background-color: #f0f8ff;
                padding: 8px 12px;
                border-radius: 8px;
                border: 1px solid #d1e9ff;
                display: inline-block;
                margin-top: 5px;
            }
            /* 탭 메뉴 글자 크기 */
            button[data-baseweb="tab"] p { font-size: 1.3rem !important; font-weight: 600 !important; }
            /* 경고/성공 메시지 */
            .stAlert p { font-size: 1.5rem !important; font-weight: 700 !important; }
        </style>
    """, unsafe_allow_html=True)

    st.title("📈 판매 현황 및 수요 예측")

    try:
        # 1. 데이터 로드 및 마스터 결합
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

        # 2. 사이드바 필터 (브랜드-품목 연동)
        st.sidebar.markdown("### 🔍 조회 조건")
        brand_list = ["전체보기"] + sorted(list(df_sales['브랜드'].unique()))
        selected_brand = st.sidebar.selectbox("1. 브랜드 선택", brand_list)
        
        prod_df = df_sales if selected_brand == "전체보기" else df_sales[df_sales['브랜드'] == selected_brand]
        product_list = ["전체보기"] + sorted(list(prod_df['공식품목명'].unique()))
        selected_product = st.sidebar.selectbox("2. 품목 선택", product_list)
        
        st.sidebar.markdown("---")
        view_mode = st.sidebar.radio("3. 분석 모드", ["월별 현황", "일별 현황", "🔮 수요 예측"], index=0)

        # 공통 필터 적용
        filtered_df = df_sales.copy()
        if selected_brand != "전체보기":
            filtered_df = filtered_df[filtered_df['브랜드'] == selected_brand]
        if selected_product != "전체보기":
            filtered_df = filtered_df[filtered_df['공식품목명'] == selected_product]

        # 3. KPI 상단 바
        total_amt = filtered_df['공급가액'].sum()
        total_qty = filtered_df['수량'].sum()
        
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("💰 총 판매액", f"{int(total_amt):,} 원")
        if view_mode == "🔮 수요 예측":
            c2.metric("📊 기준", "최근 12개월")
            c3.metric("🏷️ 브랜드", selected_brand)
        else:
            c2.metric("📦 총 수량", f"{int(total_qty):,} 개")
            c3.metric("🛒 품목 수", f"{len(filtered_df['품목코드'].unique())} 종")
        c4.metric("📈 분석 모드", view_mode)
        st.markdown("---")

        # 4. 분석 모드별 시각화
        common_axis = alt.Axis(labelFontSize=14, titleFontSize=16, labelAngle=0)

        if view_mode in ["월별 현황", "일별 현황"]:
            # (1) 추이 차트 탭 복구
            st.subheader(f"📉 {selected_product if selected_product != '전체보기' else '전체'} 판매 추이")
            t_line1, t_line2 = st.tabs(["💰 매출액 흐름", "📦 판매수량 흐름"])
            grp = '월' if view_mode == "월별 현황" else '일자'
            trend = filtered_df.groupby(grp)[['공급가액', '수량']].sum().reset_index()
            with t_line1: st.line_chart(trend.set_index(grp)['공급가액'], color="#2E86C1")
            with t_line2: st.line_chart(trend.set_index(grp)['수량'], color="#28B463")

            # (2) 상세 순위 3개 탭 복구 (이름순, 매출순, 박스순)
            group_field = '브랜드' if selected_brand == "전체보기" else '공식품목명'
            st.subheader(f"📊 {selected_brand if selected_brand != '전체보기' else '전체'} 순위 현황")
            tab_n, tab_a, tab_q = st.tabs(["📋 이름 순", "💰 매출액 순", "📦 박스 순"])
            
            sum_df = filtered_df.groupby([group_field])[['공급가액', '환산수량']].sum().reset_index()
            y_ax = alt.Axis(labelLimit=500, labelFontSize=16, title='', labelPadding=20)
            chart_h = max(400, len(sum_df) * 45)

            with tab_n:
                st.altair_chart(alt.Chart(sum_df).mark_bar(color="#95A5A6").encode(
                    x='공급가액:Q', y=alt.Y(f'{group_field}:N', sort='ascending', axis=y_ax)
                ).properties(height=chart_h), use_container_width=True)
            with tab_a:
                st.altair_chart(alt.Chart(sum_df).mark_bar(color="#E74C3C").encode(
                    x='공급가액:Q', y=alt.Y(f'{group_field}:N', sort='-x', axis=y_ax)
                ).properties(height=chart_h), use_container_width=True)
            with tab_q:
                st.altair_chart(alt.Chart(sum_df).mark_bar(color="#F39C12").encode(
                    x='환산수량:Q', y=alt.Y(f'{group_field}:N', sort='-x', axis=y_ax)
                ).properties(height=chart_h), use_container_width=True)

        elif view_mode == "🔮 수요 예측":
            st.subheader("🔮 향후 3개월 수요 예측 분석")
            m_data = filtered_df.groupby('월_dt')['수량'].sum().reset_index().set_index('월_dt').asfreq('MS').fillna(0)
            
            if len(m_data) < 12:
                st.warning("12개월 이상의 데이터가 필요합니다.")
            else:
                seasonal_idx = filtered_df.groupby(filtered_df['일자'].dt.month)['수량'].sum() / (filtered_df.groupby(filtered_df['일자'].dt.month)['수량'].sum().mean())
                recent_avg = m_data['수량'].tail(3).mean()
                cur_start = datetime.datetime.now().replace(day=1)
                
                f_res = []
                for i in range(1, 4):
                    t_date = cur_start + relativedelta(months=i)
                    f_res.append({'월_dt': t_date, '예측수량': recent_avg * seasonal_idx.get(t_date.month, 1.0)})
                f_df = pd.DataFrame(f_res)

                # 예측 그래프
                comb = pd.concat([m_data.tail(12).reset_index().rename(columns={'수량':'값','월_dt':'날'}), f_df.rename(columns={'예측수량':'값','월_dt':'날'})])
                st.altair_chart(alt.Chart(comb).mark_line(point=True).encode(x=alt.X('날:T', axis=alt.Axis(format='%y년 %m월')), y='값:Q').properties(height=350), use_container_width=True)

                st.markdown("### 📋 월별 예상 수요 요약")
                cols = st.columns(3)
                b_unit = filtered_df['박스입수'].iloc[0] if selected_product != "전체보기" else filtered_df['박스입수'].mean()

                for i, row in enumerate(f_df.itertuples()):
                    with cols[i]:
                        # 🚀 [핵심] 박스 수량을 메인으로, 개수를 보조로 표시
                        main_v = f"{row.예측수량/b_unit:.1f} 박스" if b_unit > 1 else f"{int(row.예측수량):,} 개"
                        sub_v = f"낱개: {int(row.예측수량):,} 개" if b_unit > 1 else ""
                        st.metric(f"{row.월_dt.strftime('%m월')}", main_v)
                        if sub_v: st.caption(sub_v)
                
                total_f = sum(f_df['예측수량'])
                total_box_str = f"{total_f/b_unit:.1f} 박스" if b_unit > 1 else f"{int(total_f):,} 개"
                st.success(f"✅ 3개월 총 예상 필요량: 약 {total_box_str} ({int(total_f):,} 개)")

    except Exception as e:
        st.error(f"오류 발생: {e}")
