import streamlit as st
import pandas as pd
import numpy as np
import datetime
from dateutil.relativedelta import relativedelta
import altair as alt
import os
import holidays


def run(load_data_func):
    
    try:
        with open("sales_trend.css", "r", encoding="utf-8") as f:
            st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)
    except FileNotFoundError:
        pass

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
        brand_list = ["전체보기"] + sorted(list(df_sales['브랜드'].unique()))
        selected_brand = st.sidebar.selectbox("브랜드 선택", brand_list)
        
        prod_df = df_sales if selected_brand == "전체보기" else df_sales[df_sales['브랜드'] == selected_brand]
        product_list = ["전체보기"] + sorted(list(prod_df['공식품목명'].unique()))
        selected_product = st.sidebar.selectbox("품목 선택", product_list)
        
        st.sidebar.markdown("---")

        view_mode = st.sidebar.radio("분석 모드",["월별 현황", "일별 현황", "수요 예측"], index=0)

        # 공통 필터 적용
        filtered_df = df_sales.copy()
        if selected_brand != "전체보기":
            filtered_df = filtered_df[filtered_df['브랜드'] == selected_brand]
        if selected_product != "전체보기":
            filtered_df = filtered_df[filtered_df['공식품목명'] == selected_product]

        # 🚀 [복구 완료] 3. 모드별 날짜 세팅 및 필터링
        today = datetime.date.today()
        if view_mode == "일별 현황":
            if "trend_start_date" not in st.session_state: 
                st.session_state.trend_start_date = today - relativedelta(months=3)
            
            start_date = st.sidebar.date_input("시작 일", key="trend_start_date", format="YYYY/MM/DD")
            end_date = st.sidebar.date_input("종료 일", value=today, format="YYYY/MM/DD")
            
            mask = (filtered_df['일자'].dt.date >= start_date) & (filtered_df['일자'].dt.date <= end_date)
            display_df = filtered_df.loc[mask].copy()
            
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
        
        else: # 수요 예측
            display_df = filtered_df
            diff_val = 0

        if display_df.empty:
            st.warning("선택하신 조건에 데이터가 없습니다.")
            return

        
        # ==========================================
        # 🚀 [초소형 + 공휴일 완벽 제외] 최근 1년 데이터 누락 점검기
        # ==========================================
        check_end = datetime.date.today() - datetime.timedelta(days=2) # 크롤링 D-2 기준
        check_start = check_end - datetime.timedelta(days=365)         # 365일 검사
        
        # 1. 1차 필터: 주말(토,일)을 제외한 평일 달력 생성
        business_days = pd.bdate_range(start=check_start, end=check_end).date
        
        # 2. 엑셀에 실제로 존재하는 날짜들
        mask_recent = (df_sales_raw['일자'].dt.date >= check_start) & (df_sales_raw['일자'].dt.date <= check_end)
        actual_dates = df_sales_raw[mask_recent]['일자'].dt.date.unique()
        
        # 3. 1차 누락일 계산 (평일인데 엑셀에 없는 날)
        missing_dates_raw = set(business_days) - set(actual_dates)
        
        # 🚀 4. 2차 필터: 대한민국 공휴일 및 대체휴일 완벽 제외 마법!
        # 검사하는 기간의 연도(예: 2025, 2026)를 파악해서 해당 연도의 한국 달력을 가져옵니다.
        kr_holidays = holidays.KR(years=range(check_start.year, check_end.year + 1))
        
        # 1차 누락일 중에서 "공휴일 달력에 없는 진짜 평일"만 최종 누락일로 확정합니다.
        missing_dates = sorted([d for d in missing_dates_raw if d not in kr_holidays])
        
        
        # --- (여기서부터는 화면에 그리는 HTML 코드 동일) ---
        check_html = "<hr style='margin: 15px 0px 10px 0px; border-top: 1px solid #ddd;'>"
        check_html += "<div style='font-size: 0.85rem; line-height: 1.5; color: #666;'>"
        check_html += "<strong style='color: #2C3E50;'>🚨 데이터 점검 (최근 1년)</strong><br>"
        
        if missing_dates:
            check_html += f"<span style='color: #E74C3C; font-weight: 600;'>⚠️ 평일 데이터 누락 ({len(missing_dates)}일)</span><br>"
            check_html += "<div style='max-height: 120px; overflow-y: auto; margin-top: 5px; padding-right: 5px; border-left: 2px solid #E74C3C;'>"
            weekdays_kr = ["월", "화", "수", "목", "금", "토", "일"]
            for md in missing_dates:
                check_html += f"<span style='margin-left: 8px; font-size: 0.8rem;'>- {md.strftime('%y/%m/%d')} ({weekdays_kr[md.weekday()]})</span><br>"
            check_html += "</div>"
        else:
            check_html += "<span style='color: #27AE60; font-weight: 600;'>✅ 1년간 누락 없음 완벽!</span>"
            
        check_html += "</div>"
        
        st.sidebar.markdown(check_html, unsafe_allow_html=True)
        # ==========================================

        # 4. KPI 상단 바 (🚀 display_df 기반으로 계산)
        total_amt = display_df['공급가액'].sum()
        total_qty = display_df['수량'].sum()
        
        # 🚀 '만 원' 단위 환산
        total_amt_man = total_amt / 10000
        
        c1, c2, c3, c4 = st.columns(4)
        
        if view_mode == "수요 예측":
            # [순서 변경] 1. 기간(기준) -> 2. 총 판매액 -> 3. 브랜드 -> 4. 총 수량
            c1.metric("📊 기준", "최근 12개월")
            # delta 옵션에 실제 금액을 넣고 delta_color="off"를 주면 날짜처럼 밑에 작게 회색으로 표시됩니다!
            c2.metric("💰 총 판매액", f"{int(total_amt_man):,}만 원", f"실제: {int(total_amt):,} 원", delta_color="off")
            c3.metric("🏷️ 브랜드", selected_brand)
        else:
            avg_amt = total_amt / diff_val if diff_val > 0 else 0
            avg_amt_man = avg_amt / 10000
            
            # [순서 변경] 1. 분석 기간 -> 2. 총 판매액 -> 3. 평균 판매액 -> 4. 총 수량
            c1.metric("📅 분석 기간", f"{diff_val}{'일' if view_mode=='일별 현황' else '개월'}", date_range_str, delta_color="off")
            c2.metric("💰 총 판매액", f"{int(total_amt_man):,}만 원", f"실제: {int(total_amt):,} 원", delta_color="off")
            c3.metric(avg_label, f"{int(avg_amt_man):,}만 원", f"실제: {int(avg_amt):,} 원", delta_color="off")
            
        c4.metric("📦 총 수량", f"{int(total_qty):,} 개")
        st.markdown("---")

        # 5. 분석 모드별 시각화 (🚀 display_df 기반으로 시각화)
        common_axis = alt.Axis(labelFontSize=14, titleFontSize=16, labelAngle=0)

        if view_mode in ["월별 현황", "일별 현황"]:
            st.subheader(f"📉 {selected_product if selected_product != '전체보기' else '전체'} 판매 추이")
            t_line1, t_line2 = st.tabs(["💰 매출액 흐름", "📦 판매수량 흐름"])
            grp = '월' if view_mode == "월별 현황" else '일자'
            
            trend = display_df.groupby(grp)[['공급가액', '수량']].sum().reset_index()
            with t_line1: st.line_chart(trend.set_index(grp)['공급가액'], color="#2E86C1")
            with t_line2: st.line_chart(trend.set_index(grp)['수량'], color="#28B463")

            group_field = '브랜드' if selected_brand == "전체보기" else '공식품목명'
            st.subheader(f"📊 {selected_brand if selected_brand != '전체보기' else '전체'} 순위 현황")
            tab_n, tab_a, tab_q = st.tabs(["📋 이름 순", "💰 매출액 순", "📦 박스 순"])
            
            sum_df = display_df.groupby([group_field])[['공급가액', '환산수량']].sum().reset_index()
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

        elif view_mode == "수요 예측":
            st.subheader("향후 3개월 수요 예측 분석")
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
