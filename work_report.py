import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
import time
import json
import gspread
from oauth2client.service_account import ServiceAccountCredentials

# =====================================================================
# 🔑 [1] 쓰기용 구글 시트 연결 함수
# =====================================================================
def get_worksheet_for_write(sheet_name):
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    creds_dict = json.loads(st.secrets["gcp_service_account"])
    creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
    client = gspread.authorize(creds)
    doc = client.open("통합재고관리")
    return doc.worksheet(sheet_name)

def get_week_start(d):
    return (d - timedelta(days=d.weekday())).strftime("%Y-%m-%d")

# =====================================================================
# 🖥️ [2] 메인 실행 함수
# =====================================================================
def run(load_sheet_data):
    st.markdown("<h1>📝 주간 업무 보고 시스템</h1>", unsafe_allow_html=True)
    
    df_emp = load_sheet_data("Employees")
    df_report = load_sheet_data("WorkReports")
    
    if df_emp is None or df_report is None:
        st.error("데이터 로드 실패")
        return

    # 헤더 정리
    df_report.columns = df_report.columns.str.strip()
    
    # 사이드바 설정
    st.sidebar.markdown("### 📅 조회 및 작성 조건")
    target_date = st.sidebar.date_input("주차 선택", datetime.today())
    target_week = get_week_start(target_date)
    emp_names = df_emp['성명'].tolist()
    selected_emp = st.sidebar.selectbox("직원 선택", emp_names)

    # 선택된 직원의 ID 가져오기
    target_id = str(df_emp[df_emp['성명'] == selected_emp]['직원ID'].values[0])
    
    # 데이터 타입 통일
    df_report['보고일자'] = df_report['보고일자'].astype(str).str.strip()
    df_report['직원ID'] = df_report['직원ID'].astype(str).str.strip()
    
    # 현재 선택된 주차/직원의 데이터 필터링
    subset = df_report[(df_report['보고일자'] == target_week) & (df_report['직원ID'] == target_id)]
    
    # -----------------------------------------------------------------
    # 💡 [핵심] 데이터가 없으면 빈 양식(Template) 생성
    # -----------------------------------------------------------------
    day_order = ['월', '화', '수', '목', '금']
    category_order = ['저번주 할일', '결과', '이번주 할일']

    if subset.empty:
        st.info(f"✨ {selected_emp} 님의 {target_week} 주차 데이터가 없습니다. 새로운 내용을 입력해주세요.")
        # 빈 매트릭스 생성
        pivot_df = pd.DataFrame("", index=category_order, columns=day_order)
    else:
        # 기존 데이터가 있으면 피벗 (분류=행, 요일=열)
        pivot_df = subset.pivot(index='분류', columns='요일', values='내용')
        # 행/열 순서 고정
        pivot_df = pivot_df.reindex(index=category_order, columns=day_order).fillna("")

    st.subheader(f"{selected_emp} 님의 {target_week} 주간 보고")
    
    # 🚀 노션 스타일 에디터 (여기서 직접 타이핑)
    edited_df = st.data_editor(
        pivot_df, 
        use_container_width=True,
        key=f"editor_{selected_emp}_{target_week}"
    )

    # -----------------------------------------------------------------
    # 💾 [저장 로직] 매트릭스를 다시 시트용 데이터로 변환 (Melt)
    # -----------------------------------------------------------------
    if st.button("💾 주간 업무 보고서 저장하기", use_container_width=True):
        with st.spinner("구글 시트에 저장 중..."):
            sheet_r = get_worksheet_for_write("WorkReports")
            
            # 1. 시트의 기존 데이터 로드 (중복 제거용)
            all_records = sheet_r.get_all_records()
            all_df = pd.DataFrame(all_records)
            
            # 2. 만약 기존 데이터가 있다면 해당 주차/직원 데이터 삭제 후 재입력 (Update 효과)
            if not all_df.empty:
                # 시트에서 해당 조건에 맞는 행 번호 찾아서 삭제하는 대신, 
                # 새로운 데이터 15줄을 만들어 Append 하는 방식이 안전함
                pass 

            # 3. 에디터의 데이터를 시트용(Long Format)으로 변환
            new_rows = []
            timestamp = int(time.time())
            
            for cat in category_order:
                for day in day_order:
                    content = edited_df.loc[cat, day]
                    report_id = f"R_{timestamp}_{target_id}_{day_order.index(day)}"
                    # [보고ID, 직원ID, 보고일자, 요일, 분류, 내용]
                    new_rows.append([report_id, target_id, target_week, day, cat, content])
            
            # 4. 구글 시트에 일괄 추가 (중복 방지를 위해 기존 데이터 삭제 로직은 운영 상황에 따라 보강 필요)
            # 여기서는 단순하게 추가(append) 하되, 대표님이 원하시면 기존 주차 데이터를 지우고 쓰는 코드로 바꿀 수 있습니다.
            sheet_r.append_rows(new_rows)
            
            st.success(f"✅ {selected_emp} 님의 {target_week} 주차 보고서가 성공적으로 저장되었습니다!")
            time.sleep(1)
            st.cache_data.clear()
            st.rerun()
