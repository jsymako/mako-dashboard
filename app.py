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



with st.sidebar:
    # 로고가 있다면 아래 주석을 풀고 사용하세요
    st.image("mako_logo.png", use_container_width=True) 
    
    # ⚠️ 아래 main_menu 변수는 무조건 들여쓰기(Tab 1번)가 되어 있어야 합니다!
    main_menu = option_menu(
        menu_title="통합관리시스템",      
        options=["자사 재고", "쿠팡 재고", "판매 현황", "거래처 현황", "채권 분석"],
        icons=["box-seam", "rocket", "graph-up", "people", "credit-card"], 
        menu_icon="cast",          
        default_index=0,           
        styles={
            "container": {"padding": "0!important"},
            "icon": {"color": "#333", "font-size": "20px"}, 
            "nav-link": {"font-size": "20px", "text-align": "left", "margin":"0px", "--hover-color": "#eee"},
            "nav-link-selected": {"background-color": "#d9534f", "color": "white"},
        }
    )
st.sidebar.markdown("---")

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



