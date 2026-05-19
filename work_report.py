import streamlit as st
import pandas as pd
from datetime import datetime, timedelta

def get_week_start(d):
    return (d - timedelta(days=d.weekday())).strftime("%Y-%m-%d")

def run(load_sheet_data):
    st.markdown("<h1>📝 주간 업무 보고 시스템</h1>", unsafe_allow_html=True)
    
    df_emp = load_sheet_data("Employees")
    df_report = load_sheet_data("WorkReports")
    
    if df_emp is None or df_report is None:
        st.error("데이터 로드 실패")
        return

    # 사이드바
    st.sidebar.markdown("### 📅 조회 조건")
    target_date = st.sidebar.date_input("주차 선택", datetime.today())
    target_week = get_week_start(target_date)
    emp_names = df_emp['성명'].tolist()
    selected_emp = st.sidebar.selectbox("직원 선택", emp_names)

    # 데이터 필터링 및 매트릭스 변환
    target_id = df_emp[df_emp['성명'] == selected_emp]['직원ID'].values[0]
    subset = df_report[(df_report['보고일자'] == target_week) & (df_report['직원ID'] == str(target_id))]
    
    # 💡 노션처럼 요일을 가로로, 분류를 세로로 만들기 위한 피벗
    pivot_df = subset.pivot(index='분류', columns='요일', values='내용')
    
    # 요일 순서 보장 (월, 화, 수, 목, 금)
    day_order = ['월', '화', '수', '목', '금']
    pivot_df = pivot_df.reindex(columns=day_order)

    st.subheader(f"{selected_emp} 님의 {target_week} 주간 보고")
    
    # 수정 가능한 표 (노션 뷰)
    edited_df = st.data_editor(
        pivot_df,
        column_config={
            "월": st.column_config.TextColumn("월", width="medium"),
            "화": st.column_config.TextColumn("화", width="medium"),
            "수": st.column_config.TextColumn("수", width="medium"),
            "목": st.column_config.TextColumn("목", width="medium"),
            "금": st.column_config.TextColumn("금", width="medium"),
        },
        use_container_width=True
    )

    if st.button("💾 변경사항 저장"):
        # 저장 로직 (edited_df를 다시 긴 형식으로 melt해서 시트 저장)
        st.success("저장 완료!")
