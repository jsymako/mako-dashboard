import streamlit as st
import pandas as pd
from datetime import datetime, timedelta

def get_week_start(d):
    # 선택된 날짜의 해당 주차 월요일을 반환
    return (d - timedelta(days=d.weekday())).strftime("%Y-%m-%d")

def run(load_sheet_data):
    st.markdown("<h1>📝 주간 업무 보고 시스템</h1>", unsafe_allow_html=True)
    
    # 1. 데이터 로드 (Google Sheet: WorkReports)
    df = load_sheet_data("WorkReports")
    if df is None:
        st.error("업무 보고 시트를 불러올 수 없습니다.")
        return

    # 2. 사이드바 필터링
    st.sidebar.markdown("### 📅 보고 조회 조건")
    target_date = st.sidebar.date_input("기준 날짜 선택", datetime.today())
    target_week = get_week_start(target_date)
    
    # 직원 목록 (Manufacturers처럼 별도 시트가 있다면 거기서 로드)
    emp_list = ["김철수", "이영희", "박지성"] # 예시
    selected_emp = st.sidebar.selectbox("직원 선택", emp_list)
    
    st.sidebar.info(f"현재 선택된 주차: **{target_week}**")

    # 3. 데이터 필터링 및 에디터 구성
    # 해당 주차 & 해당 직원의 데이터만 추출
    mask = (df['보고주차'] == target_week) & (df['직원명'] == selected_emp)
    subset = df[mask]
    
    st.subheader(f"{selected_emp} 님의 {target_week} 주차 업무 보고")
    
    # 수정 가능한 표 (Data Editor)
    edited_df = st.data_editor(
        subset[['항목', '내용']], # 필요한 열만 표시
        column_config={
            "내용": st.column_config.TextColumn("업무 내용", width="large")
        },
        hide_index=True,
        use_container_width=True
    )

    if st.button("💾 보고서 저장"):
        # 여기서 구글 시트에 반영하는 로직 (get_worksheet_for_write 사용)
        st.success("저장되었습니다!")
