import streamlit as st
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import json

# 1. 페이지 기본 설정 (가장 먼저 와야 함) - 🚀 타이틀 '통합재고관리'로 변경
st.set_page_config(page_title="통합재고관리", page_icon="📊", layout="wide")

# 2. 구글 시트 데이터 불러오기 함수
@st.cache_data(ttl=600) # 10분마다 새로고침
def load_sheet_data(worksheet_name):
    scope = [
        "https://spreadsheets.google.com/feeds",
        "https://www.googleapis.com/auth/drive"
    ]
    creds_dict = json.loads(st.secrets["gcp_service_account"])
    creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
    client = gspread.authorize(creds)
    
    doc = client.open("통합재고관리")
    sheet = doc.worksheet(worksheet_name)
    
    data = sheet.get_all_values()
    df = pd.DataFrame(data[1:], columns=data[0])
    return df

# ==========================================
# 3. 사이드바 (왼쪽 네비게이션 메뉴)
# ==========================================
# 🚀 타이틀 '통합재고관리'로 변경
st.sidebar.title("📊 통합재고관리")
st.sidebar.caption("원하시는 메뉴를 선택하세요.")

main_menu = st.sidebar.radio(
    "▶ 메뉴 이동",
    ["📦 자사 재고 현황", "🚀 쿠팡 재고 현황", "📈 판매 현황"]
)

st.sidebar.markdown("---")

# ==========================================
# 4. 메뉴별 화면 구성
# ==========================================

