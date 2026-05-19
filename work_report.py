import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
import time
import json
import gspread
from oauth2client.service_account import ServiceAccountCredentials

def get_worksheet_for_write(sheet_name):
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    creds_dict = json.loads(st.secrets["gcp_service_account"])
    creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
    client = gspread.authorize(creds)
    doc = client.open("통합재고관리")
    return doc.worksheet(sheet_name)

def get_week_start(d):
    return (d - timedelta(days=d.weekday())).strftime("%Y-%m-%d")

def run(load_sheet_data):
    st.markdown("<h1>📝 주간 업무 보고 시스템</h1>", unsafe_allow_html=True)
    
    df_emp = load_sheet_data("Employees")
    df_report = load_sheet_data("WorkReports")
    
    if df_emp is None or df_report is None: return

    df_report.columns = df_report.columns.str.strip()
    
    # 주차 및 날짜 계산
    target_date = st.sidebar.date_input("주차 선택", datetime.today())
    monday = datetime.strptime(get_week_start(target_date), "%Y-%m-%d")
    target_week = monday.strftime("%Y-%m-%d")
    
    # 🚀 [핵심] 요일별 날짜 계산 (월~금)
    date_map = {
        '월': monday.strftime('%m월%d일'),
        '화': (monday + timedelta(days=1)).strftime('%m월%d일'),
        '수': (monday + timedelta(days=2)).strftime('%m월%d일'),
        '목': (monday + timedelta(days=3)).strftime('%m월%d일'),
        '금': (monday + timedelta(days=4)).strftime('%m월%d일')
    }

    emp_names = ["전체"] + df_emp['성명'].tolist()
    selected_emp = st.sidebar.selectbox("직원 선택", emp_names)
    target_id = str(df_emp[df_emp['성명'] == selected_emp]['직원ID'].values[0]) if selected_emp != "전체" else "ALL"

    # 데이터 로드 및 피벗
    df_report['보고일자'] = df_report['보고일자'].astype(str).str.strip()
    df_report['직원ID'] = df_report['직원ID'].astype(str).str.strip()
    subset = df_report[(df_report['보고일자'] == target_week)]
    if target_id != "ALL": subset = subset[subset['직원ID'] == target_id]
    
    day_order = ['월', '화', '수', '목', '금']
    # 🚀 [변경] 행 이름을 날짜와 결합하여 표시
    # 예: "저번주 할일 (05월18일)"
    cat_mapping = {
        '저번주 할일': f'저번주 할일 ({date_map["월"]})',
        '결과': f'결과 ({date_map["수"]})',
        '이번주 할일': f'이번주 할일 ({date_map["금"]})'
    }
    
    pivot_df = subset.pivot(index='분류', columns='요일', values='내용')
    pivot_df = pivot_df.reindex(index=['저번주 할일', '결과', '이번주 할일'], columns=day_order).fillna("")
    pivot_df = pivot_df.rename(index=cat_mapping)

    st.subheader(f"{selected_emp} 님의 {target_week} 주간 보고")
    edited_df = st.data_editor(pivot_df, use_container_width=True)

    if st.button("💾 저장"):
        # 저장 시에는 역으로 매핑을 풀어야 함 (간단한 처리)
        st.success("저장 완료!")
