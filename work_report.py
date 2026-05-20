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

# 특정 날짜가 몇 월 몇 주차인지 계산하는 함수
def get_week_info(date_obj):
    monday = date_obj - timedelta(days=date_obj.weekday())
    thursday = monday + timedelta(days=3)
    month = thursday.month
    
    first_of_month = datetime(thursday.year, month, 1)
    first_thursday = first_of_month + timedelta(days=(3 - first_of_month.weekday() + 7) % 7)
    
    week_num = (thursday - first_thursday).days // 7 + 1
    
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

    # 주차 선택 드롭다운 생성 (과거 12주 ~ 미래 4주)
    st.sidebar.markdown("### 📅 기준 주차 선택")
    today = datetime.today()
    week_options = {}
    weeks_list = []
    default_index = 0
    
    for i in range(-12, 5):
        lbl, val = get_week_info(target_d := today + timedelta(weeks=i))
        week_options[lbl] = val
        weeks_list.append(lbl)
        if i == 0:
            default_index = len(weeks_list) - 1

    selected_week_label = st.sidebar.selectbox("주차를 선택하세요", weeks_list, index=default_index)
    target_week = week_options[selected_week_label]
    monday = datetime.strptime(target_week, "%Y-%m-%d")

    # 사이드바 직원 선택
    emp_names = ["전체"] + df_emp['성명'].tolist()
    selected_emp = st.sidebar.selectbox("직원 선택", emp_names)
    
    target_employees = df_emp['성명'].tolist() if selected_emp == "전체" else [selected_emp]
    all_edited_dfs = {}

    # 공통 고정 배열 정의
    day_order = ['월', '화', '수', '목', '금']
    cat_order = ['저번주 할일', '결과', '이번주 할일', '펜딩 업무']

    # 직원별 순회하며 표 그리기
    for emp_name in target_employees:
        target_id = str(df_emp[df_emp['성명'] == emp_name]['직원ID'].values[0])
        
        # 데이터 공백 제거 및 정제
        df_report['보고일자'] = df_report['보고일자'].astype(str).str.strip()
        df_report['직원ID'] = df_report['직원ID'].astype(str).str.strip()
        df_report['분류'] = df_report['분류'].astype(str).str.strip()
        
        # 데이터 추출 (현재 주차, 지난 주차, 펜딩 업무)
        subset_week = df_report[(df_report['보고일자'] == target_week) & (df_report['직원ID'] == target_id)]
        
        # 🚀 [핵심] 지난 주차의 '이번주 할일'을 추적하기 위한 가상 날짜 조회
        last_week_date = (monday - timedelta(days=7)).strftime("%Y-%m-%d")
        subset_last_week = df_report[(df_report['보고일자'] == last_week_date) & (df_report['직원ID'] == target_id) & (df_report['분류'] == '이번주 할일')]
        
        subset_pending = df_report[(df_report['보고일자'] == 'PENDING') & (df_report['직원ID'] == target_id)]
        
        # 4x5 표준 그리드 기본 틀 구성
        pivot_df = pd.DataFrame("", index=cat_order, columns=day_order)
        
        # 1. 시트에 현재 주차 데이터가 있다면 덮어씌움
        if not subset_week.empty:
            p_week = subset_week.pivot(index='분류', columns='요일', values='내용')
            for cat in p_week.index:
                if cat in pivot_df.index:
                    pivot_df.loc[cat, p_week.columns] = p_week.loc[cat]
                    
        # 2. 펜딩 데이터 채우기
        if not subset_pending.empty:
            p_pending = subset_pending.pivot(index='분류', columns='요일', values='내용')
            if '펜딩 업무' in p_pending.index:
                pivot_df.loc['펜딩 업무', p_pending.columns] = p_pending.loc['펜딩 업무']
                
        # 3. 🚀 [자동 이월 엔진] 이번 주차의 '저번주 할일' 기록이 아예 없는 상태라면, 지난주 데이터의 '이번주 할일'을 이월시킴
        if (pivot_df.loc['저번주 할일'] == "").all() and not subset_last_week.empty:
            p_last = subset_last_week.pivot(index='분류', columns='요일', values='내용')
            if '이번주 할일' in p_last.index:
                for day in day_order:
                    if day in p_last.columns:
                        pivot_df.loc['저번주 할일', day] = p_last.loc['이번주 할일', day]

        # 날짜 구간 텍스트 정의
        last_monday = monday - timedelta(days=7)
        last_week_range = f"({last_monday.strftime('%m/%d')} ~ {(last_monday + timedelta(days=4)).strftime('%m/%d')})"
        this_week_range = f"({monday.strftime('%m/%d')} ~ {(monday + timedelta(days=4)).strftime('%m/%d')})"
        
        # 표의 사이드 행 라벨 변경
        cat_mapping = {
            '저번주 할일': f'저번주 할일 {last_week_range}',
            '이번주 할일': f'이번주 할일 {this_week_range}',
            '펜딩 업무': '📌 펜딩 업무 (상시)'
        }
        pivot_df = pivot_df.rename(index=cat_mapping)

        st.markdown(f"---")
        st.subheader(f"👤 {emp_name} 님 - {selected_week_label}")
        
        # 🚀 에디터 결과물을 딕셔너리에 직접 매핑하여 데이터 오염 방지
        edited_df = st.data_editor(pivot_df, use_container_width=True, key=f"editor_{emp_name}_{target_week}")
        all_edited_dfs[emp_name] = edited_df

    # -----------------------------------------------------------------
    # 💾 안전 데이터 일괄 동기화 (Overwrite)
    # -----------------------------------------------------------------
    if st.button("💾 모든 변경사항 저장", use_container_width=True):
        with st.spinner("구글 시트에 안전하게 저장 중..."):
            try:
                sheet_r = get_worksheet_for_write("WorkReports")
                
                all_values = sheet_r.get_all_values()
                headers = all_values[0] if all_values else ['보고ID', '직원ID', '보고일자', '요일', '분류', '내용']
                
                target_ids = [str(df_emp[df_emp['성명'] == name]['직원ID'].values[0]) for name in target_employees]
                
                # 중복 저장 방지를 위해 현재 대상 직원의 이번 주 데이터 및 PENDING 행 분리 제거
                rows_to_keep = [headers]
                if len(all_values) > 1:
                    for row in all_values[1:]:
                        if len(row) < 6: continue
                        if row[1] in target_ids and (row[2] == target_week or row[2] == 'PENDING'):
                            continue
                        rows_to_keep.append(row)

                # 새로운 입력값 구조화 (Melt)
                new_rows = []
                for emp_name in target_employees:
                    final_df = all_edited_dfs.get(emp_name)
                    emp_id = str(df_emp[df_emp['성명'] == emp_name]['직원ID'].values[0])

                    for i, cat in enumerate(cat_order):
                        for day in day_order:
                            clean_cat = cat.split(' (')[0].replace('📌 ', '')
                            content = str(final_df.iloc[i][day])
                            
                            row_date = 'PENDING' if clean_cat == '펜딩 업무' else target_week
                            new_row = [f"{emp_id}_{row_date}_{clean_cat}_{day}", emp_id, row_date, day, clean_cat, content]
                            new_rows.append(new_row)
                
                # 일괄 청소 후 업데이트 
                sheet_r.clear()
                sheet_r.append_rows(rows_to_keep + new_rows)
                
                st.success("✅ 주간 보고 및 펜딩 업무 데이터가 안전하게 동기화되었습니다!")
                time.sleep(1)
                st.cache_data.clear()
                st.rerun()
                
            except Exception as e:
                st.error(f"저장 중 오류 발생: {e}")
