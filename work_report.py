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

    # 🚀 [핵심 추가] 각 직원의 '완성된 표'를 임시 저장할 저장소 생성
    all_edited_dfs = {}

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
        
        # 🚀 [핵심 수정] 에디터의 리턴값(완벽한 DataFrame)을 변수에 직접 저장!
        edited_df = st.data_editor(pivot_df, use_container_width=True, key=f"editor_{emp_name}_{target_week}")
        all_edited_dfs[emp_name] = edited_df

    # -----------------------------------------------------------------
    # 저장 버튼 로직
    # -----------------------------------------------------------------
    if st.button("💾 모든 변경사항 저장", use_container_width=True):
        with st.spinner("구글 시트에 저장 중..."):
            try:
                sheet_r = get_worksheet_for_write("WorkReports")
                new_rows = [] # 데이터를 한 번에 모아서 쏘기 위한 리스트
                
                for emp_name in target_employees:
                    # 🚀 [핵심 수정] 저장해둔 완벽한 DataFrame을 그대로 가져옴 (에러 원천 차단)
                    final_df = all_edited_dfs.get(emp_name)
                    target_id = str(df_emp[df_emp['성명'] == emp_name]['직원ID'].values[0])

                    for i, cat in enumerate(cat_order):
                        for day in day_order:
                            clean_cat = cat.split(' (')[0]
                            
                            # DataFrame에서 행(i), 열(day) 데이터를 안전하게 추출
                            content = str(final_df.iloc[i][day])
                            
                            new_row = [f"{emp_name}_{target_week}_{clean_cat}_{day}", target_id, target_week, day, clean_cat, content]
                            new_rows.append(new_row)
                
                # 시트에 한 번에 추가 (속도 최적화)
                sheet_r.append_rows(new_rows)
                
                st.success("✅ 저장 완료!")
                time.sleep(1)
                st.rerun()
                
            except Exception as e:
                st.error(f"저장 중 오류 발생: {e}")
