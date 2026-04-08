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

st.sidebar.image("mako_logo.png", use_container_width=True)

st.sidebar.title("통합관리시스템")

main_menu = option_menu(
        menu_title="통합관리",      # 메뉴 제목
        options=["자사 재고", "쿠팡 재고", "판매 현황", "거래처 현황", "채권 분석"],
        icons=["box-seam", "rocket", "graph-up", "people", "credit-card"], # 부트스트랩 아이콘 이름
        menu_icon="cast",          # 메인 메뉴 아이콘
        default_index=0,           # 기본 선택 인덱스
        styles={
            "container": {"padding": "0!important", "background-color": "#fafafa"},
            "icon": {"color": "#333", "font-size": "18px"}, 
            "nav-link": {"font-size": "15px", "text-align": "left", "margin":"0px", "--hover-color": "#eee"},
            "nav-link-selected": {"background-color": "#d9534f", "color": "white"}, # 👈 선택된 메뉴 색상 (빨간색 톤)
        }
    )

st.sidebar.markdown("---")

# 🚀 2. if 조건문도 메뉴판 글씨와 100% 동일하게 맞춰줍니다.
if main_menu == "자사 재고":
    own_stock.run(load_sheet_data) 
elif main_menu == "쿠팡 재고":
    coupang_stock.run(load_sheet_data)
elif main_menu == "판매 현황":
    sales_trend.run(load_sheet_data)
elif main_menu == "거래처 현황":
    trade_trend.run(load_sheet_data)
elif main_menu == "채권 분석":
    ar_trend.run(load_sheet_data)




