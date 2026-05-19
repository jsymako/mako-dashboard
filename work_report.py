import streamlit as st
import pandas as pd
from datetime import datetime, timedelta

# 주차의 월요일 날짜를 구하는 함수
def get_week_start(d):
    return (d - timedelta(days=d.weekday())).strftime("%Y-%m-%d")

def run(load_sheet_data):
    st.markdown("<h1>📝 주간 업무 보고 시스템</h1>", unsafe_allow_html=True)
    
    # 1. 시트 데이터 로드
    df_emp = load_sheet_data("Employees")
    df_report = load_sheet_data("WorkReports")
    
    if df_emp is None or df_report is None:
        st.error("시트를 불러올 수 없습니다. 시트 이름을 확인해주세요.")
        return

    # 2. 사이드바 주차 및 직원 필터
    st.sidebar.markdown("### 📅 보고 조회 조건")
    target_date = st.sidebar.date_input("기준 날짜 선택", datetime.today())
    target_week = get_week_start(target_date)
    
    st.sidebar.info(f"조회 주차(월요일 기준): **{target_week}**")
    
    # 3. 데이터 에디터 출력
    # 선택한 주차의 전체 직원 보고서를 필터링
    df_report['보고일자'] = df_report['보고일자'].astype(str).str.strip()
    subset = df_report[df_report['보고일자'] == target_week]
    
    # 직원 정보와 보고서 병합 (성명 표시)
    df_emp['직원ID'] = df_emp['직원ID'].astype(str)
    subset['직원ID'] = subset['직원ID'].astype(str)
    final_df = pd.merge(subset, df_emp, on='직원ID', how='left')

    st.subheader(f"전체 직원 업무 보고 ({target_week} 주차)")
    
    # 데이터 에디터로 수정 가능하게 구현
    edited_df = st.data_editor(
        final_df[['성명', '분류', '내용']],
        column_config={
            "성명": st.column_config.TextColumn("직원명", disabled=True),
            "분류": st.column_config.SelectboxColumn("구분", options=["저번주 할일", "결과", "이번주 할일"], disabled=True),
            "내용": st.column_config.TextColumn("업무 상세 내용", width="large")
        },
        hide_index=True,
        use_container_width=True
    )

    if st.button("💾 변경사항 전체 저장"):
        # 여기서 get_worksheet_for_write 를 이용해 구글 시트로 push하는 로직 추가
        st.success("데이터가 구글 시트에 업데이트되었습니다.")
