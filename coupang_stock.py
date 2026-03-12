import streamlit as st
import pandas as pd
import datetime
from dateutil.relativedelta import relativedelta
import altair as alt
import os

def load_css(file_name):
    """외부 CSS 파일을 읽어와 Streamlit에 적용"""
    try:
        with open(file_name, "r", encoding="utf-8") as f:
            st.markdown(f'<style>{f.read()}</style>', unsafe_allow_html=True)
    except FileNotFoundError:
        pass # 에러 메시지 없이 넘어가거나 기본 스타일 적용

def run(load_data_func):
    # 🚀 분리된 CSS 적용
    load_css("sales_style.css")

    st.title("📦 쿠팡 재고 및 판매가 현황")
    st.markdown("매일 기록되는 쿠팡 물류 창고의 **재고 흐름**과 **판매가 변동**을 추적합니다.")

    try:
        # 1. 데이터 로드 및 전처리
        df_raw = load_data_func("coupang_stock")
        
        # 열 이름 지정 (만약 시트 첫 줄에 이미 입력하셨다면 이 과정은 안전장치가 됩니다)
        # A:일자, B:옵션ID, C:브랜드, D:품목명, E:쿠팡품목명, F:재고, G:판매가
        df_raw.columns = ['일자', '옵션ID', '브랜드', '품목명', '쿠팡품목명', '재고', '판매가']
        
        df_raw['일자'] = pd.to_datetime(df_raw['일자'], errors='coerce')
        # 콤마 제거 및 숫자로 변환
        df_raw['재고'] = pd.to_numeric(df_raw['재고'].astype(str).str.replace(',', ''), errors='coerce').fillna(0)
        df_raw['판매가'] = pd.to_numeric(df_raw['판매가'].astype(str).str.replace(',', ''), errors='coerce').fillna(0)
        
        # 날짜가 없는 빈 행 제거 및 필요한 열만 추출 (쿠팡품목명 제외)
        df = df_raw.dropna(subset=['일자'])[['일자', '옵션ID', '브랜드', '품목명', '재고', '판매가']].copy()

        # ==========================================
        # 2. 사이드바 필터 설정
        # ==========================================
        st.sidebar.markdown("### 🔍 조회 조건")
        
        # (1) 브랜드 선택
        brand_list = ["전체보기"] + sorted(list(df['브랜드'].dropna().unique()))
        selected_brand = st.sidebar.selectbox("1. 브랜드 선택", brand_list)
        
        # (2) 날짜 선택
        today = datetime.date.today()
        if "coupang_start_date" not in st.session_state: 
            st.session_state.coupang_start_date = today - relativedelta(days=14) # 기본값: 최근 2주
        
        start_date = st.sidebar.date_input("2. 시작일", key="coupang_start_date")
        end_date = st.sidebar.date_input("종료일", value=today)
        
        # (3) 조회 항목 선택 (라디오 버튼)
        st.sidebar.markdown("---")
        view_target = st.sidebar.radio("3. 조회 항목", ["📦 재고량 추이", "💰 판매가 변동", "📊 모두 보기"], index=2)

        # ==========================================
        # 3. 데이터 필터링 적용
        # ==========================================
        filtered_df = df.copy()
        if selected_brand != "전체보기":
            filtered_df = filtered_df[filtered_df['브랜드'] == selected_brand]
            
        mask = (filtered_df['일자'].dt.date >= start_date) & (filtered_df['일자'].dt.date <= end_date)
        display_df = filtered_df.loc[mask].copy()

        if display_df.empty:
            st.warning("선택하신 조건에 데이터가 없습니다.")
            return

        # ==========================================
        # 4. 상단 요약 KPI (가장 최근 날짜 기준)
        # ==========================================
        latest_date = display_df['일자'].max()
        latest_df = display_df[display_df['일자'] == latest_date]
        
        total_stock = latest_df['재고'].sum()
        avg_price = latest_df['판매가'].mean() if not latest_df.empty else 0
        item_count = len(latest_df['품목명'].unique())
        
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("📅 최근 업데이트", latest_date.strftime('%Y년 %m월 %d일'))
        c2.metric("📦 현재 총 재고", f"{int(total_stock):,} 개")
        c3.metric("🛒 운영 품목", f"{item_count} 종")
        c4.metric("💸 평균 판매가", f"{int(avg_price):,} 원")
        st.markdown("---")

        # ==========================================
        # 5. 메인 시각화 (Altair)
        # ==========================================
        common_axis = alt.Axis(labelFontSize=14, titleFontSize=16, labelAngle=0)
        legend_config = alt.Legend(titleFontSize=15, labelFontSize=14, orient='bottom')

        # 📦 재고량 차트
        if view_target in ["📦 재고량 추이", "📊 모두 보기"]:
            st.subheader(f"📦 {selected_brand if selected_brand != '전체보기' else '전체'} 재고량 변동 흐름")
            
            # 품목별 선 그래프
            stock_chart = alt.Chart(display_df).mark_line(point=True).encode(
                x=alt.X('일자:T', title='', axis=alt.Axis(format='%m월 %d일', labelFontSize=14)),
                y=alt.Y('재고:Q', title='재고 수량 (개)', axis=common_axis),
                color=alt.Color('품목명:N', legend=legend_config, title='품목명'),
                tooltip=['일자:T', '브랜드', '품목명', '재고']
            ).properties(height=400)
            
            st.altair_chart(stock_chart, use_container_width=True)

        st.markdown("<br>", unsafe_allow_html=True) # 차트 사이 여백

        # 💰 판매가 차트
        if view_target in ["💰 판매가 변동", "📊 모두 보기"]:
            st.subheader(f"💰 {selected_brand if selected_brand != '전체보기' else '전체'} 판매가 변동 흐름")
            st.caption("※ 쿠팡의 잦은 가격 변동(바이박스 경쟁 등)을 추적합니다.")
            
            price_chart = alt.Chart(display_df).mark_line(point=True).encode(
                x=alt.X('일자:T', title='', axis=alt.Axis(format='%m월 %d일', labelFontSize=14)),
                # y축은 0부터 시작하지 않고 가격 변동폭이 잘 보이도록 zero=False 설정
                y=alt.Y('판매가:Q', title='판매가 (원)', axis=common_axis, scale=alt.Scale(zero=False)),
                color=alt.Color('품목명:N', legend=legend_config, title='품목명'),
                tooltip=['일자:T', '브랜드', '품목명', '판매가']
            ).properties(height=400)
            
            st.altair_chart(price_chart, use_container_width=True)

        # ==========================================
        # 6. 상세 데이터 표
        # ==========================================
        with st.expander("🔍 쿠팡 상세 기록 보기"):
            show_df = display_df[['일자', '브랜드', '품목명', '옵션ID', '재고', '판매가']].copy()
            show_df['일자'] = show_df['일자'].dt.strftime('%Y년 %m월 %d일')
            # 천 단위 콤마 포맷팅
            show_df['재고'] = show_df['재고'].apply(lambda x: f"{int(x):,}")
            show_df['판매가'] = show_df['판매가'].apply(lambda x: f"{int(x):,} 원")
            
            st.dataframe(show_df.sort_values(by=['일자', '품목명'], ascending=[False, True]), use_container_width=True)

    except Exception as e:
        st.error(f"오류 발생: {e}")
