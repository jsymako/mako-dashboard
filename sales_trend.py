import streamlit as st
import pandas as pd
import datetime

def run(load_data_func):
    st.title("📈 판매 현황 및 트렌드 분석")
    st.markdown("매출액과 판매량을 브랜드 및 품목별로 심도 있게 분석합니다.")

    try:
        # 1. 데이터 불러오기 (판매기록 + 품목기본정보)
        df_sales = load_data_func("sales_record")
        df_item = load_data_func("ecount_item_data") # 🚀 품목 정보 매칭용
        
        # --- [데이터 전처리: 판매 기록] ---
        df_sales.columns = df_sales.columns.str.strip()
        
        if '일자' not in df_sales.columns:
            st.error("🚨 시트 첫 줄에 '일자' 열을 찾을 수 없습니다. 시트를 확인해주세요.")
            return

        # '공급가액' 열이 없을 경우 에러 방지용 (기본값 0)
        if '공급가액' not in df_sales.columns:
            df_sales['공급가액'] = 0

        df_sales['일자'] = pd.to_datetime(df_sales['일자'], errors='coerce')
        df_sales['수량'] = df_sales['수량'].astype(str).str.replace(',', '')
        df_sales['수량'] = pd.to_numeric(df_sales['수량'], errors='coerce').fillna(0)
        df_sales['공급가액'] = df_sales['공급가액'].astype(str).str.replace(',', '')
        df_sales['공급가액'] = pd.to_numeric(df_sales['공급가액'], errors='coerce').fillna(0)
        
        # 빈 날짜 제거 및 순수 판매(수량>0)만 필터
        df_sales = df_sales.dropna(subset=['일자'])
        df_sales = df_sales[df_sales['수량'] > 0] 

        if df_sales.empty:
            st.warning("표시할 판매 데이터가 없습니다.")
            return

        # --- [데이터 전처리: 품목 정보 매칭] ---
        # ecount_item_data에서 브랜드와 박스입수(D열) 가져오기
        box_col_name = df_item.columns[3] 
        df_item_info = df_item[['품목코드', '브랜드', box_col_name]].copy()
        df_item_info.rename(columns={box_col_name: '박스입수'}, inplace=True)
        df_item_info['박스입수'] = pd.to_numeric(df_item_info['박스입수'], errors='coerce').fillna(1)
        
        # 판매 기록(df_sales)에 브랜드와 박스입수 병합 (품목코드 기준 VLOOKUP 역할)
        df_sales = pd.merge(df_sales, df_item_info, on='품목코드', how='left')
        df_sales['브랜드'] = df_sales['브랜드'].fillna('기타')
        df_sales['박스입수'] = df_sales['박스입수'].fillna(1)
        
        # 실제 계산용 환산수량 (소수점 박스)
        df_sales['환산수량'] = df_sales['수량'] / df_sales['박스입수']

        # 화면 표시용 환산 포맷 함수 (박스/개 변환)
        def format_qty_display(qty, box_unit):
            if box_unit <= 1: 
                return f"{int(qty):,} 개" if qty == int(qty) else f"{qty:.1f} 개"
            boxes = qty / box_unit
            return f"{boxes:.1f} 박스" if boxes < 10 else f"{int(boxes):,} 박스"

        # 2. 사이드바: 기간 및 브랜드 필터
        st.sidebar.markdown("### 📅 검색 조건 설정")
        min_date = df_sales['일자'].min().date()
        max_date = df_sales['일자'].max().date()
        default_start = max(min_date, max_date - datetime.timedelta(days=90))
        
        start_date = st.sidebar.date_input("시작일", default_start, min_value=min_date, max_value=max_date)
        end_date = st.sidebar.date_input("종료일", max_date, min_value=min_date, max_value=max_date)
        
        # 🚀 추가: 브랜드 필터 적용
        brand_list = ["전체보기"] + sorted(list(df_sales['브랜드'].unique()))
        selected_brand = st.sidebar.selectbox("🔍 브랜드 필터", brand_list)

        # 필터 적용 데이터 자르기
        mask = (df_sales['일자'].dt.date >= start_date) & (df_sales['일자'].dt.date <= end_date)
        filtered_df = df_sales.loc[mask].copy()
        
        if selected_brand != "전체보기":
            filtered_df = filtered_df[filtered_df['브랜드'] == selected_brand]

        if filtered_df.empty:
            st.warning("선택하신 조건에 맞는 판매 데이터가 없습니다.")
            return

        # 3. 화면 상단 KPI 요약 (매출액 중심으로 변경)
        total_amount = filtered_df['공급가액'].sum()
        total_days = (end_date - start_date).days + 1
        daily_avg_amount = total_amount / total_days if total_days > 0 else 0
        total_qty = filtered_df['수량'].sum() # 총 수량도 참고용으로 함께 표시

        # 4칸으로 나누어서 핵심 정보 배치
        col1, col2, col3, col4 = st.columns(4)
        col1.metric(label="💰 총 판매액", value=f"{int(total_amount):,} 원")
        col2.metric(label="📅 분석 기간", value=f"{total_days} 일")
        col3.metric(label="💸 일평균 판매액", value=f"{int(daily_avg_amount):,} 원")
        col4.metric(label="📦 총 판매수량", value=f"{int(total_qty):,} 개")
        
        st.markdown("---")

        # ==========================================
        # 📊 [차트 1] 일별 판매 추이
        # ==========================================
        st.subheader("📉 일별 판매 추이")
        
        # 금액과 수량의 단위(스케일)가 너무 달라서 탭으로 분리하여 보여줍니다.
        tab1, tab2 = st.tabs(["💰 매출액 흐름보기", "📦 판매수량 흐름보기"])
        
        daily_trend = filtered_df.groupby('일자')[['공급가액', '수량']].sum().reset_index()
        daily_trend.set_index('일자', inplace=True)
        
        with tab1:
            st.line_chart(daily_trend['공급가액'], color="#2E86C1") # 매출액은 파란색
        with tab2:
            st.line_chart(daily_trend['수량'], color="#28B463") # 수량은 초록색

        # ==========================================
        # 📊 [차트 2] 베스트셀러 TOP 10
        # ==========================================
        st.subheader("🏆 베스트셀러 TOP 10")
        
        tab3, tab4 = st.tabs(["💰 매출액 기준 TOP 10", "📦 환산수량(박스/개) 기준 TOP 10"])
        
        with tab3:
            # 품목별 매출액 합산 및 정렬
            top_amount = filtered_df.groupby('품목명')['공급가액'].sum().sort_values(ascending=False).head(10)
            st.bar_chart(top_amount, color="#E74C3C") # 빨간색
            
        with tab4:
            # 품목별 환산수량(박스) 합산 및 정렬
            top_qty = filtered_df.groupby('품목명')['환산수량'].sum().sort_values(ascending=False).head(10)
            st.bar_chart(top_qty, color="#F39C12") # 주황색

        # ==========================================
        # 📋 데이터 원본 확인 (환산수량 적용)
        # ==========================================
        with st.expander("🔍 선택된 기간의 상세 판매 기록 보기"):
            display_df = filtered_df[['일자', '브랜드', '품목명', '수량', '박스입수', '공급가액']].copy()
            display_df['일자'] = display_df['일자'].dt.strftime('%Y-%m-%d')
            display_df['환산수량'] = display_df.apply(lambda r: format_qty_display(r['수량'], r['박스입수']), axis=1)
            display_df['공급가액(원)'] = display_df['공급가액'].apply(lambda x: f"{int(x):,}")
            
            # 보기 편하게 컬럼 순서 재배치
            display_df = display_df[['일자', '브랜드', '품목명', '환산수량', '공급가액(원)']]
            st.dataframe(display_df.sort_values(by='일자', ascending=False), use_container_width=True)

    except Exception as e:
        st.error(f"데이터 분석 중 오류가 발생했습니다: {e}")
