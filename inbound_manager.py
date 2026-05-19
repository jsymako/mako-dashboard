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
    doc = client.open("통합재고관리") # 대표님의 실제 스프레드시트 이름
    return doc.worksheet(sheet_name)

# =====================================================================
# 🚀 [2] 입력 및 수정 팝업 모달창 (st.dialog)
# =====================================================================
@st.dialog("📦 컨테이너 정보 관리")
def container_form_dialog(mode="add", container_data=None, df_m=None):
    st.write(f"### {'✨ 신규 컨테이너 등록' if mode=='add' else '📝 컨테이너 정보 수정'}")
    
    # 제조사 선택 리스트 구성
    m_options = {row['제조사명']: str(row['제조사ID']) for _, row in df_m.iterrows()}
    
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
            sheet_c = get_worksheet_for_write("Containers") # 시트 쓰기 권한 가져오기
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
            st.cache_data.clear() # 🚀 저장 후 캐시를 비워줘서 app.py가 새 데이터를 불러오게 함
            st.rerun()

# =====================================================================
# 🖥️ [3] 메인 실행 함수 (app.py와 완벽 호환)
# =====================================================================
def run(load_sheet_data):
    st.markdown("<h1>📦 입고 현황 (컨테이너 스케줄 관리)</h1>", unsafe_allow_html=True)
    st.info("💡 컨테이너별 발주, 출항, 입항 및 최종 입고 일정을 실시간으로 관리하고 수정하는 마스터 보드입니다.")
    
    # app.py에서 넘겨받은 load_sheet_data 함수를 이용해 데이터 로드!
    df_m = load_sheet_data("Manufacturers")
    df_c = load_sheet_data("Containers")

    if df_m is None or df_c is None:
        st.error("구글 시트(Manufacturers 또는 Containers) 데이터를 불러올 수 없습니다. 시트 이름을 확인해 주세요.")
        return

    # 데이터 정돈
    if not df_c.empty:
        df_c['제조사ID'] = df_c['제조사ID'].astype(str)
        df_m['제조사ID'] = df_m['제조사ID'].astype(str)
        df_c['차수'] = pd.to_numeric(df_c['차수'], errors='coerce').fillna(0).astype(int)
        df_c = df_c.sort_values(by=['제조사ID', '차수'], ascending=[True, False])
        
    today_str = datetime.today().strftime("%Y-%m-%d")

    # -----------------------------------------------------------------
    # ⚙️ 3-1. 사이드바 UI
    # -----------------------------------------------------------------
    st.sidebar.markdown("### 🔍 입고 조회 조건")
    
    m_list = ["전체보기"] + list(df_m['제조사명'].unique())
    selected_m = st.sidebar.selectbox("🏭 제조사별 분류", m_list)
    
    st.sidebar.markdown("<br>", unsafe_allow_html=True)
    view_all_history = st.sidebar.checkbox("📂 모든 기록 보기", value=False, help="체크 해제 시 입고일이 미지정이거나 아직 지나지 않은 스케줄만 봅니다.")
    st.sidebar.markdown('<hr style="border-top: 1px solid rgba(255, 255, 255, 0.2); margin: 20px 0px;">', unsafe_allow_html=True)
    
    if st.sidebar.button("✨ 신규 컨테이너 추가", use_container_width=True):
        container_form_dialog(mode="add", df_m=df_m)

    # -----------------------------------------------------------------
    # 📝 3-2. 필터링 로직
    # -----------------------------------------------------------------
    filtered_df = df_c.copy()

    if selected_m != "전체보기":
        target_m_id = df_m[df_m['제조사명'] == selected_m]['제조사ID'].values[0]
        filtered_df = filtered_df[filtered_df['제조사ID'] == target_m_id]

    if not view_all_history:
        # 입고일이 공백이거나, 오늘 날짜 이상인 것만 필터링
        filtered_df = filtered_df[
            (filtered_df['입고일'] == "") | 
            (filtered_df['입고일'].astype(str) >= today_str)
        ]

    # -----------------------------------------------------------------
    # 🗂️ 3-3. 리스트 출력
    # -----------------------------------------------------------------
    if filtered_df.empty:
        st.warning("조회 조건에 일치하는 수입 일정이 없습니다.")
        return

    # 화면 표시를 위해 제조사명 Merge
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
                                <td style="width:25%;"><b>사이즈:</b> <span style="background-color:#E2E8F0; padding:2px 6px; border-radius:4px;">{row['피트']}</span></td>
                                <td colspan="2">{status_html}</td>
                            </tr>
                            <tr style="color:#555555; font-size:0.95rem;">
                                <td>📅 <b>발주:</b> {row.get('발주일','')}</td>
                                <td>🚢 <b>출항:</b> {row.get('출항일','')}</td>
                                <td>🛬 <b>입항:</b> {row.get('입항일','')}</td>
                                <td>📦 <b>입고예정:</b> {row['입고일'] if str(row['입고일']).strip() != "" else "미지정"}</td>
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
