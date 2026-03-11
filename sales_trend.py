import streamlit as st
import pandas as pd
import datetime

def run(load_data_func):
    st.title("📈 판매 현황 및 트렌드 분석")
    st.markdown("과거부터 현재까지의 판매 흐름을 한눈에 파악합니다.")

    try:
        # 1. 데이터 불러오기
        df_sales = load_data_func("sales_record")
        
        # 데이터 전처리 (일자를 날짜 형식으로, 수량을 숫자로)
        df_sales['일자'] = pd.to_datetime(df_sales['일자'], errors='coerce')
        df_sales['수량'] = df_sales['수량'].astype(str).str.replace(',', '')
        df_sales['수량'] = pd.to_numeric(df_sales['수량'], errors='coerce').fillna(0)
        
        # 빈 날짜나 수량이 0인 행 제거
        df_sales = df_sales.dropna(subset=['일자'])
        df_sales = df_sales[df_sales['수량'] > 0] # 반품(마이너스) 제외하고 순수 판매만 우선 보기

        if df_sales.empty:
            st.warning("표시할 판매 데이터가 없습니다.")
            return

        # 2. 사이드바: 기간 필터 설정
        st.sidebar.markdown("### 📅 검색 기간 설정")
        min_date = df_sales['일자'].min().date()
        max_date = df_sales['일자'].max().date()

        # 기본값: 최근 3개월 (또는 데이터가 짧으면 전체 기간)
        default_start = max(min_date, max_date - datetime.timedelta(days=90))
        
        start_date, end_date = st.sidebar.date_input(
            "기간을 선택하세요",
            [default_start, max_date],
            min_value=min_date,
            max_value=max_date
        )

        # 선택한 기간으로 데이터 자르기
        mask = (df_sales['일자'].dt.date >= start_date) & (df_sales['일자'].dt.date <= end_date)
        filtered_df = df_sales.loc[mask]

        # 3. 화면 상단 요약 요약 (KPI)
        total_qty = filtered_df['수량'].sum()
        total_days = (end_date - start_date).days + 1
        daily_avg = total_qty / total_days if total_days > 0 else 0

        col1, col2, col3 = st.columns(3)
        col1.metric(label="총 판매 수량", value=f"{int(total_qty):,} 개")
        col2.metric(label="분석 기간", value=f"{total_days} 일")
        col3.metric(label="일평균 판매량", value=f"{int(daily_avg):,} 개")
        
        st.markdown("---")

        # ==========================================
        # 📊 [차트 1] 일별 판매 트렌드 (꺾은선 그래프)
        # ==========================================
        st.subheader("📉 일별 총 판매 추이")
        # 날짜별로 수량 합치기
        daily_trend = filtered_df.groupby('일자')['수량'].sum().reset_index()
        # 스트림릿 내장 라인 차트를 위해 인덱스를 날짜로 설정
        daily_trend.set_index('일자', inplace=True)
        
        # 차트 그리기
        st.line_chart(daily_trend)

        # ==========================================
        # 📊 [차트 2] 판매량 TOP 10 품목 (막대 그래프)
        # ==========================================
        st.subheader("🏆 베스트셀러 TOP 10")
        # 품목명별로 수량 합치기 후 내림차순 정렬, 상위 10개만 추출
        top_items = filtered_df.groupby('품목명')['수량'].sum().sort_values(ascending=False).head(10)
        
        # 차트 그리기
        st.bar_chart(top_items)

        # ==========================================
        # 📋 데이터 원본 확인 표
        # ==========================================
        with st.expander("🔍 선택된 기간의 원본 데이터 보기"):
            st.dataframe(filtered_df.sort_values(by='일자', ascending=False), use_container_width=True)

    except Exception as e:
        st.error(f"데이터 분석 중 오류가 발생했습니다: {e}")
