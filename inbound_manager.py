import streamlit as st
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import json
from datetime import datetime
import time

# =====================================================================
# 🔑 [1] 쓰기/수정용 구글 시트 연결 (st.secrets 사용)
# =====================================================================
def get_worksheet_for_write(sheet_name):
    """데이터를 추가하거나 수정할 때 사용할 구글 시트 객체를 불러옵니다."""
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    creds_dict = json.loads(st.secrets["gcp_service_account"])
    creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
    client = gspread.authorize(creds)
    doc = client.open("통합재고관리")
    return doc.worksheet(sheet_name)

# =====================================================================
# 🚀 [2] 입력 및 수정 팝업 모달창 (st.dialog)
# =====================================================================
@st.dialog("📦 컨테이너 정보 관리")
def container_form_dialog(mode="add", container_data=None, df_m=None):
    st.write(f"### {'✨ 신규 컨테이너 등록' if mode=='add' else '📝 컨테이너 정보 수정'}")
    
    # 제조사 선택 리스트 구성
    m_options = {str(row['제조사명']): str(row['제조사ID']) for _, row in df_m.iterrows()}
    
    with st.form("container_form", clear_on_submit=True):
        # 1. 제조사 선택
        default_m_idx = 0
        if mode == "edit" and container_data is not None:
            current_m_id = str(container_data['제조사ID'])
            current_m_name = [name for name, m_id in m_options.items() if m_id == current_m_id]
            if current_m_name:
                default_m_idx = list(m_options.keys()).index(current_m_name[0])
                
        selected_m_name = st.selectbox("제조사 선택", list(m_options.keys()), index=default_m_idx)
        chosen_m_id = m_options[selected_m_name]
        
        # 2. 정보 입력
        cha_su = st.number_input("차수", min_value=1, value=int(container_data.get('차수', 1)) if mode=='edit' else 1)
        
        def safe_date_parse(date_str):
            try: return datetime.strptime(str(date_str).strip(), "%Y-%m-%d").date()
            except: return datetime.today().date()

        order_d = st.date_input("발주일", safe_date_parse(container_data['발주일']) if mode=='edit' else datetime.today())
        dept_d = st.date_input("출항일", safe_date_parse(container_data['출항일']) if mode=='edit' else datetime.today())
        arr_d = st.date_input("입항일", safe_date_parse(container_data['입항일']) if mode=='edit' else datetime.today())
        
        # 입고일 처리 (체크박스)
        has_inbound_date = True
        init_inbound_val = datetime.today().date()
        if mode == "edit":
            if not container_data['입고일'] or str(container_data['입고일']).strip() == "":
                has_inbound_date = False
            else:
                init_inbound_val = safe_date_parse(container_data['입고일'])
                
        is_inbound_checked = st.checkbox("✅ 입고 완료 (입고일 지정)", value=has_inbound_date)
        inbound_d = st.date_input("입고일", init_inbound_val if is_inbound_checked else None, disabled=not is_inbound_checked)
        
        summary = st.text_input("적요", value=str(container_data.get('적요', '')) if mode=='edit' else "")
        feet = st.selectbox("피트 (FT)", ["20FT", "40FT", "40HQ", "기타"], index=["20FT", "40FT", "40HQ", "기타"].index(str(container_data.get('피트', '20FT'))) if mode=='edit' else 1)
        
        submit_btn = st.form_submit_button("💾 데이터 저장하기")
        
        if submit_btn:
            sheet_c = get_worksheet_for_write("Containers")
            final_inbound_str = str(inbound_d) if is_inbound_checked else ""
            
            if mode == "add":
                new_id = str(int(time.time()))
                sheet_c.append_row([
                    new_id, chosen_m_id, cha_su, str(order_d), str(dept_d), str(arr_d), final_inbound_str, summary, feet
                ])
                st.success("🎉 성공적으로 등록되었습니다!")
            
            elif mode == "edit":
                c_id_list = sheet_c.col_values(1)
                try:
                    row_idx = c_id_list.index(str(container_data['컨테이너ID'])) + 1
                    update_range = f"B{row_idx}:I{row_idx}"
                    sheet_c.update(update_range, [[
                        chosen_m_id, cha_su, str(order_d), str(dept_d), str(arr_d), final_inbound_str, summary, feet
                    ]])
                    st.success("✅ 성공적으로 수정되었습니다!")
                except ValueError:
                    st.error("해당 컨테이너 정보를 찾을 수 없습니다.")
            
            time.sleep(1)
            st.cache_data.clear() 
            st.rerun()

