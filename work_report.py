import streamlit as st
import pandas as pd
from datetime import datetime, timedelta

def get_week_start(d):
    return (d - timedelta(days=d.weekday())).strftime("%Y-%m-%d")

def run(load_sheet_data):
    st.markdown("<h1>📅 주간 요일별 업무 보고</h1>", unsafe_allow_html=True)
    
    df_emp = load_sheet_data("Employees")
    df_report = load_sheet_data("WorkReports")
    
    if df_emp is None or df_report is None:
        st.error("시트를 불러올 수 없습니다.")
        return

    # 1. 사이드바 설정
    st.sidebar.markdown("### 🔍 조회 조건")
    target_date = st.sidebar.date_input("기준 날짜 선택", datetime.today())
    target_week = get_week_start(target_date)
    
    emp_names = ["전체보기"] + df_emp['성명'].tolist()
    selected_emp = st.sidebar.selectbox("직원 선택", emp_names)
    
    # 2. 데이터 필터링 (주차 및 직원)
    subset = df_report[df_report['보고일자'] == target_week].copy()
    if selected_emp != "전체보기":
        target_id = df_emp[df_emp['성명'] == selected_emp]['직원ID'].values[0]
        subset = subset[subset['직원ID'] == str(target_id)]

    # 3. 요일별 탭 구성
    days = ["월", "화", "수", "목", "금"]
    tabs = st.tabs([f"{d}요일" for d in days])

    for i, day in enumerate(days):
        with tabs[i]:
            # 해당 요일 데이터만 추출
            day_data = subset[subset['요일'] == day]
            
            st.subheader(f"{day}요일 업무 내용")
            
            # 수정 가능한 표
            edited_day_df = st.data_editor(
                day_data[['분류', '내용']],
                column_config={
                    "분류": st.column_config.SelectboxColumn("구분", options=["저번주 할일", "결과", "이번주 할일"], disabled=True),
                    "내용": st.column_config.TextColumn("업무 상세 내용", width="large")
                },
                hide_index=True,
                use_container_width=True,
                key=f"editor_{day}"
            )

    if st.button("💾 모든 요일 변경사항 저장"):
        # 여기서 각 탭의 edited_day_df를 합쳐서 구글 시트에 업데이트하는 로직 구현
        st.success("데이터가 성공적으로 업데이트되었습니다.")
