import streamlit as st
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import json
from streamlit_option_menu import option_menu

# 🚀 메뉴별 파일 임포트
import own_stock
import coupang_stock
import sales_trend
import trade_trend
import ar_trend

st.set_page_config(page_title="통합재고관리", page_icon="", layout="wide")

# 🚀 공통 데이터 로드 함수
@st.cache_data(ttl=600)
def load_sheet_data(worksheet_name):
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    creds_dict = json.loads(st.secrets["gcp_service_account"])
    creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
    client = gspread.authorize(creds)
    doc = client.open("통합재고관리")
    sheet = doc.worksheet(worksheet_name)
    data = sheet.get_all_values()
    df = pd.DataFrame(data[1:], columns=data[0])
    return df



# -----------------------------------------------------------------
# 🚀 1. 사이드바 구성 (로고 + Pills 메뉴)
# -----------------------------------------------------------------
with st.sidebar:
    # 로고가 있다면 아래 주석을 풀고 사용하세요
    st.image("mako_logo.png", use_container_width=True) 
    
    st.title("통합관리")
    
    # 🚀 트렌디한 알약(Pills) 모양 버튼 적용!
    main_menu = st.pills(
        "MENU", 
        [
            "📦 자사 재고", 
            "🚀 쿠팡 재고", 
            "📈 판매 현황", 
            "🤝 거래처 현황",
            "💳 채권 분석"
        ],
        default="📦 자사 재고" # 처음 켰을 때 기본 선택값
    )

st.sidebar.markdown("---")

# -----------------------------------------------------------------
# 🚀 2. 메뉴 선택에 따른 화면 전환 (이모지 포함 필수!)
# -----------------------------------------------------------------
# 아무것도 선택하지 않았을 때(None) 에러가 나지 않도록 방어 코드 추가
if main_menu == "📦 자사 재고" or main_menu is None:
    own_stock.run(load_sheet_data) 
elif main_menu == "🚀 쿠팡 재고":
    coupang_stock.run(load_sheet_data)
elif main_menu == "📈 판매 현황":
    sales_trend.run(load_sheet_data)
elif main_menu == "🤝 거래처 현황":
    trade_trend.run(load_sheet_data)
elif main_menu == "💳 채권 분석":
    ar_trend.run(load_sheet_data)



