import streamlit as st
import pandas as pd
from datetime import datetime, timedelta

def get_week_start(d):
    return (d - timedelta(days=d.weekday())).strftime("%Y-%m-%d")

def run(load_sheet_data):
    st.markdown("<h1>📝 주간 업무 보고 시스템</h1>", unsafe_allow_html=True)
    
    df_emp = load_sheet_data("Employees")
    df_report = load_sheet_data("WorkReports")
    
    if df_emp is None or df_report is None: return

    # 1. 날짜 구간 계산
    target_date = st.sidebar.date_input("기준 주차 선택", datetime.today())
    monday = datetime.strptime(get_week_start(target_date), "%Y-%m-%d")
    target_week = monday.strftime("%Y-%m-%d")
    
    last_monday = monday - timedelta(days=7)
    last_week_range = f"({last_monday.strftime('%m월%d일')} ~ {(last_monday + timedelta(days=4)).strftime('%m월%d일')})"
    this_week_range = f"({monday.strftime('%m월%d일')} ~ {(monday + timedelta(days=4)).strftime('%m월%d일')})"
    
    # 2. 사이드바 및 필터 설정
    emp_names = ["전체"] + df_emp['성명'].tolist()
    selected_emp = st.sidebar.selectbox("직원 선택", emp_names)
    
    # 3. 데이터 로드 및 매트릭스 변환
    df_report['보고일자'] = df_report['보고일자'].astype(str).str.strip()
    subset = df_report[df_report['보고일자'] == target_week]
    
    if selected_emp != "전체":
        target_id = str(df_emp[df_emp['성명'] == selected_emp]['직원ID'].values[0])
        subset = subset[subset['직원ID'] == target_id]

    # 4. 💡 빈 데이터 처리 및 매트릭스 구성 (에러 방지 핵심)
    day_order = ['월', '화', '수', '목', '금']
    cat_order = ['저번주 할일', '결과', '이번주 할일']
    
    if subset.empty:
        pivot_df = pd.DataFrame("", index=cat_order, columns=day_order)
    else:
        pivot_df = subset.pivot(index='분류', columns='요일', values='내용')
        # 데이터가 일부만 있어도 3x5 구조로 정렬
        pivot_df = pivot_df.reindex(index=cat_order, columns=day_order).fillna("")

    # 5. 행 이름 매핑 (날짜 구간 포함)
    cat_mapping = {
        '저번주 할일': f'저번주 할일 {last_week_range}',
        '결과': '결과',
        '이번주 할일': f'이번주 할일 {this_week_range}'
    }
    pivot_df = pivot_df.rename(index=cat_mapping)

    # 6. 화면 출력
    st.subheader(f"{selected_emp} 님의 업무 상세")
    edited_df = st.data_editor(pivot_df, use_container_width=True)

    if st.button("💾 변경사항 저장"):
        st.success("데이터를 시트로 전송할 준비가 되었습니다! (저장 로직 연동 중)")
