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
# 🚀 1. 사이드바 구성 (로고 + Pills 메뉴 + 절대 실패 없는 CSS)
# -----------------------------------------------------------------
with st.sidebar:
    st.image("mako_logo.png", use_container_width=True) 
    st.title("통합관리")

    st.markdown("""
        <style>
        /* =========================================================
           🚨 1. 사이드바 열기 글자 완벽 삭제 & 아이콘만 살리기
        ========================================================= */
        [data-testid="collapsedControl"] {
            color: transparent !important;
            background-color: transparent !important;
        }
        [data-testid="collapsedControl"] * {
            color: transparent !important; 
        }
        [data-testid="collapsedControl"] svg {
            color: #333333 !important; 
            fill: #333333 !important;
            width: 1.8rem !important;
            height: 1.8rem !important;
            visibility: visible !important;
        }

        /* =========================================================
           🚨 2. 알약(Pills) 버튼 무조건 한 줄에 하나씩(세로) 정렬
        ========================================================= */
        div[data-testid="stPills"] > div {
            display: flex !important;
            flex-direction: column !important; /* 세로 정렬의 핵심 */
            width: 100% !important;
            gap: 8px !important;
        }

        /* 개별 버튼 가로 100% 꽉 채우기 및 디자인 */
        div[data-testid="stPills"] button {
            width: 100% !important; 
            min-width: 100% !important; /* 강제로 가로를 꽉 채움 */
            display: flex !important;
            justify-content: flex-start !important; /* 텍스트 왼쪽 정렬 */
            padding: 12px 20px !important; 
            border-radius: 8px !important; 
            border: 2px solid #dddddd !important; 
            background-color: #ffffff !important; 
        }
        
        div[data-testid="stPills"] button p {
            font-size: 2.15rem !important; 
            color: #333333 !important;
            margin: 0 !important;
        }

        /* 마우스 올렸을 때 (Hover) */
        div[data-testid="stPills"] button:hover {
            border-color: #d9534f !important; 
            background-color: #fdf2f2 !important; 
        }

        /* 선택된(Active) 상태일 때 */
        div[data-testid="stPills"] button[aria-pressed="true"] {
            background-color: #d9534f !important; 
            border-color: #d9534f !important;
        }
        div[data-testid="stPills"] button[aria-pressed="true"] p {
            font-weight: 800 !important; 
            color: #ffffff !important; /* 흰색 글씨 */
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
