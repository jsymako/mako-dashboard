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

# 🚀 [핵심 로직] 특정 날짜가 몇 월 몇 주차인지 계산하는 함수
def get_week_info(date_obj):
    # 해당 주의 월요일 찾기
    monday = date_obj - timedelta(days=date_obj.weekday())
    # 해당 주의 목요일 찾기 (목요일이 속한 달이 그 주의 '월'이 됨 - 표준 기준)
    thursday = monday + timedelta(days=3)
    month = thursday.month
    
    # 그 달의 첫 번째 날과 첫 번째 목요일 찾기
    first_of_month = datetime(thursday.year, month, 1)
    first_thursday = first_of_month + timedelta(days=(3 - first_of_month.weekday() + 7) % 7)
    
    # 주차 계산
    week_num = (thursday - first_thursday).days // 7 + 1
    
    # 표시용 텍스트 및 DB 저장용 값
    mon_str = monday.strftime('%m/%d')
    fri_str = (monday + timedelta(days=4)).strftime('%m/%d')
    
    label = f"{month}월 {week_num}주차 ({mon_str}~{fri_str})"
    value = monday.strftime('%Y-%m-%d')
    return label, value

# 2. 메인 실행 함수
def run(load_sheet_data):
    st.markdown("<h1>📝 주간 업무 보고 시스템</h1>", unsafe_allow_html=True)
    
    df_emp = load_sheet_data("Employees")
    df_report = load_sheet_data("WorkReports")
    
    if df_emp is None or df_report is None:
        st.error("데이터 로드 실패")
        return

    # ---------------------------------------------------------
    # 💡 [UI 개선] 주차 선택 드롭다운 생성 (과거 12주 ~ 미래 4주)
    # ---------------------------------------------------------
    st.sidebar.markdown("### 📅 기준 주차 선택")
    
    today = datetime.today()
    week_options = {}
    default_index = 0
    
    # -12주부터 +4주까지의 리스트를 생성
    weeks_list = []
    for i in range(-12, 5):
        target_d = today + timedelta(weeks=i)
        lbl, val = get_week_info(target_d)
        week_options[lbl] = val
        weeks_list.append(lbl)
        if i == 0:  # 현재 주차의 인덱스 기억
            default_index = len(weeks_list) - 1

    # 달력(date_input) 대신 드롭다운(selectbox) 사용
    selected_week_label = st.sidebar.selectbox("주차를 선택하세요", weeks_list, index=default_index)
    
    # DB 조회용 월요일 날짜 (예: 2026-05-18)
    target_week = week_options[selected_week_label]
    monday = datetime.strptime(target_week, "%Y-%m-%d")
    # ---------------------------------------------------------

    # 사이드바 직원 선택
    emp_names = ["전체"] + df_emp['성명'].tolist()
    selected_emp = st.sidebar.selectbox("직원 선택", emp_names)
    
    target_employees = df_emp['성명'].tolist() if selected_emp == "전체" else [selected_emp]

    all_edited_dfs = {}

    # 직원별 순회
    for emp_name in target_employees:
        target_id = str(df_emp[df_emp['성명'] == emp_name]['직원ID'].values[0])
        
        subset = df_report[(df_report['보고일자'] == target_week) & (df_report['직원ID'] == target_id)]
        
        # 날짜 텍스트
        last_monday = monday - timedelta(days=7)
        last_week_range = f"({last_monday.strftime('%m/%d')} ~ {(last_monday + timedelta(days=4)).strftime('%m/%d')})"
        this_week_range = f"({monday.strftime('%m/%d')} ~ {(monday + timedelta(days=4)).strftime('%m/%d')})"
        
        day_order = ['월', '화', '수', '목', '금']
        cat_order = ['저번주 할일', '결과', '이번주 할일']
        
        if subset.empty:
            pivot_df = pd.DataFrame("", index=cat_order, columns=day_order)
        else:
            pivot_df = subset.pivot(index='분류', columns='요일', values='내용').reindex(index=cat_order, columns=day_order).fillna("")

        pivot_df = pivot_df.rename(index={'저번주 할일': f'저번주 할일 {last_week_range}', '이번주 할일': f'이번주 할일 {this_week_range}'})

        st.markdown(f"---")
        # 제목에도 선택한 '5월 3주차' 라벨을 명시적으로 표시하여 혼동 방지
        st.subheader(f"👤 {emp_name} 님 - {selected_week_label}")
        
        edited_df = st.data_editor(pivot_df, use_container_width=True, key=f"editor_{emp_name}_{target_week}")
        all_edited_dfs[emp_name] = edited_df

    # 저장 버튼 로직
    if st.button("💾 모든 변경사항 저장", use_container_width=True):
        with st.spinner("구글 시트에 저장 중..."):
            try:
                sheet_r = get_worksheet_for_write("WorkReports")
                new_rows = [] 
                
                for emp_name in target_employees:
                    final_df = all_edited_dfs.get(emp_name)
                    target_id = str(df_emp[df_emp['성명'] == emp_name]['직원ID'].values[0])

                    for i, cat in enumerate(cat_order):
                        for day in day_order:
                            clean_cat = cat.split(' (')[0]
                            content = str(final_df.iloc[i][day])
                            
                            new_row = [f"{emp_name}_{target_week}_{clean_cat}_{day}", target_id, target_week, day, clean_cat, content]
                            new_rows.append(new_row)
                
                sheet_r.append_rows(new_rows)
                
                st.success(f"✅ {selected_week_label} 데이터 저장 완료!")
                time.sleep(1)
                st.rerun()
                
            except Exception as e:
                st.error(f"저장 중 오류 발생: {e}")