# ------------------------------------------
# [메뉴 1] 자사 재고 현황 (이카운트)
# ------------------------------------------
if main_menu == "📦 자사 재고 현황":
    st.title("📦 자사 재고 현황 및 소진 예측 (주 단위)")
    
    try:
        # 1. 시트 데이터 모두 불러오기
        df_own = load_sheet_data("ecount_stock")
        df_sales = load_sheet_data("sales_record")
        df_item = load_sheet_data("ecount_item_data")
        
        update_time = df_own['업데이트 시간'].iloc[0] if '업데이트 시간' in df_own.columns and not df_own.empty else '정보 없음'

        # 전처리
        df_own['현재재고'] = pd.to_numeric(df_own['현재재고'], errors='coerce').fillna(0)
        df_sales['수량'] = df_sales['수량'].astype(str).str.replace(',', '')
        df_sales['수량'] = pd.to_numeric(df_sales['수량'], errors='coerce').fillna(0)
        df_sales['일자'] = pd.to_datetime(df_sales['일자'], errors='coerce', yearfirst=True)

        # 박스입수 및 과다기준주 추출
        box_col_name = df_item.columns[3] 
        df_item_box = df_item[['품목코드', box_col_name]].copy()
        df_item_box.rename(columns={box_col_name: '박스입수'}, inplace=True)
        df_item_box['박스입수'] = pd.to_numeric(df_item_box['박스입수'], errors='coerce').fillna(1)

        excess_col_name = df_item.columns[4]
        df_item_limit = df_item[['품목코드', excess_col_name]].copy()
        df_item_limit.rename(columns={excess_col_name: '과다기준주'}, inplace=True)
        df_item_limit['과다기준주'] = pd.to_numeric(df_item_limit['과다기준주'], errors='coerce')

        # 사이드바 필터
        brand_list = ["전체보기"] + sorted(list(df_own['브랜드'].unique()))
        selected_brand = st.sidebar.selectbox("🔍 브랜드 필터", brand_list)
        
        status_list = ["전체보기", "품절", "재고 부족", "과다 재고", "적정"]
        selected_status = st.sidebar.selectbox("⚠️ 상태 필터", status_list)
        
        months_to_look_back = st.sidebar.slider("📅 판매 평균 산출 기준 (개월)", min_value=1, max_value=12, value=1)
        
        # 날짜 계산 및 필터링
        from dateutil.relativedelta import relativedelta
        import datetime
        
        today = datetime.datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        end_date = today.replace(day=1) - datetime.timedelta(days=1)
        start_date = (end_date - relativedelta(months=months_to_look_back - 1)).replace(day=1)
        
        recent_sales = df_sales[(df_sales['일자'] >= pd.Timestamp(start_date)) & (df_sales['일자'] <= pd.Timestamp(end_date))]
        
        total_sales_by_item = recent_sales.groupby('품목코드')['수량'].sum().reset_index()
        total_sales_by_item.rename(columns={'수량': '기간내_총판매량'}, inplace=True)
        
        total_sales_by_item['월평균판매량'] = total_sales_by_item['기간내_총판매량'] / months_to_look_back
        total_sales_by_item['주평균판매량'] = (total_sales_by_item['월평균판매량'] / 4).round(1)
        
        # 데이터 병합
        df_merged = pd.merge(df_own, total_sales_by_item[['품목코드', '주평균판매량']], on='품목코드', how='left')
        df_merged['주평균판매량'] = df_merged['주평균판매량'].fillna(0)
        
        df_merged = pd.merge(df_merged, df_item_limit, on='품목코드', how='left')
        df_merged = pd.merge(df_merged, df_item_box, on='품목코드', how='left')
        
        # 계산 로직
        import numpy as np
        df_merged['예상소진주'] = np.where(df_merged['주평균판매량'] > 0, 
                                       df_merged['현재재고'] / df_merged['주평균판매량'], 
                                       999.0)
        df_merged['예상소진주'] = df_merged['예상소진주'].round(1)
        
        def check_status(row):
            if row['현재재고'] <= 0: return "🔴 품절"
            elif row['예상소진주'] < 4.0: return "🟠 재고 부족 (4주 미만)"
            else:
                limit = row['과다기준주'] if pd.notna(row['과다기준주']) and row['과다기준주'] > 0 else 24.0
                if row['예상소진주'] > limit:
                    return f"🔵 과다 재고 ({int(limit)}주 초과)"
                else:
                    return "🟢 적정"
            
        df_merged['재고상태'] = df_merged.apply(check_status, axis=1)

        def format_stock_display(qty, box_unit):
            if box_unit <= 1:
                if qty == int(qty): return f"{int(qty):,} 개"
                else: return f"{qty:.1f} 개"
            else:
                boxes = qty / box_unit
                if boxes < 10: return f"{boxes:.1f} 박스"
                else: return f"{int(boxes):,} 박스"

        df_merged['환산재고'] = df_merged.apply(lambda row: format_stock_display(row['현재재고'], row['박스입수']), axis=1)
        df_merged['환산주평균'] = df_merged.apply(lambda row: format_stock_display(row['주평균판매량'], row['박스입수']), axis=1)

        # 화면 출력 필터
        if selected_brand != "전체보기":
            df_merged = df_merged[df_merged['브랜드'] == selected_brand]
            
        if selected_status != "전체보기":
            df_merged = df_merged[df_merged['재고상태'].str.contains(selected_status, na=False)]
            
        final_display_df = df_merged[['브랜드', '품목명', '환산재고', '환산주평균', '예상소진주', '재고상태']]
        final_display_df = final_display_df.rename(columns={
            '환산재고': '현재재고',
            '환산주평균': '주평균판매량'
        })
        
        date_range_str = f"{start_date.year}년 {start_date.month}월 ~ {end_date.year}년 {end_date.month}월"
        
        st.info(f"""
        **🕒 데이터 업데이트 :** {update_time}  
        **💡 산출 기준 :** {date_range_str} ({months_to_look_back}개월 판매량을 4주 단위로 환산)
        """)
        
        # ==========================================
        # 🚀 [핵심 추가] 반응형 CSS 박스 레이아웃 주입
        # ==========================================
        custom_css = """
        <style>
        /* 브랜드별 그룹을 묶어주는 바탕색 박스 */
        .brand-section {
            background-color: rgba(150, 150, 150, 0.05);
            border-radius: 12px;
            padding: 20px;
            margin-bottom: 30px;
        }
        .brand-title {
            font-size: 1.4rem;
            font-weight: bold;
            color: var(--text-color);
            margin-bottom: 15px;
            border-bottom: 2px solid rgba(150, 150, 150, 0.2);
            padding-bottom: 10px;
        }
        /* 화면 크기에 맞춰 가로 갯수가 변하는 CSS Grid */
        .grid-container {
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
            gap: 15px;
        }
        /* 개별 품목 카드 디자인 */
        .item-card {
            background-color: var(--background-color);
            border: 1px solid rgba(150, 150, 150, 0.2);
            border-radius: 10px;
            padding: 18px;
            box-shadow: 0 4px 6px rgba(0,0,0,0.05);
            transition: transform 0.2s, box-shadow 0.2s;
        }
        .item-card:hover {
            transform: translateY(-5px);
            box-shadow: 0 6px 12px rgba(0,0,0,0.1);
        }
        .item-title {
            font-size: 1.1rem;
            font-weight: bold;
            margin-bottom: 12px;
            line-height: 1.3;
            min-height: 45px; /* 제목이 두 줄일 때 카드 높이 맞춤 */
            color: var(--text-color);
        }
        .info-row {
            display: flex;
            justify-content: space-between;
            margin-bottom: 6px;
            font-size: 0.95rem;
        }
        .info-label { color: #888; font-weight: 500; }
        .info-val { font-weight: bold; color: var(--text-color); }
        
        /* 상태별 뱃지 색상 */
        .badge {
            display: block;
            text-align: center;
            padding: 8px;
            border-radius: 6px;
            font-weight: bold;
            font-size: 0.9rem;
            margin-top: 15px;
        }
        .badge-out { background-color: #ffebee; color: #c62828; border: 1px solid #ffcdd2;}
        .badge-short { background-color: #fff3e0; color: #ef6c00; border: 1px solid #ffe0b2;}
        .badge-over { background-color: #e3f2fd; color: #1565c0; border: 1px solid #bbdefb;}
        .badge-good { background-color: #e8f5e9; color: #2e7d32; border: 1px solid #c8e6c9;}
        </style>
        """
        st.markdown(custom_css, unsafe_allow_html=True)

        if final_display_df.empty:
            st.warning("조건에 맞는 품목이 없습니다.")
        else:
            # 브랜드를 가나다순으로 정렬하여 그룹별 렌더링
            unique_brands = sorted(final_display_df['브랜드'].unique())
            
            for br in unique_brands:
                br_df = final_display_df[final_display_df['브랜드'] == br]
                
                # 브랜드 섹션 시작 (바탕색 박스)
                html_content = f'<div class="brand-section">'
                html_content += f'<div class="brand-title">🏢 {br} ({len(br_df)}개 품목)</div>'
                html_content += '<div class="grid-container">'
                
                # 박스 생성
                for _, row in br_df.iterrows():
                    # 상태에 따른 뱃지 클래스 지정
                    status_class = "badge-good"
                    if "품절" in row['재고상태']: status_class = "badge-out"
                    elif "부족" in row['재고상태']: status_class = "badge-short"
                    elif "과다" in row['재고상태']: status_class = "badge-over"
                    
                    # 999주인 경우 무한대 표시 처리
                    weeks_val = "자료 없음" if row['예상소진주'] >= 999 else f"{row['예상소진주']} 주"
                    
                    html_content += f"""
                    <div class="item-card">
                        <div class="item-title">{row['품목명']}</div>
                        <div class="info-row"><span class="info-label">현재 재고</span><span class="info-val">{row['현재재고']}</span></div>
                        <div class="info-row"><span class="info-label">주평균 판매</span><span class="info-val">{row['주평균판매량']}</span></div>
                        <div class="info-row"><span class="info-label">예상 소진</span><span class="info-val">{weeks_val}</span></div>
                        <div class="badge {status_class}">{row['재고상태']}</div>
                    </div>
                    """
                
                html_content += '</div></div>' # grid-container & brand-section 닫기
                
                # HTML 렌더링
                st.markdown(html_content, unsafe_allow_html=True)
                
    except Exception as e:
        st.error(f"데이터 분석 중 오류가 발생했습니다: {e}")

