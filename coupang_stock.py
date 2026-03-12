import streamlit as st
import pandas as pd
import datetime
from dateutil.relativedelta import relativedelta
import altair as alt

def load_css(file_name):
    """외부 CSS 파일을 읽어와 Streamlit에 적용"""
    try:
        with open(file_name, "r", encoding="utf-8") as f:
            st.markdown(f'<style>{f.read()}</style>', unsafe_allow_html=True)
    except FileNotFoundError:
        pass

def run(load_data_func):
    # 🚀 공통 CSS 적용
    load_css("main_style.css")

    st.title("📦 쿠팡 재고 및 판매가 현황")
    st.markdown("매일 기록되는 쿠팡 물류 창고의 **재고 흐름**과 **판매가 변동**을 추적합니다.")

    try:
        # 1. 데이터 로드 및 마스터 결합
        df_raw = load_data_func("coupang_stock")
        df_cp_master = load_data_func("coupang_item_data") 
        
        df_raw.columns = ['일자', '옵션ID', '브랜드', '품목명', '쿠팡품목명', '재고', '판매가']
        df_raw['일자'] = pd.to_datetime(df_raw['일자'], errors='coerce')
        df_raw['재고'] = pd.to_numeric(df_raw['재고'].astype(str).str.replace(',', ''), errors='coerce').fillna(0)
        df_raw['판매가'] = pd.to_numeric(df_raw['판매가'].astype(str).str.replace(',', ''), errors='coerce').fillna(0)
        df_raw['옵션ID'] = df_raw['옵션ID'].astype(str).str.strip()
        df_raw = df_raw.dropna(subset=['일자'])
        
        df_cp_master = df_cp_master[['옵션ID', '안전재고량', '최대판매가', '최소판매가']].copy()
        df_cp_master['옵션ID'] = df_cp_master['옵션ID'].astype(str).str.strip()
        
        for col in ['안전재고량', '최대판매가', '최소판매가']:
            df_cp_master[col] = pd.to_numeric(df_cp_master[col].astype(str).str.replace(',', ''), errors='coerce').fillna(0)
            
        df = pd.merge(df_raw, df_cp_master, on='옵션ID', how='left')
        df[['안전재고량', '최대판매가', '최소판매가']] = df[['안전재고량', '최대판매가', '최소판매가']].fillna(0)

        # 2. 사이드바 필터 설정
        st.sidebar.markdown("### 🔍 조회 조건")
        
        brand_list = ["전체보기"] + sorted(list(df['브랜드'].dropna().unique()))
        selected_brand = st.sidebar.selectbox("1. 브랜드 선택", brand_list)
        
        today = datetime.date.today()
        if "coupang_start_date" not in st.session_state: 
            st.session_state.coupang_start_date = today - relativedelta(days=14)
        
        start_date = st.sidebar.date_input("2. 시작일", key="coupang_start_date", format="YYYY/MM/DD")
        end_date = st.sidebar.date_input("종료일", value=today, format="YYYY/MM/DD")
        
        st.sidebar.markdown("---")
        view_target = st.sidebar.radio("3. 조회 항목", ["📦 재고량 추이", "💰 판매가 변동", "📊 모두 보기"], index=2)

        # 필터링 적용
        filtered_df = df.copy()
        if selected_brand != "전체보기":
            filtered_df = filtered_df[filtered_df['브랜드'] == selected_brand]
            
        mask = (filtered_df['일자'].dt.date >= start_date) & (filtered_df['일자'].dt.date <= end_date)
        display_df = filtered_df.loc[mask].copy()

        if display_df.empty:
            st.warning("선택하신 조건에 데이터가 없습니다.")
            return

        # 3. 상단 요약 KPI
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

        # 4. 메인 시각화 (Altair)
        common_axis = alt.Axis(labelFontSize=14, titleFontSize=16, labelAngle=0)
        legend_config = alt.Legend(titleFontSize=15, labelFontSize=14, orient='bottom')

        if view_target in ["📦 재고량 추이", "📊 모두 보기"]:
            st.subheader(f"📦 {selected_brand if selected_brand != '전체보기' else '전체'} 재고량 변동 흐름")
            stock_chart = alt.Chart(display_df).mark_line(point=True).encode(
                x=alt.X('일자:T', title='', axis=alt.Axis(format='%m/%d', labelFontSize=14)),
                y=alt.Y('재고:Q', title='재고 수량 (개)', axis=common_axis),
                color=alt.Color('품목명:N', legend=legend_config, title='품목명'),
                tooltip=['일자:T', '브랜드', '품목명', '재고']
            ).properties(height=400)
            st.altair_chart(stock_chart, use_container_width=True)

        st.markdown("<br>", unsafe_allow_html=True)

        if view_target in ["💰 판매가 변동", "📊 모두 보기"]:
            st.subheader(f"💰 {selected_brand if selected_brand != '전체보기' else '전체'} 판매가 변동 흐름")
            st.caption("※ 쿠팡의 잦은 가격 변동(바이박스 경쟁 등)을 추적합니다.")
            price_chart = alt.Chart(display_df).mark_line(point=True).encode(
                x=alt.X('일자:T', title='', axis=alt.Axis(format='%m/%d', labelFontSize=14)),
                y=alt.Y('판매가:Q', title='판매가 (원)', axis=common_axis, scale=alt.Scale(zero=False)),
                color=alt.Color('품목명:N', legend=legend_config, title='품목명'),
                tooltip=['일자:T', '브랜드', '품목명', '판매가']
            ).properties(height=400)
            st.altair_chart(price_chart, use_container_width=True)

        # ==========================================
        # 5. 🚀 일자별 상세 모니터링 표 (날짜 열 피벗)
        # ==========================================
        st.markdown("---")
        st.subheader("🚨 일자별 안전재고 및 가격 모니터링")
        st.markdown("※ 기준치 미달/초과 발생 시 아이콘과 함께 표시됩니다.")

        # 상태 판별 함수
        def format_stock_status(row):
            val = int(row['재고'])
            safe_val = int(row['안전재고량'])
            if safe_val > 0 and val < safe_val:
                return f"{val:,} 🚨"
            return f"{val:,}"

        def format_price_status(row):
            val = int(row['판매가'])
            max_val = int(row['최대판매가'])
            min_val = int(row['최소판매가'])
            
            if max_val > 0 and val > max_val:
                return f"{val:,} 🔺"
            elif min_val > 0 and val < min_val:
                return f"{val:,} 🔻"
            return f"{val:,}"

        show_df = display_df[['일자', '브랜드', '품목명', '재고', '안전재고량', '판매가', '최소판매가', '최대판매가']].copy()
        
        # 상태값 추출
        show_df['재고 현황'] = show_df.apply(format_stock_status, axis=1)
        show_df['판매가 현황'] = show_df.apply(format_price_status, axis=1)
        
        # 날짜를 열로 보내기 위해 'MM/DD' 형식으로 변환 (가로 공간 확보)
        show_df['일자'] = show_df['일자'].dt.strftime('%m/%d')

        # 🚀 사이드바 라디오 버튼에 따라 표 내용 변경
        if view_target == "📦 재고량 추이":
            show_df['표시값'] = show_df['재고 현황']
        elif view_target == "💰 판매가 변동":
            show_df['표시값'] = show_df['판매가 현황']
        else:
            show_df['표시값'] = "📦 " + show_df['재고 현황'] + " | 💰 " + show_df['판매가 현황']

        # 기준 정보 포맷팅 (기준값은 열 고정)
        show_df['안전재고'] = show_df['안전재고량'].apply(lambda x: f"{int(x):,}")
        show_df['최소판매가'] = show_df['최소판매가'].apply(lambda x: f"{int(x):,}")
        show_df['최대판매가'] = show_df['최대판매가'].apply(lambda x: f"{int(x):,}")

        # 🚀 날짜 피벗 (일자가 열 제목으로 올라감)
        pivot_df = show_df.pivot_table(
            index=['브랜드', '품목명', '안전재고', '최소판매가', '최대판매가'],
            columns='일자',
            values='표시값',
            aggfunc=lambda x: ' '.join(x)
        ).reset_index()

        # 열 정렬: 최신 날짜가 품목명 바로 옆(왼쪽)에 오도록 내림차순 정렬
        date_cols = sorted([col for col in pivot_df.columns if col not in ['브랜드', '품목명', '안전재고', '최소판매가', '최대판매가']], reverse=True)
        final_cols = ['브랜드', '품목명', '안전재고', '최소판매가', '최대판매가'] + date_cols
        
        # 데이터가 없는 날짜 빈칸 처리
        pivot_df = pivot_df[final_cols].fillna("-")

        # 테이블 출력
        st.dataframe(pivot_df, use_container_width=True, hide_index=True)

    except Exception as e:
        st.error(f"오류 발생: {e}")
