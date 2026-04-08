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
        /* 1. 알약 버튼을 감싸는 보이지 않는 부모 박스를 찾아 세로(Column)로 강제 정렬 */
        div:has(> button[data-testid^="stBaseButton-pill"]) {
            display: flex !important;
            flex-direction: column !important; /* 세로 정렬의 핵심 */
            gap: 10px !important; /* 버튼 사이의 간격 */
            width: 100% !important;
        }

        /* 2. 개별 알약 버튼 디자인 (정확한 버튼 고유 ID 타겟팅) */
        button[data-testid^="stBaseButton-pill"] {
            width: 100% !important; 
            justify-content: flex-start !important; /* 왼쪽 정렬 */
            padding-left: 10px !important; /* 왼쪽 여백 */
            border-radius: 8px !important; 
            border: 2px solid #dddddd !important; /* 테두리 굵기 */
            background-color: #ffffff !important; 
            font-size: 2.1rem !important; /* 2.05rem은 너무 클 수 있어 살짝 줄였습니다. 필요시 늘리세요! */
            transition: all 0.2s ease-in-out !important; 
        }

        /* 3. 마우스를 올렸을 때(Hover)의 디자인 */
        button[data-testid^="stBaseButton-pill"]:hover {
            border-color: #d9534f !important; 
            background-color: #fdf2f2 !important; 
        }

        /* 4. 선택된(Active) 상태일 때의 버튼 및 글자 디자인 */
        button[data-testid="stBaseButton-pillsActive"] {
            background-color: #d9534f !important; /* 선택되면 배경을 빨간색으로 */
            border-color: #d9534f !important;
        }
        
        button[data-testid="stBaseButton-pillsActive"] p {
            font-weight: 900 !important; 
            color: #ffffff !important; /* 선택되면 글자를 흰색으로 확 띄게 */
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
