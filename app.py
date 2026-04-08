import streamlit as st
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import json

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
# 🚀 1. 사이드바 구성 (로고 + Pills 메뉴 + 커스텀 CSS)
# -----------------------------------------------------------------
with st.sidebar:
    st.image("mako_logo.png", use_container_width=True) 
    
    st.title("통합관리")

    st.markdown("""
        <style>
        /* 🚀 1. 펼치기(>) 아이콘 살리고 "Open sidebar" 글자만 완벽 제거 */
        [data-testid="collapsedControl"] {
            font-size: 0px !important; /* 텍스트 크기를 0으로 만들어 흔적도 없이 지움 */
        }
        [data-testid="collapsedControl"] svg {
            width: 1.5rem !important;  /* 지워지지 않게 아이콘 크기 강제 고정 */
            height: 1.5rem !important; 
            fill: #333333 !important;  /* 아이콘 색상 진하게 */
        }

        /* 🚀 2. 알약(Pills) 버튼 세로 정렬 (100% 확실한 타겟팅) */
        section[data-testid="stSidebar"] div[role="group"] {
            display: flex !important;
            flex-direction: column !important; /* 세로 정렬 */
            gap: 10px !important; /* 버튼 간격 */
            width: 100% !important;
        }

        /* 🚀 3. 개별 알약 버튼 디자인 */
        section[data-testid="stSidebar"] div[role="group"] button {
            width: 100% !important; 
            justify-content: flex-start !important; /* 글자 왼쪽 정렬 */
            padding: 10px 20px !important; 
            border-radius: 8px !important; 
            border: 2px solid #dddddd !important; 
            background-color: #ffffff !important; 
            transition: all 0.2s ease-in-out !important; 
        }
        
        section[data-testid="stSidebar"] div[role="group"] button p {
            font-size: 1.15rem !important; /* 너무 크면 잘릴 수 있어 1.15로 세팅 */
            margin: 0 !important;
        }

        /* 🚀 4. 마우스 올렸을 때 (Hover) */
        section[data-testid="stSidebar"] div[role="group"] button:hover {
            border-color: #d9534f !important; 
            background-color: #fdf2f2 !important; 
        }

        /* 🚀 5. 선택된(Active) 상태일 때 */
        section[data-testid="stSidebar"] div[role="group"] button[aria-pressed="true"] {
            background-color: #d9534f !important; 
            border-color: #d9534f !important;
        }
        section[data-testid="stSidebar"] div[role="group"] button[aria-pressed="true"] p {
            font-weight: 800 !important; 
            color: #ffffff !important; /* 글자를 흰색으로 확 띄게 */
        }
        </style>
    """, unsafe_allow_html=True)
    
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
        label_visibility="collapsed" 
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
