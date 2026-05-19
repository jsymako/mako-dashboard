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
        
        # 날짜 파싱 및 안전한 기본값 할당 로직
        def safe_date_parse(date_str):
            if not date_str or str(date_str).strip() in ["", "미정", "nan", "None"]:
                return None
            try: 
                return datetime.strptime(str(date_str).strip(), "%Y-%m-%d").date()
            except: 
                return None

        # 🚀 [수정] 안내 글자 크기를 확 줄이고, 백스페이스로 지우는 방법으로 안내 변경
        st.markdown("<div style='font-size: 0.85rem; color: #7F8C8D; margin-bottom: 10px;'>💡 날짜가 아직 정해지지 않았다면, 달력창을 클릭 후 <b>백스페이스(지우기) 키</b>를 눌러 칸을 텅 비워두세요. (자동으로 '미정' 처리됩니다)</div>", unsafe_allow_html=True)
        
        val_order = safe_date_parse(container_data.get('발주일', '')) if mode == 'edit' else None
        val_dept = safe_date_parse(container_data.get('출항일', '')) if mode == 'edit' else None
        val_arr = safe_date_parse(container_data.get('입항일', '')) if mode == 'edit' else None
        val_inbound = safe_date_parse(container_data.get('입고일', '')) if mode == 'edit' else None

        order_d = st.date_input("발주일", value=val_order)
        dept_d = st.date_input("출항일", value=val_dept)
        arr_d = st.date_input("입항일", value=val_arr)
        inbound_d = st.date_input("입고일", value=val_inbound)
        
        summary = st.text_input("적요", value=str(container_data.get('적요', '')) if mode=='edit' else "")
        
        # 🚀 [수정] 40HQ 제거 및 에러 방지 로직 적용
        feet_options = ["20FT", "40FT", "기타"]
        current_feet = str(container_data.get('피트', '20FT')) if mode == 'edit' else "20FT"
        feet_idx = feet_options.index(current_feet) if current_feet in feet_options else 0
        feet = st.selectbox("피트 (FT)", feet_options, index=feet_idx)
        
        submit_btn = st.form_submit_button("💾 데이터 저장하기")
        
        if submit_btn:
            sheet_c = get_worksheet_for_write("Containers")
            
            str_order = str(order_d) if order_d else ""
            str_dept = str(dept_d) if dept_d else ""
            str_arr = str(arr_d) if arr_d else ""
            str_inbound = str(inbound_d) if inbound_d else ""
            
            if mode == "add":
                new_id = str(int(time.time()))
                sheet_c.append_row([
                    new_id, chosen_m_id, cha_su, str_order, str_dept, str_arr, str_inbound, summary, feet
                ])
                st.success("🎉 성공적으로 등록되었습니다!")
            
            elif mode == "edit":
                c_id_list = sheet_c.col_values(1)
                try:
                    row_idx = c_id_list.index(str(container_data['컨테이너ID'])) + 1
                    update_range = f"B{row_idx}:I{row_idx}"
                    sheet_c.update(update_range, [[
                        chosen_m_id, cha_su, str_order, str_dept, str_arr, str_inbound, summary, feet
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
        st.error("🚨 구글 시트 데이터를 불러올 수 없습니다. 탭 이름을 확인해 주세요.")
        return

    # 공백 소독
    if not df_m.empty:
        df_m.columns = df_m.columns.astype(str).str.strip()
        for col in df_m.columns: df_m[col] = df_m[col].astype(str).str.strip()
    if not df_c.empty:
        df_c.columns = df_c.columns.astype(str).str.strip()
        for col in df_c.columns: df_c[col] = df_c[col].astype(str).str.strip()

    # -----------------------------------------------------------------
    # ⚙️ 3-1. 사이드바 UI
    # -----------------------------------------------------------------
    st.sidebar.markdown("### 🔍 입고 조회 조건")
    if st.sidebar.button("🔄 시트 데이터 즉시 새로고침", use_container_width=True):
        st.cache_data.clear()
        st.rerun()
        
    st.sidebar.markdown("<br>", unsafe_allow_html=True)
    
    m_list = ["전체보기"]
    if not df_m.empty: m_list += list(df_m['제조사명'].unique())
        
    selected_m = st.sidebar.selectbox("🏭 제조사별 분류", m_list)
    view_all_history = st.sidebar.checkbox("📂 모든 기록 보기", value=False, help="체크 해제 시 입고일이 미지정이거나 아직 지나지 않은 스케줄만 봅니다.")
    st.sidebar.markdown('<hr style="border-top: 1px solid rgba(255, 255, 255, 0.2); margin: 20px 0px;">', unsafe_allow_html=True)
    
    if st.sidebar.button("✨ 신규 컨테이너 추가", use_container_width=True):
        if df_m.empty: st.warning("먼저 구글 시트 'Manufacturers' 탭에 제조사를 등록해 주세요!")
        else: container_form_dialog(mode="add", df_m=df_m)

    if df_c.empty or len(df_c) == 0:
        st.warning("📅 구글 시트 'Containers' 탭에 등록된 데이터가 없습니다. 신규 추가를 진행해 주세요.")
        return

    df_c['차수'] = pd.to_numeric(df_c['차수'], errors='coerce').fillna(0).astype(int)
    df_c = df_c.sort_values(by=['제조사ID', '차수'], ascending=[True, False])
    today_str = datetime.today().strftime("%Y-%m-%d")

    # -----------------------------------------------------------------
    # 📝 3-2. 필터링 로직
    # -----------------------------------------------------------------
    filtered_df = df_c.copy()

    if selected_m != "전체보기":
        target_m_id = df_m[df_m['제조사명'] == selected_m]['제조사ID'].values[0]
        filtered_df = filtered_df[filtered_df['제조사ID'] == target_m_id]

    if not view_all_history:
        filtered_df = filtered_df[
            (filtered_df['입고일'] == "") | 
            (filtered_df['입고일'] >= today_str)
        ]

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
            ord_dt = str(row.get('발주일', '')).strip()
            dep_dt = str(row.get('출항일', '')).strip()
            arr_dt = str(row.get('입항일', '')).strip()
            inb_dt = str(row.get('입고일', '')).strip()

            # 4단계 우선순위 상태 체계
            if inb_dt:
                if inb_dt < today_str:
                    status_html = f"<span style='color:#2ECC71; font-weight:bold;'>[✅ 입고 완료]</span>"
                else:
                    status_html = f"<span style='color:#E67E22; font-weight:bold;'>[⏳ 입고 대기중]</span>"
            elif arr_dt:
                status_html = f"<span style='color:#3498DB; font-weight:bold;'>[🛬 입항 대기중]</span>"
            elif dep_dt:
                status_html = f"<span style='color:#9B59B6; font-weight:bold;'>[🚢 출항 대기중]</span>"
            else:
                status_html = f"<span style='color:#95A5A6; font-weight:bold;'>[🛠️ 준비 중]</span>"
                
            with st.container():
                st.markdown(f"""
                <div style="background-color: #F8F9FA; padding: 18px; border-left: 5px solid #2E86C1; border-radius: 6px; margin-bottom: 5px; border-top: 1px solid #E2E8F0; border-right: 1px solid #E2E8F0; border-bottom: 1px solid #E2E8F0;">
                    <table style="width:100%; border:none; font-size:1.05rem; margin-bottom: 5px;">
                        <tr>
                            <td style="width:25%;"><b>차수:</b> {row['차수']}차</td>
                            <td style="width:25%;"><b>사이즈:</b> <span style="background-color:#E2E8F0; padding:2px 6px; border-radius:4px;">{row.get('피트', '20FT')}</span></td>
                            <td colspan="2" style="text-align:left;">{status_html}</td>
                        </tr>
                        <tr style="color:#555555; font-size:0.95rem;">
                            <td>📦 <b>입고일:</b> {inb_dt if inb_dt else "<span style='color:#A0AEC0;'>미정</span>"}</td>
                            <td>🛬 <b>입항일:</b> {arr_dt if arr_dt else "<span style='color:#A0AEC0;'>미정</span>"}</td>
                            <td>🚢 <b>출항일:</b> {dep_dt if dep_dt else "<span style='color:#A0AEC0;'>미정</span>"}</td>
                            <td>📅 <b>발주일:</b> {ord_dt if ord_dt else "<span style='color:#A0AEC0;'>미정</span>"}</td>
                        </tr>
                        <tr>
                            <td colspan="4" style="padding-top:10px; color:#2C3E50;">📝 <b>적요:</b> {row.get('적요','') if str(row.get('적요','')).strip() != "" else "<span style='color:#A0AEC0;'>없음</span>"}</td>
                        </tr>
                    </table>
                </div>
                """, unsafe_allow_html=True)
                
                if st.button("⚙️ 이 컨테이너 정보 수정", key=f"edit_{row['컨테이너ID']}", use_container_width=True):
                    container_form_dialog(mode="edit", container_data=row, df_m=df_m)
                    
        st.markdown("<div style='margin-bottom:30px;'></div>", unsafe_allow_html=True)
