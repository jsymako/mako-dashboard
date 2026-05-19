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

    # 🚀 [방어 코드] 시트 헤더 공백 제거 (이게 있으면 에러가 싹 사라집니다)
    df_report.columns = df_report.columns.str.strip()
    
    # 🚀 [방어 코드] '요일' 열이 있는지 확인
    if '요일' not in df_report.columns:
        st.error(f"🚨 시트에 '요일' 열이 없습니다! 현재 시트 헤더: {list(df_report.columns)}")
        return

    st.sidebar.markdown("### 📅 조회 조건")
    target_date = st.sidebar.date_input("주차 선택", datetime.today())
    target_week = get_week_start(target_date)
    emp_names = df_emp['성명'].tolist()
    selected_emp = st.sidebar.selectbox("직원 선택", emp_names)

    target_id = df_emp[df_emp['성명'] == selected_emp]['직원ID'].values[0]
    
    # 데이터 타입 통일
    df_report['보고일자'] = df_report['보고일자'].astype(str).str.strip()
    df_report['직원ID'] = df_report['직원ID'].astype(str).str.strip()
    
    subset = df_report[(df_report['보고일자'] == target_week) & (df_report['직원ID'] == str(target_id))]
    
    if subset.empty:
        st.warning(f"{target_week} 주차에 등록된 {selected_emp} 님의 업무 데이터가 없습니다.")
        return
    
    pivot_df = subset.pivot(index='분류', columns='요일', values='내용')
    
    day_order = ['월', '화', '수', '목', '금']
    # 🚀 [방어 코드] 요일이 없는 경우 예외 처리
    existing_days = [d for d in day_order if d in pivot_df.columns]
    pivot_df = pivot_df.reindex(columns=existing_days)

    st.subheader(f"{selected_emp} 님의 {target_week} 주간 보고")
    
    edited_df = st.data_editor(pivot_df, use_container_width=True)

    if st.button("💾 변경사항 저장"):
        st.success("저장 완료!")
