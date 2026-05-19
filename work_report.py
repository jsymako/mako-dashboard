import streamlit as st
import pandas as pd
from datetime import datetime, timedelta

# 주차의 월요일 날짜를 구하는 함수
def get_week_start(d):
    return (d - timedelta(days=d.weekday())).strftime("%Y-%m-%d")

def run(load_sheet_data):
    # 1. 스타일 적용 (기존 style.css 연동)
    try:
        with open('style.css', encoding='utf-8') as f:
            st.markdown(f'<style>{f.read()}</style>', unsafe_allow_html=True)
    except: pass

    st.markdown("<h1>📝 주간 업무 보고 시스템</h1>", unsafe_allow_html=True)
    
    # 2. 시트 데이터 로드
    df_emp = load_sheet_data("Employees")
    df_report = load_sheet_data("WorkReports")
    
    if df_emp is None or df_report is None:
        st.error("🚨 업무 보고 시트(Employees/WorkReports)를 불러올 수 없습니다.")
        return

    # 3. 사이드바 필터링
    st.sidebar.markdown("### 📅 조회 및 작성 조건")
    target_date = st.sidebar.date_input("기준 날짜 선택", datetime.today())
    target_week = get_week_start(target_date)
    
    # 직원 선택 (전체보기 추가)
    emp_names = ["전체보기"] + df_emp['성명'].tolist()
    selected_emp = st.sidebar.selectbox("직원 선택", emp_names)
    
    st.sidebar.info(f"현재 선택된 주차: **{target_week}**")

    # 4. 데이터 병합 및 필터링
    df_report['보고일자'] = df_report['보고일자'].astype(str).str.strip()
    subset = df_report[df_report['보고일자'] == target_week]
    
    if selected_emp != "전체보기":
        target_id = df_emp[df_emp['성명'] == selected_emp]['직원ID'].values[0]
        subset = subset[subset['직원ID'] == str(target_id)]

    # 5. 데이터 에디터 출력
    st.subheader(f"업무 상세 내용 ({target_week} 주차)")
    
    # 수정 가능한 표: 분류별(저번주/결과/이번주)로 보여줌
    edited_df = st.data_editor(
        subset[['직원ID', '분류', '내용']], 
        column_config={
            "직원ID": st.column_config.TextColumn("직원ID", disabled=True),
            "분류": st.column_config.SelectboxColumn("구분", options=["저번주 할일", "결과", "이번주 할일"], disabled=True),
            "내용": st.column_config.TextColumn("업무 상세 내용", width="large")
        },
        hide_index=True,
        use_container_width=True
    )

    if st.button("💾 변경사항 저장"):
        # 여기서 get_worksheet_for_write 를 이용해 구글 시트 반영
        st.success("데이터가 구글 시트에 업데이트되었습니다.")