# =====================================================================
# 🖥️ [3] 메인 실행 함수 (app.py와 호환)
# =====================================================================
def run(load_sheet_data):
    # 🚀 [1순위] 통합 공통 CSS 강제 로드 및 사이드바 동기화
    try:
        with open('style.css', encoding='utf-8') as f:
            st.markdown(f'<style>{f.read()}</style>', unsafe_allow_html=True)
    except:
        pass

    st.markdown("<h1>📦 입고 현황 (컨테이너 스케줄 관리)</h1>", unsafe_allow_html=True)
    st.info("💡 컨테이너별 발주, 출항, 입항 및 최종 입고 일정을 실시간으로 관리하고 수정하는 마스터 보드입니다.")
    
    df_m = load_sheet_data("Manufacturers")
    df_c = load_sheet_data("Containers")

    if df_m is None or df_c is None:
        st.error("🚨 구글 시트(Manufacturers 또는 Containers) 데이터를 불러올 수 없습니다. 탭 이름을 확인해 주세요.")
        return

    # 🚀 [데이터 튜닝] 모든 헤더와 내부 글자들의 앞뒤 공백을 완벽히 제거합니다.
    if not df_m.empty:
        df_m.columns = df_m.columns.astype(str).str.strip()
        for col in df_m.columns:
            df_m[col] = df_m[col].astype(str).str.strip()
            
    if not df_c.empty:
        df_c.columns = df_c.columns.astype(str).str.strip()
        for col in df_c.columns:
            df_c[col] = df_c[col].astype(str).str.strip()

    # -----------------------------------------------------------------
    # ⚙️ 3-1. 사이드바 조회 조건 및 동기화 장치
    # -----------------------------------------------------------------
    st.sidebar.markdown("### 🔍 입고 조회 조건")
    
    # 🔄 [핵심 치트키] 구글 시트 강제 강제 동기화 버튼 배치
    if st.sidebar.button("🔄 시트 데이터 즉시 새로고침", use_container_width=True):
        st.cache_data.clear() # app.py의 10분 캐시를 완전히 파괴합니다.
        st.rerun()
        
    st.sidebar.markdown("<br>", unsafe_allow_html=True)
    
    m_list = ["전체보기"]
    if not df_m.empty:
        m_list += list(df_m['제조사명'].unique())
        
    selected_m = st.sidebar.selectbox("🏭 제조사별 분류", m_list)
    view_all_history = st.sidebar.checkbox("📂 모든 기록 보기", value=False, help="체크 해제 시 입고일이 미지정이거나 아직 지나지 않은 스케줄만 봅니다.")
    
    st.sidebar.markdown('<hr style="border-top: 1px solid rgba(255, 255, 255, 0.2); margin: 20px 0px;">', unsafe_allow_html=True)
    
    if st.sidebar.button("✨ 신규 컨테이너 추가", use_container_width=True):
        if df_m.empty:
            st.warning("먼저 구글 시트 'Manufacturers' 탭에 제조사를 등록해 주세요!")
        else:
            container_form_dialog(mode="add", df_m=df_m)

    # 🚀 [상태 진단] 구글 시트에 원본 데이터가 아예 비어있는지 체크
    if df_c.empty or len(df_c) == 0:
        st.warning("📅 구글 시트 'Containers' 탭에 등록된 원본 데이터가 아예 없습니다. 사이드바의 '신규 컨테이너 추가' 버튼을 눌러 첫 데이터를 넣어주십시오!")
        return

    # 데이터 타입 캐스팅 및 정렬
    df_c['차수'] = pd.to_numeric(df_c['차수'], errors='coerce').fillna(0).astype(int)
    df_c = df_c.sort_values(by=['제조사ID', '차수'], ascending=[True, False])
    today_str = datetime.today().strftime("%Y-%m-%d")

    # -----------------------------------------------------------------
    # 📝 3-2. 필터링 엔진 작동
    # -----------------------------------------------------------------
    filtered_df = df_c.copy()

    # 조건 1. 제조사 분류
    if selected_m != "전체보기":
        target_m_id = df_m[df_m['제조사명'] == selected_m]['제조사ID'].values[0]
        filtered_df = filtered_df[filtered_df['제조사ID'] == target_m_id]

    # 조건 2. 진행중인 일정만 보기 (체크 해제 시)
    if not view_all_history:
        filtered_df = filtered_df[
            (filtered_df['입고일'] == "") | 
            (filtered_df['입고일'] >= today_str)
        ]

    # 🚀 [결과 출력 분기] 원본 데이터는 있으나 필터링 때문에 안 보이는 경우 안내
    if filtered_df.empty:
        st.warning("💡 이미 입고가 완료된 지난 기록들만 존재합니다. 과거 내역을 보시려면 사이드바의 [📂 모든 기록 보기]를 체크해 주십시오!")
        return

    # -----------------------------------------------------------------
    # 🗂️ 3-3. 카드 레이아웃 렌더링
    # -----------------------------------------------------------------
    display_df = pd.merge(filtered_df, df_m, on='제조사ID', how='left')
    grouped = display_df.groupby('제조사명')

    for m_name, group in grouped:
        st.markdown(f"## 🏭 {m_name} 입고 스케줄")
        
        for _, row in group.iterrows():
            if str(row.get('입고일', '')).strip() == "":
                status_html = "<span style='color:#E67E22; font-weight:bold;'>[⏳ 입고 대기중]</span>"
            else:
                status_html = f"<span style='color:#2ECC71; font-weight:bold;'>[✅ 입고완료: {row['입고일']}]</span>"
                
            with st.container():
                col_info, col_btn = st.columns([6, 1])
                
                with col_info:
                    st.markdown(f"""
                    <div style="background-color: #F8F9FA; padding: 15px; border-left: 5px solid #2E86C1; border-radius: 4px; margin-bottom: 10px;">
                        <table style="width:100%; border:none; font-size:1.05rem;">
                            <tr>
                                <td style="width:25%;"><b>차수:</b> {row['차수']}차</td>
                                <td style="width:25%;"><b>사이즈:</b> <span style="background-color:#E2E8F0; padding:2px 6px; border-radius:4px;">{row.get('feet', row.get('피트', '20FT'))}</span></td>
                                <td colspan="2">{status_html}</td>
                            </tr>
                            <tr style="color:#555555; font-size:0.95rem;">
                                <td>📅 <b>발주:</b> {row.get('발주일','')}</td>
                                <td>🚢 <b>출항:</b> {row.get('출항일','')}</td>
                                <td>🛬 <b>입항:</b> {row.get('입항일','')}</td>
                                <td>📦 <b>입고예정:</b> {row['입고일'] if str(row.get('입고일','')).strip() != "" else "미지정"}</td>
                            </tr>
                            <tr>
                                <td colspan="4" style="padding-top:8px; color:#2C3E50;">📝 <b>적요:</b> {row.get('적요','') if str(row.get('적요','')).strip() != "" else "없음"}</td>
                            </tr>
                        </table>
                    </div>
                    """, unsafe_allow_html=True)
                
                with col_btn:
                    st.markdown("<div style='padding-top:25px;'></div>", unsafe_allow_html=True)
                    if st.button("⚙️ 수정", key=f"edit_{row['컨테이너ID']}", use_container_width=True):
                        container_form_dialog(mode="edit", container_data=row, df_m=df_m)
        
        st.markdown("<div style='margin-bottom:30px;'></div>", unsafe_allow_html=True)