# ------------------------------------------
# [메뉴 2] 쿠팡 재고 현황 (광고센터 크롤링)
# ------------------------------------------
elif main_menu == "🚀 쿠팡 재고 현황":
    st.title("🚀 쿠팡 재고 현황")
    st.info("💡 향후 이곳에 쿠팡 품절 임박 상품, 과다 재고 알림 등의 로직이 추가될 예정입니다.")
    
    try:
        df_coupang = load_sheet_data("coupang_stock")
        last_update = df_coupang['기록시간'].iloc[0] if not df_coupang.empty and '기록시간' in df_coupang.columns else '정보 없음'
        st.caption(f"최근 데이터 동기화: {last_update}")
        st.subheader("📋 쿠팡 원본 데이터 확인")
        st.dataframe(df_coupang, use_container_width=True)
    except Exception as e:
        st.error(f"쿠팡 데이터를 불러오지 못했습니다: {e}")

# ------------------------------------------
# [메뉴 3] 판매 현황 (이카운트 매출)
# ------------------------------------------
elif main_menu == "📈 판매 현황":
    st.title("📈 제품별 판매 현황 및 트렌드")
    st.info("💡 향후 이곳에 기간(1~12개월) 선택 필터와, 판매량 기반 재고 소진 예상일 분석이 추가될 예정입니다.")
    
    try:
        df_sales = load_sheet_data("sales_record")
        st.subheader("📋 누적 판매 데이터 확인")
        st.dataframe(df_sales.tail(100), use_container_width=True)
    except Exception as e:
        st.error(f"판매 데이터를 불러오지 못했습니다: {e}")

