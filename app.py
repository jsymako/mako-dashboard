import streamlit as st
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import json
from streamlit_option_menu import option_menu # 👈 완벽한 세로 메뉴를 위한 라이브러리

# 🚀 메뉴별 파일 임포트
import own_stock
import coupang_stock
import sales_trend
import trade_trend
import ar_trend

st.set_page_config(page_title="통합재고관리", page_icon="📦", layout="wide")

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
# 🚀 1. 사이드바 열기/닫기 글자 "완전 박멸" CSS
# -----------------------------------------------------------------
st.markdown("""
    <style>
    /* 기존 버튼 안의 모든 글자, 아이콘(SVG)을 완전히 삭제하고 깔끔한 ❯ 화살표만 남김 */
    [data-testid="collapsedControl"] {
        color: transparent !important;
        background: transparent !important;
    }
    [data-testid="collapsedControl"] * {
        display: none !important; 
    }
    [data-testid="collapsedControl"]::after {
        content: "❯" !important;
        font-size: 24px !important;
        font-weight: 900 !important;
        color: #333333 !important;
        display: block !important;
        margin-left: 10px !important;
    }
    </style>
""", unsafe_allow_html=True)

# -----------------------------------------------------------------
# 🚀 2. 사이드바 구성 (스트레스 없는 완벽한 세로 메뉴)
# -----------------------------------------------------------------
with st.sidebar:
    st.image("mako_logo.png", use_container_width=True) 
    st.title("통합관리")

    # CSS 꼼수 없이 자체적으로 완벽하게 세로 정렬 및 디자인을 지원하는 메뉴!
    main_menu = option_menu(
        menu_title=None, # "MENU"라는 글자 숨김 (더 깔끔함)
        options=["📦 자사 재고", "🚀 쿠팡 재고", "📈 판매 현황", "🤝 거래처 현황", "💳 채권 분석"],
        icons=["", "", "", "", ""], # 이모지를 썼으므로 자체 아이콘은 뺌
        default_index=0,
        styles={
            # 메뉴 배경 
            "container": {"padding": "0!important", "background-color": "transparent", "border": "none"},
            # 개별 버튼 폰트 및 박스 디자인 (여기서 수치만 바꾸시면 100% 적용됩니다)
            "nav-link": {
                "font-size": "1.3rem",       # 👈 글자 크기 확실하게 커집니다
                "text-align": "left",        # 왼쪽 정렬
                "margin": "0px 0px 10px 0px",# 버튼 사이 간격
                "padding": "15px 20px",      # 버튼 내부 여백
                "border-radius": "8px",      # 둥근 모서리
                "border": "2px solid #ddd",  # 테두리
                "color": "#333",             # 평상시 글자색
                "font-weight": "bold"
            },
            # 마우스 올렸을 때
            "nav-link-hover": {
                "background-color": "#fdf2f2", 
                "border-color": "#d9534f"
            },
            # 클릭해서 선택되었을 때 (빨간 배경 + 흰 글씨)
            "nav-link-selected": {
                "background-color": "#d9534f", 
                "color": "white", 
                "font-weight": "900", 
                "border-color": "#d9534f"
            },
        }
    )

st.sidebar.markdown("---")

# -----------------------------------------------------------------
# 🚀 3. 메뉴 선택에 따른 화면 전환
# -----------------------------------------------------------------
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
