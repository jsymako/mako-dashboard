import streamlit as st
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import json

# 🚀 메뉴별 파일 임포트
import own_stock
import coupang_stock
import sales_trend

st.set_page_config(page_title="통합재고관리", page_icon="📊", layout="wide")

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

st.sidebar.title("📊 통합재고관리")
main_menu = st.sidebar.radio("▶ 메뉴 이동", ["📦 자사 재고 현황", "🚀 쿠팡 재고 현황", "📈 판매 현황"])
st.sidebar.markdown("---")

# 🚀 각 파일의 run 함수에 load_sheet_data 함수 자체를 전달함
if main_menu == "📦 자사 재고 현황":
    own_stock.run(load_sheet_data) 
elif main_menu == "🚀 쿠팡 재고 현황":
    coupang_stock.run(load_sheet_data)
elif main_menu == "📈 판매 현황":
    sales_trend.run(load_sheet_data)

