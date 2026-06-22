import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
import time
import json
import gspread
from oauth2client.service_account import ServiceAccountCredentials

from utils import custom_fullscreen_spinner

# 1. 시트 연결 함수
def get_worksheet_for_write(sheet_name):
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    creds_dict = json.loads(st.secrets["gcp_service_account"])
    creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
    client = gspread.authorize(creds)
    doc = client.open("통합재고관리")
    return doc.worksheet(sheet_name)

def get_week_info(date_obj):
    # 월요일과 금요일 날짜 계산
    monday = date_obj - timedelta(days=date_obj.weekday())
    friday = monday + timedelta(days=4)
    
    # "5월 10일 ~ 5월 14일" 형태로 직관적인 텍스트 생성
    mon_str = f"{monday.month}월 {monday.day}일"
    fri_str = f"{friday.month}월 {friday.day}일"
    
    label = f"{mon_str} ~ {fri_str}"
    value = monday.strftime('%Y-%m-%d')
    
    return label, value

# 2. 메인 실행 함수
def run(load_sheet_data):
    try:
        with open('style.css', encoding='utf-8') as f:
            st.markdown(f'<style>{f.read()}</style>', unsafe_allow_html=True)
    except: pass
        
    st.markdown("<h1>업무 보고</h1>", unsafe_allow_html=True)
    
    with custom_fullscreen_spinner("보고 데이터 로딩..."):
        df_emp_raw = load_sheet_data("Employees")
        df_report = load_sheet_data("WorkReports")
        
        if df_emp_raw is None or df_report is None:
            st.error("데이터 로드 실패")
            return

        # 🚀 [핵심 추가] '업무보고' 열이 'Y'인 직원만 필터링 (대소문자, 공백 무시)
        if '업무보고' in df_emp_raw.columns:
            df_emp = df_emp_raw[df_emp_raw['업무보고'].astype(str).str.strip().str.upper() == 'Y'].copy()
        else:
            # 혹시 시트 연동 지연으로 열이 안 보일 경우를 대비한 안전 장치
            st.warning("⚠️ Employees 시트에 '업무보고' 열이 존재하지 않아 전체 직원을 표시합니다.")
            df_emp = df_emp_raw.copy()

        # 만약 Y인 직원이 한 명도 없다면 안내문 띄우고 종료
        if df_emp.empty:
            st.info("💡 업무 보고 대상자가 없습니다. [Employees] 시트의 '업무보고' 열을 'Y'로 설정해 주세요.")
            return

        # --- 사이드바 설정 ---
        today = datetime.today()
        week_options = {}
        weeks_list = []
        default_index = 0
        
        for i in range(-12, 5):
            lbl, val = get_week_info(target_d := today + timedelta(weeks=i))
            week_options[lbl] = val
            weeks_list.append(lbl)
            if i == 0: default_index = len(weeks_list) - 1

        selected_week_label = st.sidebar.selectbox("기준 주차 선택", weeks_list, index=default_index)
        target_week = week_options[selected_week_label]
        monday = datetime.strptime(target_week, "%Y-%m-%d")

        history_weeks = st.sidebar.slider("조회 범위", min_value=1, max_value=5, value=1)

        # 🚀 이제 드롭다운(emp_names)에는 'Y'인 직원들만 나타납니다!
        emp_names = ["전체"] + df_emp['성명'].tolist()
        selected_emp = st.sidebar.selectbox("직원 선택", emp_names)
        target_employees = df_emp['성명'].tolist() if selected_emp == "전체" else [selected_emp]

        all_edited_data = {}
        all_pending_inputs = {}

        rows_map = []
        for i in range(history_weeks, 0, -1):
            curr_mon = monday - timedelta(weeks=i-1)
            curr_week_str = curr_mon.strftime("%Y-%m-%d")
            
            last_mon = curr_mon - timedelta(weeks=1)
            last_range = f"({last_mon.strftime('%m/%d')}~{(last_mon+timedelta(days=4)).strftime('%m/%d')})"
            curr_range = f"({curr_mon.strftime('%m/%d')}~{(curr_mon+timedelta(days=4)).strftime('%m/%d')})"
            
            if i > 1:
                rows_map.append({'db_week': curr_week_str, 'db_cat': '저번주 할일', 'display_cat': f'{i}주전 한일<br><span style="font-size:0.8em; color:gray;">{last_range}</span>'})
                rows_map.append({'db_week': curr_week_str, 'db_cat': '결과', 'display_cat': f'{i}주전 결과'})
            else:
                rows_map.append({'db_week': curr_week_str, 'db_cat': '저번주 할일', 'display_cat': f'저번주 한일<br><span style="font-size:0.8em; color:gray;">{last_range}</span>'})
                rows_map.append({'db_week': curr_week_str, 'db_cat': '결과', 'display_cat': '결과'})
                rows_map.append({'db_week': curr_week_str, 'db_cat': '이번주 할일', 'display_cat': f'이번주 할일<br><span style="font-size:0.8em; color:gray;">{curr_range}</span>'})

        # 🚀 '전체'를 선택해도 'Y'인 직원들의 데이터만 조회 및 표시됩니다.
        for emp_name in target_employees:
            target_id = str(df_emp[df_emp['성명'] == emp_name]['직원ID'].values[0])
            
            subset_all = df_report[df_report['직원ID'].astype(str).str.strip() == target_id]
            emp_data_dict = {}
            for _, row in subset_all.iterrows():
                emp_data_dict[(str(row['보고일자']).strip(), str(row['분류']).strip(), str(row['요일']).strip())] = row['내용']

            st.markdown(f"---")
            st.subheader(f"👤 {emp_name} | {selected_week_label}")
            
            all_edited_data[emp_name] = {}
            
            header_cols = st.columns([1.2, 2, 2, 2, 2, 2])
            header_cols[0].markdown("<div style='text-align:center; font-size: 1.2rem; color: #2E86C1; padding:10px 0;'>구분</div>", unsafe_allow_html=True)
            for idx, day in enumerate(['월', '화', '수', '목', '금']):
                header_cols[idx+1].markdown(f"<div style='text-align:center; font-size: 1.2rem; color: #2E86C1; padding:10px 0;'>{day}</div>", unsafe_allow_html=True)

            for r in rows_map:
                cols = st.columns([1.5, 2, 2, 2, 2, 2])
                
                row_vals = []
                for day in ['월', '화', '수', '목', '금']:
                    val = emp_data_dict.get((r['db_week'], r['db_cat'], day), "")
                    if val == "" and r['db_cat'] == '저번주 할일':
                        prev_w = (datetime.strptime(r['db_week'], "%Y-%m-%d") - timedelta(weeks=1)).strftime("%Y-%m-%d")
                        val = emp_data_dict.get((prev_w, '이번주 할일', day), "")
                    row_vals.append(val)
                    
                max_lines = 3 
                for v in row_vals:
                    lines = 0
                    for line in v.split('\n'):
                        lines += 1 + (len(line) // 15)
                    if lines > max_lines: 
                        max_lines = lines
                        
                row_height = max_lines * 28 + 20 
                
                pad_top = max(10, row_height // 2 - 20)
                cols[0].markdown(f"<div style='padding-top:{pad_top}px; font-size: 1.1rem; color: #333333;'>{r['display_cat']}</div>", unsafe_allow_html=True)
                
                for idx, day in enumerate(['월', '화', '수', '목', '금']):
                    val = row_vals[idx]
                    ta_key = f"ta_{emp_name}_{r['db_week']}_{r['db_cat']}_{day}"
                    new_val = cols[idx+1].text_area("hidden", value=val, key=ta_key, label_visibility="collapsed", height=row_height)
                    all_edited_data[emp_name][(r['db_week'], r['db_cat'], day)] = new_val

            pending_text = emp_data_dict.get(('PENDING', '펜딩 업무', '공통'), "")
            
            p_lines = 0
            for line in pending_text.split('\n'):
                p_lines += 1 + (len(line) // 80) 
            p_height = max(120, p_lines * 28 + 20)
            
            st.markdown("<div style='font-size: 1.1rem; font-weight: bold; color: #333333; margin-top: 15px; margin-bottom: 5px;'>📌 펜딩 업무</div>", unsafe_allow_html=True)
            
            pending_input = st.text_area("hidden_pending", value=pending_text, key=f"pending_{emp_name}", label_visibility="collapsed", height=p_height)
            
            # -----------------------------------------------------------------
            # 💾 일괄 통합 저장 로직 (직원 섹션별 버튼 배치)
            # -----------------------------------------------------------------
            if st.button("💾 변경사항 저장", key=f"save_btn_{emp_name}", use_container_width=True):
                with custom_fullscreen_spinner("데이터베이스에 저장..."):
                    try:
                        sheet_r = get_worksheet_for_write("WorkReports")
                        all_values = sheet_r.get_all_values()
                        headers = all_values[0] if all_values else ['보고ID', '직원ID', '보고일자', '요일', '분류', '내용']
                        
                        target_ids = [str(df_emp[df_emp['성명'] == name]['직원ID'].values[0]) for name in target_employees]
                        loaded_weeks = list(set([r_map['db_week'] for r_map in rows_map]))
                        
                        rows_to_keep = [headers]
                        if len(all_values) > 1:
                            for row in all_values[1:]:
                                if len(row) < 6: continue
                                if row[1] in target_ids and (row[2] in loaded_weeks or row[2] == 'PENDING'):
                                    continue
                                rows_to_keep.append(row)

                        new_rows = []
                        for name in target_employees:
                            emp_id = str(df_emp[df_emp['성명'] == name]['직원ID'].values[0])

                            for r_map in rows_map:
                                db_w, db_c = r_map['db_week'], r_map['db_cat']
                                for day in ['월', '화', '수', '목', '금']:
                                    ta_key = f"ta_{name}_{db_w}_{db_c}_{day}"
                                    content = str(st.session_state.get(ta_key, ""))
                                    if content.strip() != "":
                                        new_rows.append([f"{emp_id}_{db_w}_{db_c}_{day}", emp_id, db_w, day, db_c, content])
                                
                            p_key = f"pending_{name}"
                            p_text = str(st.session_state.get(p_key, ""))
                            if p_text.strip() != "":
                                new_rows.append([f"{emp_id}_PENDING_공통", emp_id, 'PENDING', '공통', '펜딩 업무', p_text])
                        
                        sheet_r.clear()
                        sheet_r.append_rows(rows_to_keep + new_rows)
                        
                        st.success("저장되었습니다!")
                        time.sleep(1)
                        st.cache_data.clear()
                        st.rerun()
                        
                    except Exception as e:
                        st.error(f"저장 중 오류 발생: {e}")
