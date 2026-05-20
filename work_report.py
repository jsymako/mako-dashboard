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
    cat_order = ['저번주 할일', '결과', '이번주 할일', '펜딩 업무'] # 🚀 펜딩 업무 추가

    # 직원별 순회하며 표 그리기
    for emp_name in target_employees:
        target_id = str(df_emp[df_emp['성명'] == emp_name]['직원ID'].values[0])
        
        # 🚀 [데이터 결합] 해당 주차 데이터 + 상시 펜딩 업무(PENDING) 데이터 로드
        df_report['보고일자'] = df_report['보고일자'].astype(str).str.strip()
        df_report['직원ID'] = df_report['직원ID'].astype(str).str.strip()
        
        subset_week = df_report[(df_report['보고일자'] == target_week) & (df_report['직원ID'] == target_id)]
        subset_pending = df_report[(df_report['보고일자'] == 'PENDING') & (df_report['직원ID'] == target_id)]
        subset = pd.concat([subset_week, subset_pending])
        
        # 날짜 구간 텍스트 계산
        last_monday = monday - timedelta(days=7)
        last_week_range = f"({last_monday.strftime('%m/%d')} ~ {(last_monday + timedelta(days=4)).strftime('%m/%d')})"
        this_week_range = f"({monday.strftime('%m/%d')} ~ {(monday + timedelta(days=4)).strftime('%m/%d')})"
        
        if subset.empty:
            pivot_df = pd.DataFrame("", index=cat_order, columns=day_order)
        else:
            pivot_df = subset.pivot(index='분류', columns='요일', values='내용')
            pivot_df = pivot_df.reindex(index=cat_order, columns=day_order).fillna("")

        # 화면 표기용 라벨 바꿈
        cat_mapping = {
            '저번주 할일': f'저번주 할일 {last_week_range}',
            '이번주 할일': f'이번주 할일 {this_week_range}',
            '펜딩 업무': '📌 펜딩 업무 (상시)'
        }
        pivot_df = pivot_df.rename(index=cat_mapping)

        st.markdown(f"---")
        st.subheader(f"👤 {emp_name} 님 - {selected_week_label}")
        
        # 편집기 생성 및 결과 보관
        edited_df = st.data_editor(pivot_df, use_container_width=True, key=f"editor_{emp_name}_{target_week}")
        all_edited_dfs[emp_name] = edited_df

    # -----------------------------------------------------------------
    # 💾 중복 방지 및 통합 저장 로직 (중요)
    # -----------------------------------------------------------------
    if st.button("💾 모든 변경사항 저장", use_container_width=True):
        with st.spinner("구글 시트에 안전하게 저장 중..."):
            try:
                sheet_r = get_worksheet_for_write("WorkReports")
                
                # 1. 시트의 기존 데이터 전체 확보
                all_values = sheet_r.get_all_values()
                headers = all_values[0] if all_values else ['보고ID', '직원ID', '보고일자', '요일', '분류', '내용']
                
                # 저장 대상 직원들의 ID 목록 생성
                target_ids = [str(df_emp[df_emp['성명'] == name]['직원ID'].values[0]) for name in target_employees]
                
                # 2. 기존 데이터 중 [현재 주차 데이터]와 [PENDING 데이터]를 필터링하여 제외 (덮어쓰기 효과)
                rows_to_keep = [headers]
                if len(all_values) > 1:
                    for row in all_values[1:]:
                        if len(row) < 6: continue
                        # 대상 직원의 이번 주차 데이터이거나 PENDING 데이터이면 덮어써야 하므로 제외
                        if row[1] in target_ids and (row[2] == target_week or row[2] == 'PENDING'):
                            continue
                        rows_to_keep.append(row)

                # 3. 에디터에서 수정된 새로운 행 데이터 구성
                new_rows = []
                for emp_name in target_employees:
                    final_df = all_edited_dfs.get(emp_name)
                    emp_id = str(df_emp[df_emp['성명'] == emp_name]['직원ID'].values[0])

                    for i, cat in enumerate(cat_order):
                        for day in day_order:
                            clean_cat = cat.split(' (')[0].replace('📌 ', '')
                            content = str(final_df.iloc[i][day])
                            
                            # 🚀 펜딩 업무는 보고일자를 'PENDING'으로 고정 저장
                            row_date = 'PENDING' if clean_cat == '펜딩 업무' else target_week
                            
                            new_row = [f"{emp_id}_{row_date}_{clean_cat}_{day}", emp_id, row_date, day, clean_cat, content]
                            new_rows.append(new_row)
                
                # 4. 시트 완전히 밀고 새로 합쳐서 쓰기 (중복 원천 차단 및 저장 신뢰도 100%)
                sheet_r.clear()
                sheet_r.append_rows(rows_to_keep + new_rows)
                
                st.success("✅ 주간 보고 및 펜딩 업무가 성공적으로 동기화되었습니다!")
                time.sleep(1)
                st.cache_data.clear()
                st.rerun()
                
            except Exception as e:
                st.error(f"저장 중 오류 발생: {e}")
