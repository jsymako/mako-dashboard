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
# 🚀 1. 사이드바 구성 (로고 + Pills 메뉴 + 커스텀 CSS)
# -----------------------------------------------------------------
with st.sidebar:
    # 로고가 있다면 아래 주석을 풀고 사용하세요
    st.image("mako_logo.png", use_container_width=True) 
    
    st.title("통합관리")

    # 🎨 [CSS] 알약(Pills) 버튼 세로형 배치 및 커스텀 스타일링
    st.markdown("""
        <style>
        /* 1. 알약 버튼들을 가로가 아닌 '세로(한 줄에 하나씩)'로 강제 정렬 */
        div[data-testid="stPills"] > div {
            display: flex !important;
            flex-direction: column !important; /* 세로 정렬의 핵심 */
            gap: 8px !important; /* 버튼 사이의 위아래 간격 */
        }

        /* 2. 개별 알약 버튼 디자인 (여기서 색상/모양을 마음대로 수정하세요!) */
        div[data-testid="stPills"] button {
            width: 100% !important; /* 가로 길이를 사이드바에 꽉 차게 */
            justify-content: flex-start !important; /* 글자를 왼쪽으로 정렬 (가운데 정렬 원하시면 center로 변경) */
            padding-left: 20px !important; /* 왼쪽 여백 */
            border-radius: 8px !important; /* 모서리 둥글기 (0으로 하면 네모난 버튼이 됨) */
            border: 1px solid #dddddd !important; /* 테두리 굵기와 색상 */
            background-color: #ffffff !important; /* 평상시 배경색 */
            font-size: 1.05rem !important; /* 글자 크기 */
            transition: all 0.2s ease-in-out !important; /* 마우스 올릴 때 부드러운 효과 */
        }

        /* 3. 마우스를 올렸을 때(Hover)의 디자인 */
        div[data-testid="stPills"] button:hover {
            border-color: #d9534f !important; /* 마우스 올렸을 때 테두리 색상 */
            background-color: #fdf2f2 !important; /* 마우스 올렸을 때 배경색 (연한 빨강) */
        }

        /* 4. 선택된(Active) 상태일 때 스트림릿 기본색(빨강 등)을 유지하면서 글자만 조정하고 싶을 때 */
        div[data-testid="stPills"] button[aria-pressed="true"] p {
            font-weight: 800 !important; /* 선택된 메뉴 글자를 아주 굵게! */
        }
        </style>
    """, unsafe_allow_html=True)
    
    # 🚀 트렌디한 알약(Pills) 버튼 적용! (이제 세로로 나옵니다)
    main_menu = st.pills(
        "MENU", 
        [
            "📦 자사 재고", 
            "🚀 쿠팡 재고", 
            "📈 판매 현황", 
            "🤝 거래처 현황",
            "💳 채권 분석"
        ],
        default="📦 자사 재고",
        label_visibility="collapsed" # "MENU"라는 작은 글씨가 거슬리면 이걸로 숨길 수 있습니다.
    )

st.sidebar.markdown("---")

# -----------------------------------------------------------------
# 🚀 2. 메뉴 선택에 따른 화면 전환
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

