import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
import time
import json
import gspread
from oauth2client.service_account import ServiceAccountCredentials

# Google Sheets 연결
def get_worksheet_for_write(sheet_name):
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    creds_dict = json.loads(st.secrets["gcp_service_account"])
    creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
    client = gspread.authorize(creds)
    doc = client.open("통합재고관리")
    return doc.worksheet(sheet_name)

def get_week_start(d):
    return (d - timedelta(days=d.weekday()))

def run(load_sheet_data):
    st.markdown("<h1>📝 주간 업무 보고 시스템</h1>", unsafe_allow_html=True)
    
    df_emp = load_sheet_data("Employees")
    df_report = load_sheet_data("WorkReports")
    
    if df_emp is None or df_report is None: return

    # 날짜 구간 계산
    target_date = st.sidebar.date_input("기준 주차 선택", datetime.today())
    monday = get_week_start(target_date)
    last_monday = monday - timedelta(days=7)
    
    # 예: 5월 11일 ~ 15일
    last_week_range = f"({last_monday.strftime('%m월%d일')} ~ {(last_monday + timedelta(days=4)).strftime('%m월%d일')})"
    this_week_range = f"({monday.strftime('%m월%d일')} ~ {(monday + timedelta(days=4)).strftime('%m월%d일')})"
    
    # 🚀 행 이름 정의 (날짜 구간 포함)
    cat_mapping = {
        '저번주 할일': f'저번주 할일 {last_week_range}',
        '결과': '결과',
        '이번주 할일': f'이번주 할일 {this_week_range}'
    }
    
    # 사이드바 직원 선택
    emp_names = ["전체"] + df_emp['성명'].tolist()
    selected_emp = st.sidebar.selectbox("직원 선택", emp_names)
    
    # (생략: 데이터 로드 및 subset 추출 로직은 이전과 동일)
    # ... subset 생성 ...

    # 💡 데이터 에디터에 적용
    st.subheader(f"{selected_emp} 님의 업무 상세")
    
    # pivot_df 생성 후
    pivot_df = pivot_df.rename(index=cat_mapping)
    edited_df = st.data_editor(pivot_df, use_container_width=True)

    if st.button("💾 저장"):
        # 🚀 저장 시에는 cat_mapping 역으로 돌려서 '저번주 할일' 키워드로 시트에 저장
        st.success("저장 완료!")
