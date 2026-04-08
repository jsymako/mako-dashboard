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

st.sidebar.title("통합관리")

# 🚀 1. 메뉴판 글씨를 조건문과 똑같이 이모지까지 포함해서 적어줍니다! (거래처 현황도 🤝 추가)
main_menu = st.sidebar.radio("MENU", [
    "📦 자사 재고", 
    "🚀 쿠팡 재고", 
    "📈 판매 현황", 
    "🤝 거래처 현황",
    "💳 채권 분석"
])

st.sidebar.markdown("---")

# 🚀 2. if 조건문도 메뉴판 글씨와 100% 동일하게 맞춰줍니다.
if main_menu == "📦 자사 재고":
    own_stock.run(load_sheet_data) 
elif main_menu == "🚀 쿠팡 재고":
    coupang_stock.run(load_sheet_data)
elif main_menu == "📈 판매 현황":
    sales_trend.run(load_sheet_data)
elif main_menu == "🤝 거래처 현황":
    trade_trend.run(load_sheet_data)
elif main_menu == "💳 채권 분석":
    ar_trend.run(load_sheet_data)




