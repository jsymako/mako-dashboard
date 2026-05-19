import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
import time
import json
import gspread
from oauth2client.service_account import ServiceAccountCredentials

# Google Sheets 연결 함수
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
    
    if df_emp is None or df_report is None:
        st.error("데이터 로드 실패")
        return

    df_report.columns = df_report.columns.str.strip()
    
    st.sidebar.markdown("### 📅 조회 및 작성 조건")
    target_date = st.sidebar.date_input("주차 선택", datetime.today())
    target_week = get_week_start(target_date)
    
    # 요일 계산을 위한 날짜 객체 생성
    monday = datetime.strptime(target_week, "%Y-%m-%d")
    friday = monday + timedelta(days=4)
    date_range_str = f"{monday.strftime('%m월%d일')} ~ {friday.strftime('%m월%d일')}"
    
    # 🚀 [업데이트] 전체 보기 추가
    emp_names = ["전체"] + df_emp['성명'].tolist()
    selected_emp = st.sidebar.selectbox("직원 선택", emp_names)

    # 보고 대상 ID 리스트 결정
    if selected_emp == "전체":
        target_ids = df_emp['직원ID'].astype(str).tolist()
    else:
        target_ids = [str(df_emp[df_emp['성명'] == selected_emp]['직원ID'].values[0])]

    st.subheader(f"{selected_emp} 님의 주간 업무 보고")
    st.caption(f"🗓️ 영업일: {date_range_str}") # 🚀 영업일 표시

    # 데이터 로직 (여러 직원이면 첫 번째 직원 기준 폼 생성/로드)
    target_id = target_ids[0] 
    df_report['보고일자'] = df_report['보고일자'].astype(str).str.strip()
    df_report['직원ID'] = df_report['직원ID'].astype(str).str.strip()
    subset = df_report[(df_report['보고일자'] == target_week) & (df_report['직원ID'] == target_id)]
    
    day_order = ['월', '화', '수', '목', '금']
    category_order = ['저번주 할일', '결과', '이번주 할일']

    if subset.empty:
        st.info(f"✨ {target_week} ({date_range_str}) 데이터가 없습니다. 내용을 입력해주세요.")
        pivot_df = pd.DataFrame("", index=category_order, columns=day_order)
    else:
        pivot_df = subset.pivot(index='분류', columns='요일', values='내용').reindex(index=category_order, columns=day_order).fillna("")

    edited_df = st.data_editor(pivot_df, use_container_width=True, key="report_editor")

    if st.button("💾 주간 업무 보고서 저장하기", use_container_width=True):
        sheet_r = get_worksheet_for_write("WorkReports")
        # 기존 저장 로직과 동일 (단, 전체 선택 시 저장은 1인 기준 처리)
        new_rows = []
        timestamp = int(time.time())
        for cat in category_order:
            for day in day_order:
                content = edited_df.loc[cat, day]
                new_rows.append([f"R_{timestamp}_{target_id}_{day}", target_id, target_week, day, cat, content])
        
        sheet_r.append_rows(new_rows)
        st.success(f"✅ 저장되었습니다!")
        time.sleep(1)
        st.rerun()
