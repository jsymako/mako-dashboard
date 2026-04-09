import streamlit as st
import pandas as pd
import altair as alt
import datetime
import json
import gspread
from oauth2client.service_account import ServiceAccountCredentials

def run(load_data_func):
    st.title("🏆 영업 실적 분석")
    st.markdown("직원별 목표 달성률과 분기별 실적 추이를 확인합니다.")

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

    # 숫자형 변환
    df_target['연간목표액'] = pd.to_numeric(df_target['연간목표액'].astype(str).str.replace(',', ''), errors='coerce').fillna(0)
    df_record['실적금액'] = pd.to_numeric(df_record['실적금액'].astype(str).str.replace(',', ''), errors='coerce').fillna(0)

    # ==========================================
    # 🚀 2. 데이터 입력 패널 (대시보드 내 직접 입력)
    # ==========================================
    with st.expander("✍️ 목표 및 월별 실적 입력 패널 열기", expanded=False):
        c1, c2 = st.columns(2)
        
        with c1:
            st.markdown("<div class='col-title'>🎯 연간 목표 설정</div>", unsafe_allow_html=True)
            t_emp = st.text_input("직원 이름")
            t_amt = st.number_input("연간 목표액 (원)", min_value=0, step=1000000, format="%d")
            if st.button("목표 저장", use_container_width=True):
                if t_emp:
                    # 기존에 있는 직원이면 덮어쓰기, 없으면 새로 추가
                    if t_emp in df_target['직원명'].values:
                        df_target.loc[df_target['직원명'] == t_emp, '연간목표액'] = t_amt
                    else:
                        new_row = pd.DataFrame([{"직원명": t_emp, "연간목표액": t_amt}])
                        df_target = pd.concat([df_target, new_row], ignore_index=True)
                    
                    # 구글 시트 저장
                    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
                    creds_dict = json.loads(st.secrets["gcp_service_account"])
                    creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
                    client = gspread.authorize(creds)
                    doc = client.open("통합재고관리")
                    try:
                        sheet = doc.worksheet("sales_target")
                    except:
                        sheet = doc.add_worksheet(title="sales_target", rows="100", cols="5")
                    sheet.clear()
                    sheet.update([df_target.columns.values.tolist()] + df_target.astype(str).values.tolist())
                    st.cache_data.clear()
                    st.success(f"✅ {t_emp}님의 목표가 저장되었습니다.")
                    st.rerun()
                else:
                    st.warning("직원 이름을 입력하세요.")

        with c2:
            st.markdown("<div class='col-title'>📈 월별 실적 입력</div>", unsafe_allow_html=True)
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
                    
                    # 구글 시트 저장
                    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
                    creds_dict = json.loads(st.secrets["gcp_service_account"])
                    creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
                    client = gspread.authorize(creds)
                    doc = client.open("통합재고관리")
                    try:
                        sheet = doc.worksheet("sales_record_emp")
                    except:
                        sheet = doc.add_worksheet(title="sales_record_emp", rows="1000", cols="5")
                    sheet.clear()
                    sheet.update([df_record.columns.values.tolist()] + df_record.astype(str).values.tolist())
                    st.cache_data.clear()
                    st.success(f"✅ {r_emp}님의 {r_month} 실적이 저장되었습니다.")
                    st.rerun()
                else:
                    st.warning("직원과 입력월을 정확히 선택해주세요.")

    st.markdown("---")

    # 3. 방어 로직 (데이터가 비어있을 때)
    if df_target.empty:
        st.info("👆 위 패널을 열어 직원별 [연간 목표액]을 먼저 설정해 주세요.")
        return

    # ==========================================
    # 🚀 4. 실적 데이터 가공 및 KPI
    # ==========================================
    df_record['연도'] = df_record['입력월'].str[:4]
    df_record['월'] = pd.to_numeric(df_record['입력월'].str[5:7], errors='coerce').fillna(0).astype(int)
    
    years = sorted(df_record['연도'].dropna().unique().tolist(), reverse=True)
    if not years:
        years = [str(datetime.date.today().year)]
    
    sel_year = st.sidebar.selectbox("📅 조회 연도", years)
    df_curr_year = df_record[df_record['연도'] == sel_year].copy()

    # (1) 직원별 가공
    emp_actual = df_curr_year.groupby('직원명')['실적금액'].sum().reset_index()
    emp_merged = pd.merge(df_target, emp_actual, on='직원명', how='left').fillna(0)
    emp_merged['달성률(%)'] = (emp_merged['실적금액'] / emp_merged['연간목표액'] * 100).fillna(0).round(1)

    # (2) 분기별 가공
    total_annual_target = df_target['연간목표액'].sum()
    q_target = total_annual_target / 4  # 분기별 목표는 연간목표의 1/4

    def get_quarter(month):
        if 1 <= month <= 3: return '1분기'
        elif 4 <= month <= 6: return '2분기'
        elif 7 <= month <= 9: return '3분기'
        elif 10 <= month <= 12: return '4분기'
        else: return '기타'

    df_curr_year['분기'] = df_curr_year['월'].apply(get_quarter)
    q_actual = df_curr_year.groupby('분기')['실적금액'].sum().reset_index()

    q_frame = pd.DataFrame({'분기': ['1분기', '2분기', '3분기', '4분기']})
    q_merged = pd.merge(q_frame, q_actual, on='분기', how='left').fillna(0)
    q_merged['목표금액'] = q_target

    # 상단 KPI 지표
    c1, c2, c3 = st.columns(3)
    c1.metric("🎯 전사 연간 목표액", f"{int(total_annual_target/10000):,}만 원")
    c2.metric("💰 현재 누적 실적액", f"{int(emp_merged['실적금액'].sum()/10000):,}만 원")
    
    total_rate = (emp_merged['실적금액'].sum() / total_annual_target * 100) if total_annual_target > 0 else 0
    c3.metric("🔥 전체 달성률", f"{total_rate:.1f}%")
    st.markdown("<br>", unsafe_allow_html=True)

    # ==========================================
    # 🚀 5. 교차 시각화 (직원별 vs 분기별)
    # ==========================================
    col1, col2 = st.columns(2)

    with col1:
        st.subheader("🧑‍💼 직원별 목표 대비 실적")
        emp_melt = emp_merged[['직원명', '연간목표액', '실적금액']].melt(id_vars='직원명', var_name='구분', value_name='금액')
        
        # 목표바와 실적바를 나란히 보여주는 그룹형 차트
        emp_chart = alt.Chart(emp_melt).mark_bar(cornerRadiusTop=5).encode(
            x=alt.X('구분:N', title='', axis=alt.Axis(labels=False, ticks=False)), # 세부 그룹 축 숨기기
            y=alt.Y('금액:Q', title='금액(원)'),
            color=alt.Color('구분:N', scale=alt.Scale(domain=['연간목표액', '실적금액'], range=['#D5DBDB', '#2E86C1']), legend=alt.Legend(title="구분", orient='top-left')),
            column=alt.Column('직원명:N', header=alt.Header(title="", labelFontSize=14, labelPadding=10)),
            tooltip=['직원명', '구분', alt.Tooltip('금액:Q', format=',')]
        ).properties(width=80, height=350)
        
        st.altair_chart(emp_chart, use_container_width=False)

    with col2:
        st.subheader("📅 분기별 목표 대비 실적")
        q_melt = q_merged.melt(id_vars='분기', var_name='구분', value_name='금액')
        
        q_chart = alt.Chart(q_melt).mark_bar(cornerRadiusTop=5).encode(
            x=alt.X('구분:N', title='', axis=alt.Axis(labels=False, ticks=False)),
            y=alt.Y('금액:Q', title='금액(원)'),
            color=alt.Color('구분:N', scale=alt.Scale(domain=['목표금액', '실적금액'], range=['#FADBD8', '#E74C3C']), legend=alt.Legend(title="구분", orient='top-left')),
            column=alt.Column('분기:N', header=alt.Header(title="", labelFontSize=14, labelPadding=10)),
            tooltip=['분기', '구분', alt.Tooltip('금액:Q', format=',')]
        ).properties(width=80, height=350)
        
        st.altair_chart(q_chart, use_container_width=False)
        
    st.markdown("---")
    st.markdown("### 📋 직원별 상세 달성률 현황")
    st.dataframe(emp_merged[['직원명', '연간목표액', '실적금액', '달성률(%)']].style.format({'연간목표액': '{:,.0f}', '실적금액': '{:,.0f}', '달성률(%)': '{:.1f}%'}), use_container_width=True)
