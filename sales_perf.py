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
    st.markdown("직원별 목표 달성률(%)과 당월 및 분기 상세 실적을 확인합니다.")

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
    # 🚀 2. 데이터 입력 패널 (연/월 셀렉트 박스 적용)
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
            
            # 🚀 입력 방식을 텍스트(YYYY-MM)에서 연/월 셀렉트 박스로 변경
            today_date = datetime.date.today()
            col_y, col_m = st.columns(2)
            with col_y:
                r_year = st.selectbox("해당 연도", range(today_date.year - 2, today_date.year + 3), index=2)
            with col_m:
                r_month_num = st.selectbox("해당 월", range(1, 13), index=today_date.month - 1, format_func=lambda x: f"{x}월")
            
            # 합쳐서 YYYY-MM 형태로 내부 변환
            r_month = f"{r_year}-{r_month_num:02d}"
            
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
    df_record['월'] = pd.to_numeric(df_record['입력월'].str[5:7], errors='coerce').fillna(0).astype(int)
    df_record['분기'] = (df_record['월'] - 1) // 3 + 1

    df_y = df_record[df_record['연도'] == curr_y]
    df_q = df_y[df_y['분기'] == curr_q]
    df_m = df_y[df_y['월'] == curr_m]

    y_target_total = df_target['연간목표액'].sum()
    q_target_total = y_target_total / 4
    m_target_total = y_target_total / 12

    y_actual_total = df_y['실적금액'].sum()
    q_actual_total = df_q['실적금액'].sum()
    m_actual_total = df_m['실적금액'].sum()

    y_rate = (y_actual_total / y_target_total * 100) if y_target_total > 0 else 0
    q_rate = (q_actual_total / q_target_total * 100) if q_target_total > 0 else 0
    m_rate = (m_actual_total / m_target_total * 100) if m_target_total > 0 else 0

    # ==========================================
    # 🚀 4. 전사 KPI 상단 바 
    # ==========================================
    st.subheader(f"🎯 {curr_y}년 전사 목표 달성 현황")
    
    kpi_cols = st.columns(3)
    
    with kpi_cols[0]:
        with st.container(border=True):
            st.markdown("##### 📅 연간 누적")
            st.metric("목표액", f"{int(y_target_total/10000):,}만 원")
            st.metric("실적액", f"{int(y_actual_total/10000):,}만 원")
            st.markdown(f"<h3 style='color:#E74C3C; margin-top:0px;'>🔥 달성률 {y_rate:.1f}%</h3>", unsafe_allow_html=True)

    with kpi_cols[1]:
        with st.container(border=True):
            st.markdown(f"##### 📊 {curr_q}분기 누적")
            st.metric("목표액", f"{int(q_target_total/10000):,}만 원")
            st.metric("실적액", f"{int(q_actual_total/10000):,}만 원")
            st.markdown(f"<h3 style='color:#E74C3C; margin-top:0px;'>🔥 달성률 {q_rate:.1f}%</h3>", unsafe_allow_html=True)

    with kpi_cols[2]:
        with st.container(border=True):
            st.markdown(f"##### 📆 {curr_m}월 당월")
            st.metric("목표액", f"{int(m_target_total/10000):,}만 원")
            st.metric("실적액", f"{int(m_actual_total/10000):,}만 원")
            st.markdown(f"<h3 style='color:#E74C3C; margin-top:0px;'>🔥 달성률 {m_rate:.1f}%</h3>", unsafe_allow_html=True)

    st.markdown("---")

    # ==========================================
    # 🚀 5. 직원별 실적 가공 (당월 및 분기 분리)
    # ==========================================
    emp_df = df_target[['직원명', '연간목표액']].copy()
    emp_df['분기목표액'] = emp_df['연간목표액'] / 4
    emp_df['월간목표액'] = emp_df['연간목표액'] / 12
    
    # 월간/분기 실적 합산
    m_emp = df_m.groupby('직원명')['실적금액'].sum().reset_index().rename(columns={'실적금액': '월간실적액'})
    q_emp = df_q.groupby('직원명')['실적금액'].sum().reset_index().rename(columns={'실적금액': '분기실적액'})
    
    emp_df = pd.merge(emp_df, m_emp, on='직원명', how='left').fillna(0)
    emp_df = pd.merge(emp_df, q_emp, on='직원명', how='left').fillna(0)
    
    # 달성률(%) 계산
    emp_df['월간달성률'] = np.where(emp_df['월간목표액'] > 0, (emp_df['월간실적액'] / emp_df['월간목표액'] * 100), 0)
    emp_df['분기달성률'] = np.where(emp_df['분기목표액'] > 0, (emp_df['분기실적액'] / emp_df['분기목표액'] * 100), 0)

    # ==========================================
    # 🚀 6. 시각화 및 상세 데이터 표 (당월 vs 분기 분리 배치)
    # ==========================================
    def make_rate_chart(data, y_col, bar_color):
        rule = alt.Chart(pd.DataFrame({'y': [100]})).mark_rule(
            color='#E74C3C', strokeDash=[5, 5], strokeWidth=2
        ).encode(y='y:Q')

        base = alt.Chart(data).encode(
            x=alt.X('직원명:N', title='', axis=alt.Axis(labelAngle=0, labelFontSize=14)),
            y=alt.Y(f'{y_col}:Q', title='달성률 (%)', scale=alt.Scale(domain=[0, max(110, data[y_col].max() + 10)])),
            tooltip=['직원명', alt.Tooltip(f'{y_col}:Q', format='.1f', title='달성률(%)')]
        )
        bar = base.mark_bar(size=40, cornerRadiusEnd=5, color=bar_color, opacity=0.8)
        
        text = base.mark_text(
            align='center', baseline='bottom', dy=-5, fontSize=14, fontWeight='bold', color='#333'
        ).encode(text=alt.Text(f'{y_col}:Q', format='.1f'))
        
        return (bar + text + rule).properties(height=350)

    col_chart1, col_chart2 = st.columns(2)
    
    with col_chart1:
        st.subheader(f"🧑‍💼 당월({curr_m}월) 달성률 (%)")
        st.altair_chart(make_rate_chart(emp_df, '월간달성률', '#3498DB'), use_container_width=True)
        
        # 🚀 당월 그래프 바로 아래에 당월 데이터만 표출
        st.markdown(f"##### 📋 {curr_m}월 실적 상세")
        disp_m = emp_df[['직원명', '월간목표액', '월간실적액', '월간달성률']].copy()
        st.dataframe(disp_m.style.format({
            '월간목표액': '{:,.0f} 원',
            '월간실적액': '{:,.0f} 원',
            '월간달성률': '{:.1f} %'
        }), use_container_width=True)

    with col_chart2:
        st.subheader(f"📅 {curr_q}분기 달성률 (%)")
        st.altair_chart(make_rate_chart(emp_df, '분기달성률', '#27AE60'), use_container_width=True)
        
        # 🚀 분기 그래프 바로 아래에 분기 데이터만 표출
        st.markdown(f"##### 📋 {curr_q}분기 실적 상세")
        disp_q = emp_df[['직원명', '분기목표액', '분기실적액', '분기달성률']].copy()
        st.dataframe(disp_q.style.format({
            '분기목표액': '{:,.0f} 원',
            '분기실적액': '{:,.0f} 원',
            '분기달성률': '{:.1f} %'
        }), use_container_width=True)
