import streamlit as st
import pandas as pd
import numpy as np
import altair as alt
import datetime
import json
import gspread
from oauth2client.service_account import ServiceAccountCredentials

def run(load_data_func):
    st.title("🏆 영업 실적 분석")
    st.markdown("직원별 목표 달성률(%)과 상세 실적을 확인합니다.")

    # 1. 데이터 로드 (시트가 없으면 자동으로 빈 데이터 생성)
    try:
        df_target = load_data_func("sales_target")
        if df_target is None or df_target.empty:
            df_target = pd.DataFrame(columns=["직원명", "연간목표액"])
    except:
        df_target = pd.DataFrame(columns=["직원명", "연간목표액"])

    try:
        df_record = load_data_func("sales_record_emp")
        if df_record is None or df_record.empty:
            df_record = pd.DataFrame(columns=["입력월", "직원명", "실적금액"])
    except:
        df_record = pd.DataFrame(columns=["입력월", "직원명", "실적금액"])

    df_target['연간목표액'] = pd.to_numeric(df_target['연간목표액'].astype(str).str.replace(',', ''), errors='coerce').fillna(0)
    df_record['실적금액'] = pd.to_numeric(df_record['실적금액'].astype(str).str.replace(',', ''), errors='coerce').fillna(0)

    # ==========================================
    # 🚀 2. 데이터 입력 패널
    # ==========================================
    with st.expander("✍️ 목표 및 월별 실적 입력 패널 열기", expanded=False):
        c1, c2 = st.columns(2)
        
        with c1:
            st.markdown("#### 🎯 연간 목표 설정")
            t_emp = st.text_input("직원 이름")
            t_amt = st.number_input("연간 목표액 (원)", min_value=0, step=1000000, format="%d")
            if st.button("목표 저장", use_container_width=True):
                if t_emp:
                    if t_emp in df_target['직원명'].values:
                        df_target.loc[df_target['직원명'] == t_emp, '연간목표액'] = t_amt
                    else:
                        new_row = pd.DataFrame([{"직원명": t_emp, "연간목표액": t_amt}])
                        df_target = pd.concat([df_target, new_row], ignore_index=True)
                    
                    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
                    creds_dict = json.loads(st.secrets["gcp_service_account"])
                    creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
                    client = gspread.authorize(creds)
                    doc = client.open("통합재고관리")
                    try: sheet = doc.worksheet("sales_target")
                    except: sheet = doc.add_worksheet(title="sales_target", rows="100", cols="5")
                    sheet.clear()
                    sheet.update([df_target.columns.values.tolist()] + df_target.astype(str).values.tolist())
                    
                    st.cache_data.clear()
                    st.success(f"✅ {t_emp}님의 목표가 저장되었습니다.")
                    st.rerun()
                else:
                    st.warning("직원 이름을 입력하세요.")

        with c2:
            st.markdown("#### 📈 월별 실적 입력")
            emp_list = df_target['직원명'].tolist()
            r_emp = st.selectbox("직원 선택 (목표가 등록된 직원)", ["선택하세요"] + emp_list)
            r_month = st.text_input("해당 월 (YYYY-MM 형식)", value=datetime.date.today().strftime("%Y-%m"))
            r_amt = st.number_input("해당 월 실적액 (원)", min_value=0, step=1000000, format="%d")
            
            if st.button("실적 저장", use_container_width=True):
                if r_emp != "선택하세요" and r_month:
                    mask = (df_record['직원명'] == r_emp) & (df_record['입력월'] == r_month)
                    if mask.any():
                        df_record.loc[mask, '실적금액'] = r_amt
                    else:
                        new_row = pd.DataFrame([{"입력월": r_month, "직원명": r_emp, "실적금액": r_amt}])
                        df_record = pd.concat([df_record, new_row], ignore_index=True)
                    
                    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
                    creds_dict = json.loads(st.secrets["gcp_service_account"])
                    creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
                    client = gspread.authorize(creds)
                    doc = client.open("통합재고관리")
                    try: sheet = doc.worksheet("sales_record_emp")
                    except: sheet = doc.add_worksheet(title="sales_record_emp", rows="1000", cols="5")
                    sheet.clear()
                    sheet.update([df_record.columns.values.tolist()] + df_record.astype(str).values.tolist())
                    
                    st.cache_data.clear()
                    st.success(f"✅ {r_emp}님의 {r_month} 실적이 저장되었습니다.")
                    st.rerun()
                else:
                    st.warning("직원과 입력월을 정확히 선택해주세요.")

    st.markdown("---")

    if df_target.empty:
        st.info("👆 위 패널을 열어 직원별 [연간 목표액]을 먼저 설정해 주세요.")
        return

    # ==========================================
    # 🚀 3. 날짜 기준 세팅 (연간/분기/월간)
    # ==========================================
    today = datetime.date.today()
    curr_y = str(today.year)
    curr_m = today.month
    curr_q = (curr_m - 1) // 3 + 1

    df_record['연도'] = df_record['입력월'].str[:4]
    df
