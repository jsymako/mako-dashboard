import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
import time
import json
import gspread
from oauth2client.service_account import ServiceAccountCredentials

# 1. 시트 연결 함수
def get_worksheet_for_write(sheet_name):
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    creds_dict = json.loads(st.secrets["gcp_service_account"])
    creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
    client = gspread.authorize(creds)
    doc = client.open("통합재고관리")
    return doc.worksheet(sheet_name)

def get_week_start(d):
    return (d - timedelta(days=d.weekday())).strftime("%Y-%m-%d")

# 2. 메인 실행 함수
def run(load_sheet_data):
    st.markdown("<h1>📝 주간 업무 보고 시스템</h1>", unsafe_allow_html=True)
    
    df_emp = load_sheet_data("Employees")
    df_report = load_sheet_data("WorkReports")
    
    if df_emp is None or df_report is None:
        st.error("데이터 로드 실패")
        return

    # 날짜 구간 계산
    target_date = st.sidebar.date_input("기준 주차 선택", datetime.today())
    monday = datetime.strptime(get_week_start(target_date), "%Y-%m-%d")
    target_week = monday.strftime("%Y-%m-%d")
    
    # 사이드바 직원 선택
    emp_names = ["전체"] + df_emp['성명'].tolist()
    selected_emp = st.sidebar.selectbox("직원 선택", emp_names)
    
    target_employees = df_emp['성명'].tolist() if selected_emp == "전체" else [selected_emp]

    # 직원별 순회
    for emp_name in target_employees:
        target_id = str(df_emp[df_emp['성명'] == emp_name]['직원ID'].values[0])
        
        subset = df_report[(df_report['보고일자'] == target_week) & (df_report['직원ID'] == target_id)]
        
        # 날짜 텍스트
        last_monday = monday - timedelta(days=7)
        last_week_range = f"({last_monday.strftime('%m월%d일')} ~ {(last_monday + timedelta(days=4)).strftime('%m월%d일')})"
        this_week_range = f"({monday.strftime('%m월%d일')} ~ {(monday + timedelta(days=4)).strftime('%m월%d일')})"
        
        day_order = ['월', '화', '수', '목', '금']
        cat_order = ['저번주 할일', '결과', '이번주 할일']
        
        if subset.empty:
            pivot_df = pd.DataFrame("", index=cat_order, columns=day_order)
        else:
            pivot_df = subset.pivot(index='분류', columns='요일', values='내용').reindex(index=cat_order, columns=day_order).fillna("")

        pivot_df = pivot_df.rename(index={'저번주 할일': f'저번주 할일 {last_week_range}', '이번주 할일': f'이번주 할일 {this_week_range}'})

        st.markdown(f"---")
        st.subheader(f"👤 {emp_name} 님 ({target_week} 주차)")
        st.data_editor(pivot_df, use_container_width=True, key=f"editor_{emp_name}_{target_week}")

    # 기존 if st.button("💾 모든 변경사항 저장"): 부분을 아래로 교체하세요
    if st.button("💾 모든 변경사항 저장"):
        with st.spinner("구글 시트에 저장 중..."):
            try:
                sheet_r = get_worksheet_for_write("WorkReports")
                
                # 기존 데이터 전체를 가져옵니다 (업데이트 효율을 위해)
                all_data = sheet_r.get_all_values()
                
                for emp_name in target_employees:
                    # 각 직원별 에디터에 담긴 데이터를 가져옴
                    edited_df = st.session_state.get(f"editor_{emp_name}_{target_week}")
                    
                    # 💡 표(Pivot)를 다시 시트 형태(Long Format)로 변환 (Melt)
                    # 요일(가로)과 분류(세로)를 행으로 풀어서 저장
                    for cat in cat_order:
                        for day in day_order:
                            content = edited_df.loc[cat, day]
                            
                            # 날짜 텍스트 제거 (저번주 할일 (05/11...) -> 저번주 할일)
                            clean_cat = cat.split(' (')[0]
                            
                            # 행 데이터 구성: [보고ID, 직원ID, 보고일자, 요일, 분류, 내용]
                            # 기존에 데이터가 있다면 보고ID를 찾아 업데이트, 없으면 추가
                            new_row = [f"{emp_name}_{target_week}_{cat}_{day}", target_id, target_week, day, clean_cat, content]
                            
                            # 구글 시트에 행 업데이트 (간단한 append 방식 적용)
                            sheet_r.append_row(new_row)
                
                st.success("✅ 모든 데이터가 구글 시트에 저장되었습니다!")
                time.sleep(1)
                st.rerun()
                
            except Exception as e:
                st.error(f"저장 중 오류 발생: {e}")
