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

    # --- 사이드바 설정 ---
    st.sidebar.markdown("### 📅 기준 주차 선택")
    today = datetime.today()
    week_options = {}
    weeks_list = []
    default_index = 0
    
    for i in range(-12, 5):
        lbl, val = get_week_info(target_d := today + timedelta(weeks=i))
        week_options[lbl] = val
        weeks_list.append(lbl)
        if i == 0: default_index = len(weeks_list) - 1

    selected_week_label = st.sidebar.selectbox("주차를 선택하세요", weeks_list, index=default_index)
    target_week = week_options[selected_week_label]
    monday = datetime.strptime(target_week, "%Y-%m-%d")

    # 🚀 [추가] 과거 기록 조회 슬라이더
    st.sidebar.markdown("### 🔍 조회 범위")
    history_weeks = st.sidebar.slider("과거 기록 함께 보기 (주)", min_value=1, max_value=5, value=1)

    emp_names = ["전체"] + df_emp['성명'].tolist()
    selected_emp = st.sidebar.selectbox("직원 선택", emp_names)
    target_employees = df_emp['성명'].tolist() if selected_emp == "전체" else [selected_emp]

    all_edited_dfs = {}
    all_pending_inputs = {}

    # --- 테이블 행(Row) 맵핑 동적 생성 ---
    rows_map = []
    for i in range(history_weeks, 0, -1):
        curr_mon = monday - timedelta(weeks=i-1)
        curr_week_str = curr_mon.strftime("%Y-%m-%d")
        
        last_mon = curr_mon - timedelta(weeks=1)
        last_range = f"({last_mon.strftime('%m/%d')}~{(last_mon+timedelta(days=4)).strftime('%m/%d')})"
        curr_range = f"({curr_mon.strftime('%m/%d')}~{(curr_mon+timedelta(days=4)).strftime('%m/%d')})"
        
        if i > 1:
            rows_map.append({'db_week': curr_week_str, 'db_cat': '저번주 할일', 'display_cat': f'{i}주전 할일 {last_range}'})
            rows_map.append({'db_week': curr_week_str, 'db_cat': '결과', 'display_cat': f'{i}주전 결과'})
        else:
            rows_map.append({'db_week': curr_week_str, 'db_cat': '저번주 할일', 'display_cat': f'저번주 할일 {last_range}'})
            rows_map.append({'db_week': curr_week_str, 'db_cat': '결과', 'display_cat': '결과'})
            rows_map.append({'db_week': curr_week_str, 'db_cat': '이번주 할일', 'display_cat': f'이번주 할일 {curr_range}'})

    # 직원별 데이터 렌더링
    for emp_name in target_employees:
        target_id = str(df_emp[df_emp['성명'] == emp_name]['직원ID'].values[0])
        
        # 해당 직원의 모든 데이터(과거+현재+펜딩) 딕셔너리로 변환하여 속도 최적화
        subset_all = df_report[df_report['직원ID'].astype(str).str.strip() == target_id]
        emp_data_dict = {}
        for _, row in subset_all.iterrows():
            emp_data_dict[(str(row['보고일자']).strip(), str(row['분류']).strip(), str(row['요일']).strip())] = row['내용']

        # 🚀 [핵심] 다중 주차 그리드 데이터 조립 및 이월 자동화
        grid_data = []
        for r in rows_map:
            row_dict = {'구분': r['display_cat']}
            for day in ['월', '화', '수', '목', '금']:
                val = emp_data_dict.get((r['db_week'], r['db_cat'], day), "")
                
                # 자동 이월: '저번주 할일'이 비어있으면 이전 주의 '이번주 할일'을 가져옴
                if val == "" and r['db_cat'] == '저번주 할일':
                    prev_w = (datetime.strptime(r['db_week'], "%Y-%m-%d") - timedelta(weeks=1)).strftime("%Y-%m-%d")
                    val = emp_data_dict.get((prev_w, '이번주 할일', day), "")
                    
                row_dict[day] = val
            grid_data.append(row_dict)

        pivot_df = pd.DataFrame(grid_data)

        # 펜딩 업무 텍스트 로드
        pending_text = emp_data_dict.get(('PENDING', '펜딩 업무', '공통'), "")

        # --- UI 출력부 ---
        st.markdown(f"---")
        st.subheader(f"👤 {emp_name} 님 - {selected_week_label}")
        
        # 🚀 정렬 화살표 제거를 위한 컬럼 설정 (인덱스 숨김 + 첫 열 읽기전용)
        col_config = {
            "구분": st.column_config.TextColumn("구분", disabled=True, width="medium"),
            "월": st.column_config.TextColumn("월", width="large"),
            "화": st.column_config.TextColumn("화", width="large"),
            "수": st.column_config.TextColumn("수", width="large"),
            "목": st.column_config.TextColumn("목", width="large"),
            "금": st.column_config.TextColumn("금", width="large"),
        }
        
        edited_df = st.data_editor(
            pivot_df, 
            use_container_width=True, 
            hide_index=True, 
            column_config=col_config,
            key=f"editor_{emp_name}_{target_week}"
        )
        all_edited_dfs[emp_name] = edited_df

        # 🚀 펜딩 업무를 자유로운 텍스트 박스로 분리
        st.markdown("##### 📌 펜딩 업무 (상시)")
        pending_input = st.text_area("앞으로 해야 할 일 (자유롭게 엔터 사용 가능)", value=pending_text, key=f"pending_{emp_name}", height=120)
        all_pending_inputs[emp_name] = pending_input

    # -----------------------------------------------------------------
    # 💾 일괄 통합 저장
    # -----------------------------------------------------------------
    if st.button("💾 모든 변경사항 저장", use_container_width=True):
        with st.spinner("구글 시트에 동기화 중..."):
            try:
                sheet_r = get_worksheet_for_write("WorkReports")
                all_values = sheet_r.get_all_values()
                headers = all_values[0] if all_values else ['보고ID', '직원ID', '보고일자', '요일', '분류', '내용']
                
                target_ids = [str(df_emp[df_emp['성명'] == name]['직원ID'].values[0]) for name in target_employees]
                loaded_weeks = list(set([r['db_week'] for r in rows_map]))
                
                # 중복 방지 로직 (화면에 뜬 주차 + 펜딩 데이터만 필터링)
                rows_to_keep = [headers]
                if len(all_values) > 1:
                    for row in all_values[1:]:
                        if len(row) < 6: continue
                        if row[1] in target_ids and (row[2] in loaded_weeks or row[2] == 'PENDING'):
                            continue
                        rows_to_keep.append(row)

                # 그리드 + 펜딩 입력값 병합
                new_rows = []
                for emp_name in target_employees:
                    final_df = all_edited_dfs[emp_name]
                    emp_id = str(df_emp[df_emp['성명'] == emp_name]['직원ID'].values[0])

                    # 그리드 데이터
                    for i, r in enumerate(rows_map):
                        db_w, db_c = r['db_week'], r['db_cat']
                        for day in ['월', '화', '수', '목', '금']:
                            content = str(final_df.iloc[i][day])
                            if content.strip() != "":
                                new_rows.append([f"{emp_id}_{db_w}_{db_c}_{day}", emp_id, db_w, day, db_c, content])
                    
                    # 펜딩 데이터
                    p_text = all_pending_inputs[emp_name]
                    if p_text.strip() != "":
                        new_rows.append([f"{emp_id}_PENDING_공통", emp_id, 'PENDING', '공통', '펜딩 업무', p_text])
                
                sheet_r.clear()
                sheet_r.append_rows(rows_to_keep + new_rows)
                
                st.success("✅ 주간 보고 및 펜딩 업무가 완벽하게 저장되었습니다!")
                time.sleep(1)
                st.cache_data.clear()
                st.rerun()
                
            except Exception as e:
                st.error(f"저장 중 오류 발생: {e}")
