import streamlit as st
import pandas as pd
import datetime
from dateutil.relativedelta import relativedelta
import altair as alt
import holidays

def run(load_data_func):
    
    try:
        with open("sales_trend.css", "r", encoding="utf-8") as f:
            st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)
    except FileNotFoundError:
        pass

    st.title("🤝 거래처별 판매 현황")

    try:
        # 1. 데이터 로드 및 마스터 결합
        df_trade_raw = load_data_func("trade_record")
        df_item = load_data_func("ecount_item_data")
        
        df_trade_raw.columns = ['일자', '거래처명', '품목코드', '품목명', '수량', '공급가액']
        df_trade_raw['일자'] = pd.to_datetime(df_trade_raw['일자'], errors='coerce')
        df_trade_raw['수량'] = pd.to_numeric(df_trade_raw['수량'].astype(str).str.replace(',', ''), errors='coerce').fillna(0)
        df_trade_raw['공급가액'] = pd.to_numeric(df_trade_raw['공급가액'].astype(str).str.replace(',', ''), errors='coerce').fillna(0)
        df_trade_raw = df_trade_raw.dropna(subset=['일자'])
        
        df_item_master = df_item[['품목코드', '이름', '브랜드']].copy()
        df_item_master.rename(columns={'이름': '공식품목명'}, inplace=True)
        
        df_trade = pd.merge(df_trade_raw, df_item_master, on='품목코드', how='left')
        
        df_trade['브랜드'] = df_trade['브랜드'].fillna('기타(미지정)')
        df_trade['공식품목명'] = df_trade['공식품목명'].fillna(df_trade['품목명'])
        
        df_trade['월_dt'] = df_trade['일자'].dt.to_period('M').dt.to_timestamp()
        df_trade['월'] = df_trade['일자'].dt.strftime('%Y년 %m월')

        # 2. 사이드바 필터
        
        trader_list = sorted(list(df_trade['거래처명'].dropna().unique()))
        selected_traders = st.sidebar.multiselect(
            "거래처 선택", 
            options=trader_list,
            default=[],
            placeholder="비워두면 전체 거래처 조회"
        )
        
        temp_df = df_trade if not selected_traders else df_trade[df_trade['거래처명'].isin(selected_traders)]
        
        brand_list = ["전체보기"] + sorted(list(temp_df['브랜드'].dropna().unique()))
        selected_brand = st.sidebar.selectbox("브랜드 선택", brand_list)

        view_mode = st.sidebar.radio("분석 모드", ["월별 현황", "일별 현황"], index=0)

        # 공통 필터 적용
        filtered_df = df_trade.copy()
        if selected_traders:
            filtered_df = filtered_df[filtered_df['거래처명'].isin(selected_traders)]
        if selected_brand != "전체보기":
            filtered_df = filtered_df[filtered_df['브랜드'] == selected_brand]

        group_field = '브랜드' if selected_brand == "전체보기" else '공식품목명'

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

        # 5. 메인 시각화 (거래액 추이)
        common_axis = alt.Axis(labelFontSize=14, titleFontSize=16, labelAngle=0)
        grp = '월' if view_mode == "월별 현황" else '일자'
        
        trader_title = "전체 거래처" if not selected_traders else ", ".join(selected_traders)
        st.subheader(f"📉 {trader_title} 거래액 추이")
        
        color_encoding = alt.Color('거래처명:N', legend=alt.Legend(title="거래처")) if selected_traders else alt.value("#2E86C1")
        
        if selected_traders:
            trend = display_df.groupby([grp, '거래처명'])['공급가액'].sum().reset_index()
        else:
            trend = display_df.groupby([grp])['공급가액'].sum().reset_index()
            trend['거래처명'] = '전체'

        if view_mode == "일별 현황":
            x_min, x_max = display_df['일자'].min(), display_df['일자'].max()
            diff_days = (x_max - x_min).days
            axis_options = {'format': '%m/%d', 'labelFontSize': 14}
            if 0 < diff_days <= 14: axis_options['tickCount'] = diff_days
            common_x = alt.X('일자:T', title='', axis=alt.Axis(**axis_options))
            
            line_chart = alt.Chart(trend).mark_line(point=True).encode(
                x=common_x, y=alt.Y('공급가액:Q', title='금액(원)'), color=color_encoding, tooltip=[grp, '거래처명', '공급가액']
            ).properties(height=350)
            st.altair_chart(line_chart, use_container_width=True)
        else:
            line_chart = alt.Chart(trend).mark_line(point=True).encode(
                x=alt.X(f'{grp}:N', title='', axis=alt.Axis(labelAngle=0, labelFontSize=14)), 
                y=alt.Y('공급가액:Q', title='금액(원)'), color=color_encoding, tooltip=[grp, '거래처명', '공급가액']
            ).properties(height=350)
            st.altair_chart(line_chart, use_container_width=True)

        # ==========================================
        # 🚀 [디자인 튜닝 완료] 6. 관점 전환이 가능한 교차 랭킹 차트
        # 막대 두께를 고정하고, 순위에 따라 다채로운 그라데이션 색상을 적용합니다.
        # ==========================================
        st.markdown("---")
        
        # 스위치(라디오 버튼) 추가: 가로로 예쁘게 배치
        rank_mode = st.radio(
            "그래프 기준", 
            ["제품", "거래처"], 
            horizontal=True
        )
        
        # 사용자가 선택한 모드에 따라 차트의 축(Y)과 제목이 즉시 바뀝니다!
        if "품목" in rank_mode:
            rank_field = group_field # 전체보기일 땐 브랜드명, 브랜드를 선택했을 땐 공식품목명
            st.subheader(f"📊 {trader_title} 내 [{rank_field}] 매출 순위 (TOP 15)")
        else:
            rank_field = '거래처명'
            brand_title = "전체 품목" if selected_brand == "전체보기" else selected_brand
            st.subheader(f"📊 [{brand_title}] 매출 견인 거래처 순위 (TOP 15)")
            
        # 선택된 축(rank_field) 기준으로 데이터를 합산
        sum_df = display_df.groupby([rank_field])[['공급가액', '수량']].sum().reset_index()
        sum_df = sum_df.sort_values(by='공급가액', ascending=False).head(15) 
        
        y_ax = alt.Axis(labelLimit=500, labelFontSize=14, title='', labelPadding=10)
        chart_h = max(300, len(sum_df) * 45)

        # 🚀 [디자인 핵심] 막대 차트 정의
        # 🚀 [디자인 핵심] 막대 차트 정의
        rank_chart = alt.Chart(sum_df).mark_bar(
            size=25,            # 막대 두께 25로 고정 (슬림하게 유지)
            cornerRadius=5,     # 막대 끝 둥글게
            color="#2E86C1",    # 🌟 그라데이션 제거! 모든 막대를 또렷한 파란색으로 통일합니다. (빨간색을 원하시면 "#E74C3C" 로 변경)
            opacity=0.9
        ).encode(
            x=alt.X('공급가액:Q', title='총 거래액 (원)'), 
            y=alt.Y(f'{rank_field}:N', sort='-x', axis=y_ax),
            tooltip=[rank_field, alt.Tooltip('공급가액', format=','), alt.Tooltip('수량', format=',')]
        )
        
        # [보너스 디자인] 막대 끝에 실제 수량 숫자를 띄워 가독성 업그레이드!
        text_label = rank_chart.mark_text(
            align='left', 
            dx=5, 
            fontSize=13, 
            fontWeight='bold',
            color='#555'
        ).encode(
            text=alt.Text('공급가액:Q', format=',')
        )

        # 차트와 숫자 라벨을 합쳐서 그립니다.
        st.altair_chart((rank_chart + text_label).properties(height=chart_h), use_container_width=True)
        # ==========================================
    
    except Exception as e:
        st.error(f"오류 발생: {e}")
