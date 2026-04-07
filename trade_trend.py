import streamlit as st
import pandas as pd
import datetime
from dateutil.relativedelta import relativedelta
import altair as alt
import holidays

def run(load_data_func):
    
    # 🚀 기존 판매 현황 CSS를 그대로 공유하여 톤앤매너 유지!
    try:
        with open("sales_trend.css", "r", encoding="utf-8") as f:
            st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)
    except FileNotFoundError:
        pass

    st.title("🤝 거래처별 판매 현황")

    try:
        # 1. 데이터 로드
        df_trade_raw = load_data_func("trade_record")
        
        # 컬럼명 맞추기 (일자, 거래처명, 품목코드, 품목명, 수량, 공급가액)
        df_trade_raw.columns = ['일자', '거래처명', '품목코드', '품목명', '수량', '공급가액']
        
        # 데이터 전처리
        df_trade_raw['일자'] = pd.to_datetime(df_trade_raw['일자'], errors='coerce')
        df_trade_raw['수량'] = pd.to_numeric(df_trade_raw['수량'].astype(str).str.replace(',', ''), errors='coerce').fillna(0)
        df_trade_raw['공급가액'] = pd.to_numeric(df_trade_raw['공급가액'].astype(str).str.replace(',', ''), errors='coerce').fillna(0)
        df_trade_raw = df_trade_raw.dropna(subset=['일자'])
        
        df_trade = df_trade_raw.copy()
        df_trade['월_dt'] = df_trade['일자'].dt.to_period('M').dt.to_timestamp()
        df_trade['월'] = df_trade['일자'].dt.strftime('%Y년 %m월')

        # 2. 사이드바 필터
        st.sidebar.markdown("### 🔍 조회 조건")
        trader_list = ["전체보기"] + sorted(list(df_trade['거래처명'].dropna().unique()))
        selected_trader = st.sidebar.selectbox("1. 거래처 선택", trader_list)
        
        # 🚀 선택한 거래처가 사간 품목만 추려서 2차 필터 구성
        prod_df = df_trade if selected_trader == "전체보기" else df_trade[df_trade['거래처명'] == selected_trader]
        product_list = ["전체보기"] + sorted(list(prod_df['품목명'].dropna().unique()))
        selected_product = st.sidebar.selectbox("2. 품목 선택 (옵션)", product_list)

        st.sidebar.markdown("---")

        view_mode = st.sidebar.radio("3. 분석 모드", ["월별 현황", "일별 현황"], index=0)

        # 공통 필터 적용
        filtered_df = df_trade.copy()
        if selected_trader != "전체보기":
            filtered_df = filtered_df[filtered_df['거래처명'] == selected_trader]
        if selected_product != "전체보기":
            filtered_df = filtered_df[filtered_df['품목명'] == selected_product]

        # 3. 모드별 날짜 세팅 및 필터링
        today = datetime.date.today()
        if view_mode == "일별 현황":
            if "trade_start_date" not in st.session_state: 
                st.session_state.trade_start_date = today - relativedelta(months=1)
            
            start_date = st.sidebar.date_input("시작 일", key="trade_start_date", format="YYYY/MM/DD")
            end_date = st.sidebar.date_input("종료 일", value=today, format="YYYY/MM/DD")
            
            mask = (filtered_df['일자'].dt.date >= start_date) & (filtered_df['일자'].dt.date <= end_date)
            display_df = filtered_df.loc[mask].copy()
            
            date_range_str = f"{start_date.strftime('%Y년 %m월 %d일')} ~ {end_date.strftime('%Y년 %m월 %d일')}"
            diff_val = (end_date - start_date).days + 1
            avg_label = "💸 일평균 거래액"

        else: # 월별 현황
            month_list = sorted(list(df_trade['월'].unique()))
            if not month_list:
                st.warning("데이터가 없습니다.")
                return
                
            start_month = st.sidebar.selectbox("시작 월", month_list, index=max(0, len(month_list)-6))
            end_month = st.sidebar.selectbox("종료 월", month_list, index=len(month_list)-1)
            
            display_df = filtered_df[(filtered_df['월'] >= start_month) & (filtered_df['월'] <= end_month)]
            
            date_range_str = f"{start_month} ~ {end_month}"
            d1, d2 = pd.to_datetime(start_month, format='%Y년 %m월'), pd.to_datetime(end_month, format='%Y년 %m월')
            diff_val = (d2.year - d1.year) * 12 + (d2.month - d1.month) + 1
            avg_label = "💸 월평균 거래액"

        if display_df.empty:
            st.warning("선택하신 조건에 데이터가 없습니다.")
            return

        # ==========================================
        # 🚀 [데이터 누락 점검기] 한국 공휴일 완벽 제외
        # ==========================================
        check_end = datetime.date.today() - datetime.timedelta(days=2) 
        check_start = check_end - datetime.timedelta(days=365)         
        
        business_days = pd.bdate_range(start=check_start, end=check_end).date
        mask_recent = (df_trade_raw['일자'].dt.date >= check_start) & (df_trade_raw['일자'].dt.date <= check_end)
        actual_dates = df_trade_raw[mask_recent]['일자'].dt.date.unique()
        
        missing_dates_raw = set(business_days) - set(actual_dates)
        kr_holidays = holidays.KR(years=range(check_start.year, check_end.year + 1))
        missing_dates = sorted([d for d in missing_dates_raw if d not in kr_holidays])
        
        check_html = "<hr style='margin: 15px 0px 10px 0px; border-top: 1px solid #ddd;'>"
        check_html += "<div style='font-size: 0.85rem; line-height: 1.5; color: #666;'>"
        check_html += "<strong style='color: #2C3E50;'>🚨 크롤링 점검 (최근 1년)</strong><br>"
        
        if missing_dates:
            check_html += f"<span style='color: #E74C3C; font-weight: 600;'>⚠️ 평일 데이터 누락 ({len(missing_dates)}일)</span><br>"
            check_html += "<div style='max-height: 120px; overflow-y: auto; margin-top: 5px; padding-right: 5px; border-left: 2px solid #E74C3C;'>"
            weekdays_kr = ["월", "화", "수", "목", "금", "토", "일"]
            for md in missing_dates:
                check_html += f"<span style='margin-left: 8px; font-size: 0.8rem;'>- {md.strftime('%y/%m/%d')} ({weekdays_kr[md.weekday()]})</span><br>"
            check_html += "</div>"
        else:
            check_html += "<span style='color: #27AE60; font-weight: 600;'>✅ 누락 없음 완벽!</span>"
            
        check_html += "</div>"
        st.sidebar.markdown(check_html, unsafe_allow_html=True)
        # ==========================================

        # 4. KPI 상단 바
        total_amt = display_df['공급가액'].sum()
        total_qty = display_df['수량'].sum()
        total_amt_man = total_amt / 10000
        
        c1, c2, c3, c4 = st.columns(4)
        avg_amt = total_amt / diff_val if diff_val > 0 else 0
        avg_amt_man = avg_amt / 10000
        
        c1.metric("📅 분석 기간", f"{diff_val}{'일' if view_mode=='일별 현황' else '개월'}", date_range_str, delta_color="off")
        c2.metric("💰 총 거래액", f"{int(total_amt_man):,}만 원", f"실제: {int(total_amt):,} 원", delta_color="off")
        c3.metric(avg_label, f"{int(avg_amt_man):,}만 원", f"실제: {int(avg_amt):,} 원", delta_color="off")
        c4.metric("📦 총 출고수량", f"{int(total_qty):,} 개")
        st.markdown("---")

        # 5. 메인 시각화
        common_axis = alt.Axis(labelFontSize=14, titleFontSize=16, labelAngle=0)
        grp = '월' if view_mode == "월별 현황" else '일자'
        
        st.subheader(f"📉 {selected_trader} 거래액 추이")
        trend = display_df.groupby(grp)['공급가액'].sum().reset_index()
        
        if view_mode == "일별 현황":
            x_min, x_max = display_df['일자'].min(), display_df['일자'].max()
            diff_days = (x_max - x_min).days
            axis_options = {'format': '%m/%d', 'labelFontSize': 14}
            if 0 < diff_days <= 14: axis_options['tickCount'] = diff_days
            common_x = alt.X('일자:T', title='', axis=alt.Axis(**axis_options))
            st.altair_chart(alt.Chart(trend).mark_line(point=True).encode(x=common_x, y=alt.Y('공급가액:Q', title='금액(원)')).properties(height=350), use_container_width=True)
        else:
            st.line_chart(trend.set_index(grp)['공급가액'], color="#2E86C1")

        # 🚀 6. 교차 분석 랭킹 (전체보기일 땐 '거래처 랭킹', 특정 거래처 선택 시 '품목 랭킹')
        group_field = '거래처명' if selected_trader == "전체보기" else '품목명'
        st.subheader(f"📊 {selected_trader} 내 {group_field} 순위 (매출액 기준)")
        
        sum_df = display_df.groupby([group_field])[['공급가액', '수량']].sum().reset_index().sort_values(by='공급가액', ascending=False).head(15) # 상위 15개만
        y_ax = alt.Axis(labelLimit=500, labelFontSize=14, title='', labelPadding=10)
        chart_h = max(300, len(sum_df) * 45)

        st.altair_chart(alt.Chart(sum_df).mark_bar(color="#E74C3C").encode(
            x=alt.X('공급가액:Q', title='총 거래액 (원)'), 
            y=alt.Y(f'{group_field}:N', sort='-x', axis=y_ax),
            tooltip=[group_field, '공급가액', '수량']
        ).properties(height=chart_h), use_container_width=True)

        # 7. 상세 데이터 표
        st.markdown("---")
        st.subheader("📋 거래처 상세 모니터링")
        
        # 피벗 테이블 생성 (가로축: 날짜, 세로축: 거래처/품목명)
        show_df = display_df.copy()
        show_df['표시값'] = show_df.apply(lambda r: f"{int(r['공급가액']):,}원 ({int(r['수량'])}개)", axis=1)
        
        pivot_col = '월' if view_mode == "월별 현황" else '일자'
        if view_mode == "일별 현황": show_df['일자'] = show_df['일자'].dt.strftime('%m/%d')
        
        pivot_df = show_df.pivot_table(
            index=['거래처명', '품목명'],
            columns=pivot_col,
            values='표시값',
            aggfunc=lambda x: ' '.join(x)
        ).reset_index()

        date_cols = sorted([col for col in pivot_df.columns if col not in ['거래처명', '품목명']], reverse=True)
        final_cols = ['거래처명', '품목명'] + date_cols
        pivot_df = pivot_df[final_cols].fillna("-")

        st.dataframe(pivot_df, use_container_width=True, hide_index=True)

    except Exception as e:
        st.error(f"오류 발생: {e}")
