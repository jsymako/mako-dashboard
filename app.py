import streamlit as st
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import json

# 1. 페이지 기본 설정 (가장 먼저 와야 함)
st.set_page_config(page_title="마코 통합 대시보드", page_icon="📊", layout="wide")

# 2. 구글 시트 데이터 불러오기 함수 (시트 이름만 넣으면 다 가져오도록 모듈화!)
@st.cache_data(ttl=600) # 10분마다 새로고침
def load_sheet_data(worksheet_name):
    scope = [
        "https://spreadsheets.google.com/feeds",
        "https://www.googleapis.com/auth/drive"
    ]
    # Secrets에서 인증 정보 가져오기
    creds_dict = json.loads(st.secrets["gcp_service_account"])
    creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
    client = gspread.authorize(creds)
    
    # 통합재고관리 문서에서 원하는 탭(worksheet_name) 열기
    doc = client.open("통합재고관리")
    sheet = doc.worksheet(worksheet_name)
    
    data = sheet.get_all_values()
    df = pd.DataFrame(data[1:], columns=data[0])
    return df

# ==========================================
# 3. 사이드바 (왼쪽 네비게이션 메뉴)
# ==========================================
st.sidebar.title("📊 통합 대시보드")
st.sidebar.caption("원하시는 메뉴를 선택하세요.")

# 라디오 버튼으로 큰 카테고리 3개 분리
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
    st.title("📦 자사 재고 현황 (이카운트)")
    
    try:
        df_own = load_sheet_data("ecount_stock")
        df_own['현재재고'] = pd.to_numeric(df_own['현재재고'], errors='coerce').fillna(0)
        
        # 업데이트 시간 표시
        last_update = df_own['업데이트 시간'].iloc[0] if not df_own.empty else '정보 없음'
        st.caption(f"최근 데이터 동기화: {last_update}")
        
        # 자사 재고 전용 브랜드 필터 (사이드바 하단에 추가)
        brand_list = ["전체보기"] + sorted(list(df_own['브랜드'].unique()))
        selected_brand = st.sidebar.selectbox("🔍 브랜드 필터", brand_list)
        
        if selected_brand == "전체보기":
            filtered_df = df_own
        else:
            filtered_df = df_own[df_own['브랜드'] == selected_brand]
            
        st.subheader(f"📊 [{selected_brand}] 재고 차트")
        chart_data = filtered_df.set_index('품목명')['현재재고']
        st.bar_chart(chart_data)
        
        st.subheader("📋 상세 재고 표")
        st.dataframe(filtered_df[['브랜드', '품목코드', '품목명', '현재재고']], use_container_width=True)
        
    except Exception as e:
        st.error(f"자사 재고 데이터를 불러오지 못했습니다: {e}")

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
        # 데이터가 너무 많을 수 있으므로 최근 100개만 미리보기
        st.dataframe(df_sales.tail(100), use_container_width=True)
        
    except Exception as e:
        st.error(f"판매 데이터를 불러오지 못했습니다: {e}")
