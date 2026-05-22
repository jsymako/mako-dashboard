import streamlit as st
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import json
from datetime import datetime
import time

# =====================================================================
# ⚙️ 글자 크기 조정 변수
# =====================================================================
TABLE_HEADER_SIZE = "1.00rem"  
TABLE_BODY_SIZE = "1.00rem"    

# =====================================================================
# 🔑 [1] 쓰기/수정용 구글 시트 연결
# =====================================================================
def get_worksheet_for_write(sheet_name):
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    creds_dict = json.loads(st.secrets["gcp_service_account"])
    creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
    client = gspread.authorize(creds)
    doc = client.open("통합재고관리")
    return doc.worksheet(sheet_name)

def add_one_year(d):
    if d is None: return ""
    try: return str(d.replace(year=d.year + 1))
    except ValueError: return str(d.replace(month=2, day=28, year=d.year + 1))

def safe_date_parse(date_str):
    if not date_str or str(date_str).strip() in ["", "미정", "nan", "None"]: return None
    try: return datetime.strptime(str(date_str).strip(), "%Y-%m-%d").date()
    except: return None

# =====================================================================
# 🚀 [2] 다이얼로그 팝업창 모음
# =====================================================================
@st.dialog("컨테이너 정보 관리")
def container_form_dialog(mode="add", container_data=None, df_m=None):
    st.write(f"### {'신규 컨테이너 등록' if mode=='add' else '컨테이너 정보 수정'}")
    m_options = {str(row['제조사명']): str(row['제조사ID']) for _, row in df_m.iterrows()}
    
    with st.form("container_form", clear_on_submit=True):
        default_m_idx = 0
        if mode == "edit" and container_data is not None:
            current_m_id = str(container_data['제조사ID'])
            current_m_name = [name for name, m_id in m_options.items() if m_id == current_m_id]
            if current_m_name: default_m_idx = list(m_options.keys()).index(current_m_name[0])
                
        selected_m_name = st.selectbox("제조사 선택", list(m_options.keys()), index=default_m_idx)
        chosen_m_id = m_options[selected_m_name]
        
        cha_su = st.number_input("차수", min_value=1, value=int(container_data.get('차수', 1)) if mode=='edit' else 1)
        
        feet_options = ["20FT", "40FT", "기타"]
        current_feet = str(container_data.get('피트', '40FT')) if mode == 'edit' else "40FT"
        feet_idx = feet_options.index(current_feet) if current_feet in feet_options else 1
        feet = st.selectbox("피트 (FT)", feet_options, index=feet_idx)
        
        st.markdown("<div style='font-size: 0.85rem; color: #7F8C8D; margin-bottom: 10px;'>💡 달력창 클릭 후 <b>백스페이스(지우기) 키</b>를 누르면 '미정' 처리됩니다.</div>", unsafe_allow_html=True)
        
        val_order = safe_date_parse(container_data.get('발주일', '')) if mode == 'edit' else None
        val_dept = safe_date_parse(container_data.get('출항일', '')) if mode == 'edit' else None
        val_arr = safe_date_parse(container_data.get('입항일', '')) if mode == 'edit' else None
        val_inbound = safe_date_parse(container_data.get('입고일', '')) if mode == 'edit' else None

        order_d = st.date_input("발주일", value=val_order)
        dept_d = st.date_input("출항일", value=val_dept)
        arr_d = st.date_input("입항일", value=val_arr)
        inbound_d = st.date_input("입고일", value=val_inbound)
        
        summary = st.text_input("적요", value=str(container_data.get('적요', '')) if mode=='edit' else "")
        submit_btn = st.form_submit_button("💾 데이터 저장하기")
        
        if submit_btn:
            sheet_c = get_worksheet_for_write("Containers")
            str_order = str(order_d) if order_d else ""
            str_dept = str(dept_d) if dept_d else ""
            str_arr = str(arr_d) if arr_d else ""
            str_inbound = str(inbound_d) if inbound_d else ""
            
            if mode == "add":
                new_id = str(int(time.time()))
                sheet_c.append_row([new_id, chosen_m_id, cha_su, str_order, str_dept, str_arr, str_inbound, summary, feet])
                st.success("🎉 성공적으로 등록되었습니다!")
            elif mode == "edit":
                c_id_list = sheet_c.col_values(1)
                try:
                    row_idx = c_id_list.index(str(container_data['컨테이너ID'])) + 1
                    sheet_c.update(f"B{row_idx}:I{row_idx}", [[chosen_m_id, cha_su, str_order, str_dept, str_arr, str_inbound, summary, feet]])
                    st.success("✅ 성공적으로 수정되었습니다!")
                except ValueError: st.error("데이터를 찾을 수 없습니다.")
            
            time.sleep(1)
            st.cache_data.clear() 
            st.rerun()

@st.dialog("🔍 현물검정 정보 관리")
def inspection_form_dialog(mode="add", insp_data=None):
    st.write(f"### {'신규 현물검정 제품 등록' if mode=='add' else '현물검정 정보 수정'}")
    
    with st.form("inspection_form", clear_on_submit=True):
        feed_name = st.text_input("사료의 명칭", value=str(insp_data.get('사료명칭', '')) if mode=='edit' else "")
        prod_type = st.text_input("제품 종류", value=str(insp_data.get('제품종류', '')) if mode=='edit' else "")
        insp_prod = st.text_input("현물검정제품", value=str(insp_data.get('현물검정제품', '')) if mode=='edit' else "")
        rel_prod = st.text_input("관련제품", value=str(insp_data.get('관련제품', '')) if mode=='edit' else "")
        
        st.markdown("<div style='font-size: 0.85rem; color: #7F8C8D; margin-bottom: 10px;'>💡 완료일을 선택하면 <b>검정예정일(1년 뒤)이 자동으로 계산</b>되어 기록됩니다. 빈칸이면 '미정' 처리됩니다.</div>", unsafe_allow_html=True)
        
        val_done = safe_date_parse(insp_data.get('현물검정완료일', '')) if mode == 'edit' else None
        done_d = st.date_input("현물검정완료일", value=val_done)
        
        submit_btn = st.form_submit_button("💾 검정 데이터 저장")
        
        if submit_btn:
            sheet_i = get_worksheet_for_write("Inspection")
            str_done = str(done_d) if done_d else ""
            str_next = add_one_year(done_d)
            
            if mode == "add":
                new_id = f"INSP_{int(time.time())}"
                sheet_i.append_row([new_id, feed_name, prod_type, insp_prod, rel_prod, str_done, str_next])
                st.success("🎉 성공적으로 등록되었습니다!")
            elif mode == "edit":
                i_id_list = sheet_i.col_values(1)
                try:
                    row_idx = i_id_list.index(str(insp_data['검정ID'])) + 1
                    sheet_i.update(f"B{row_idx}:G{row_idx}", [[feed_name, prod_type, insp_prod, rel_prod, str_done, str_next]])
                    st.success("✅ 성공적으로 수정되었습니다!")
                except ValueError: st.error("해당 데이터를 찾을 수 없습니다.")
                
            time.sleep(1)
            st.cache_data.clear()
            st.rerun()

# =====================================================================
# 🖥️ [3] 메인 실행 함수
# =====================================================================
def run(load_sheet_data):
    try:
        with open('style.css', encoding='utf-8') as f:
            st.markdown(f'<style>{f.read()}</style>', unsafe_allow_html=True)
    except: pass

    # -----------------------------------------------------------------
    # 파트 A: 컨테이너 입고 현황 
    # -----------------------------------------------------------------
    st.markdown("<h1>입고 현황</h1>", unsafe_allow_html=True)
    
    df_m = load_sheet_data("Manufacturers")
    df_c = load_sheet_data("Containers")
    df_i = load_sheet_data("Inspection") 

    if df_m is None or df_c is None:
        st.error("🚨 구글 시트 데이터를 불러올 수 없습니다. 탭 이름을 확인해 주세요.")
        return

    if not df_m.empty:
        df_m.columns = df_m.columns.astype(str).str.strip()
        for col in df_m.columns: df_m[col] = df_m[col].astype(str).str.strip()
    if not df_c.empty:
        df_c.columns = df_c.columns.astype(str).str.strip()
        for col in df_c.columns: df_c[col] = df_c[col].astype(str).str.strip()
    if df_i is not None and not df_i.empty:
        df_i.columns = df_i.columns.astype(str).str.strip()
        for col in df_i.columns: df_i[col] = df_i[col].astype(str).str.strip()

    m_order = []
    if not df_m.empty:
        for m in df_m['제조사명'].tolist():
            if m not in m_order: m_order.append(m)


        
    #st.sidebar.markdown("<br>", unsafe_allow_html=True)
    m_list = ["전체보기"] + m_order
    selected_m = st.sidebar.selectbox("제조사별 분류", m_list)
    view_all_history = st.sidebar.checkbox("모든 기록 보기", value=False)
    #st.sidebar.markdown('<hr style="border-top: 1px solid rgba(255, 255, 255, 0.2); margin: 20px 0px;">', unsafe_allow_html=True)
    
    if st.sidebar.button("신규 컨테이너 추가", use_container_width=True):
        container_form_dialog(mode="add", df_m=df_m)

    # st.sidebar.markdown("### 🔍 입고 조회 조건")
    if st.sidebar.button("데이터 새로고침", use_container_width=True):
        st.cache_data.clear()
        st.rerun()

    if not df_c.empty:
        df_c['차수'] = pd.to_numeric(df_c['차수'], errors='coerce').fillna(0).astype(int)
        m_id_order = [mid for mid in df_m['제조사ID'].tolist()]
        df_c['제조사ID'] = pd.Categorical(df_c['제조사ID'], categories=m_id_order, ordered=True)
        df_c = df_c.sort_values(by=['제조사ID', '차수'], ascending=[True, True])
        
        today_str = datetime.today().strftime("%Y-%m-%d")
        filtered_df = df_c.copy()
        if selected_m != "전체보기":
            target_m_id = df_m[df_m['제조사명'] == selected_m]['제조사ID'].values[0]
            filtered_df = filtered_df[filtered_df['제조사ID'] == target_m_id]
        if not view_all_history:
            filtered_df = filtered_df[(filtered_df['입고일'] == "") | (filtered_df['입고일'] >= today_str)]

        if filtered_df.empty:
            st.warning("💡 진행 중인 컨테이너 수입 일정이 없습니다.")
        else:
            display_df = pd.merge(filtered_df, df_m, on='제조사ID', how='left')
            for m_name in m_order:
                group = display_df[display_df['제조사명'] == m_name]
                if not group.empty:
                    st.markdown(f"## 🚢 {m_name}")
                    for _, row in group.iterrows():
                        ord_dt = str(row.get('발주일', '')).strip()
                        dep_dt = str(row.get('출항일', '')).strip()
                        arr_dt = str(row.get('입항일', '')).strip()
                        inb_dt = str(row.get('입고일', '')).strip()

                        if inb_dt:
                            if inb_dt < today_str: status_html = f"<span style='color:#2ECC71; font-weight:bold;'>[✅ 입고 완료]</span>"
                            else: status_html = f"<span style='color:#E67E22; font-weight:bold;'>[입고 대기중]</span>"
                        elif arr_dt: status_html = f"<span style='color:#3498DB; font-weight:bold;'>[입항 대기중]</span>"
                        elif dep_dt: status_html = f"<span style='color:#9B59B6; font-weight:bold;'>[출항 대기중]</span>"
                        else: status_html = f"<span style='color:#95A5A6; font-weight:bold;'>[준비 중]</span>"
                        
                        # 🚀 [수정] 표 하단 여백 박멸은 유지하되, 버튼이 표 아래에 풀사이즈로 매끄럽게 붙도록 재구성했습니다.
                        container_html = f"""
                        <div style="border: 1px solid #E2E8F0; border-left: 5px solid #2E86C1; border-radius: 6px; overflow: hidden; background-color: #FFFFFF; margin-bottom: 0px;">
                            <table style="width:100%; border-collapse: collapse; text-align: left; margin: 0px !important; padding: 0px !important;">
                                <tr style="font-size: 1.6rem; color:#444;">
                                    <td rowspan="2" style="padding: 15px; text-align: center; width: 12%; font-size: 2.0rem; color:#111; border-right: 1px solid #E2E8F0; border-bottom: none;"><b>{row['차수']}차</b></td>
                                    
                                    <td style="padding: 6px 10px; border-bottom: 1px solid #E2E8F0; width: 8%;"><b></b> {row.get('피트', '40FT')}</td>
                                    <td style="padding: 6px 10px; border-bottom: 1px solid #E2E8F0; width: 20%;"><b>입고:</b> {inb_dt if inb_dt else "<span style='color:#f14f6e;'>미정</span>"}</td>
                                    <td style="padding: 6px 10px; border-bottom: 1px solid #E2E8F0; width: 20%;"><b>입항:</b> {arr_dt if arr_dt else "<span style='color:#f14f6e;'>미정</span>"}</td>
                                    <td style="padding: 6px 10px; border-bottom: 1px solid #E2E8F0; width: 20%;"><b>출항:</b> {dep_dt if dep_dt else "<span style='color:#f14f6e;'>미정</span>"}</td>
                                    <td style="padding: 6px 10px; border-bottom: 1px solid #E2E8F0; width: 20%;"><b>발주:</b> {ord_dt if ord_dt else "<span style='color:#f14f6e;'>미정</span>"}</td>
                                </tr>
                                <tr style="font-size: 1.6rem;">
                                    <td colspan="5" style="padding: 3px 10px; color:#2C3E50; border-bottom: none;">{row.get('적요','') if str(row.get('적요','')).strip() != "" else "<span style='color:#A0AEC0;'>없음</span>"}</td>
                                </tr>
                            </table>
                        </div>
                        """
                        
                        with st.container():
                            st.markdown(container_html.replace('\n', ''), unsafe_allow_html=True)
                            
                            # 🚀 [수정] 우측으로 빠졌던 버튼을 다시 원래대로 시원한 가로형으로 되돌렸습니다.
                            if st.button("이 컨테이너 정보 수정", key=f"edit_cnt_{row['컨테이너ID']}", use_container_width=True):
                                container_form_dialog(mode="edit", container_data=row, df_m=df_m)
                            
                            # 🚀 [수정] 버튼 바로 아래에 35px 넉넉한 띄어쓰기를 주어 카드끼리 엉겨붙지 않게 차단했습니다.
                            st.markdown("<div style='margin-bottom: 10px;'></div>", unsafe_allow_html=True)

    # -----------------------------------------------------------------
    # 🚀 파트 B: 현물검정 예정일 현황 표 기능 가동
    # -----------------------------------------------------------------
    st.markdown("<hr style='border-top: 2px dashed #BDC3C7; margin: 40px 0px;'>", unsafe_allow_html=True)
    
    col_title, col_add_btn = st.columns([5, 1])
    with col_title:
        st.markdown("<h2>현물검정 현황</h2>", unsafe_allow_html=True)
    with col_add_btn:
        st.markdown("<div style='padding-top:10px;'></div>", unsafe_allow_html=True)
        if st.button("신규 검정 등록", key="add_new_inspection", use_container_width=True):
            inspection_form_dialog(mode="add")

    if df_i is None or df_i.empty:
        st.warning("📅 현물검정 현황 데이터가 시트에 존재하지 않습니다. 우측 버튼을 눌러 첫 데이터를 등록해 주십시오.")
        return

    calc_rows = []
    today = datetime.today().date()
    
    for _, row in df_i.iterrows():
        next_dt = safe_date_parse(row.get('검정예정일', ''))
        
        if next_dt:
            rem_days = (next_dt - today).days
            if rem_days < 0:
                status_txt = "초과"
                status_style = "color:#D9534F; font-weight:bold;" 
            elif rem_days < 50:
                status_txt = "임박"
                status_style = "color:#E67E22; font-weight:bold;" 
            elif rem_days < 100:
                status_txt = "준비"
                status_style = "color:#9B59B6; font-weight:bold;" 
            else:
                status_txt = "정상"
                status_style = "color:#2ECC71;" 
                
            rem_days_str = f"{rem_days}일"
            sort_val = rem_days 
        else:
            rem_days_str = "미정"
            status_txt = "미정"
            status_style = "color:#A0AEC0;"
            sort_val = 999999 
            
        row_dict = dict(row)
        row_dict['잔존일'] = rem_days_str
        row_dict['상태'] = status_txt
        row_dict['상태스타일'] = status_style
        row_dict['sort_key'] = sort_val
        calc_rows.append(row_dict)

    df_calc = pd.DataFrame(calc_rows).sort_values(by='sort_key', ascending=True)

    col_ratios = [1.4, 1.7, 1.7, 1.0, 1.1, 1.1, 0.6, 0.6, 0.6]

    st.markdown("<div style='border-top: 3px solid #2E86C1; background-color: #F8F9FA; border-radius: 4px 4px 0 0;'>", unsafe_allow_html=True)
    hcols = st.columns(col_ratios)
    headers = ["사료의 명칭", "제품 종류", "현물검정제품", "관련제품", "현물검정완료일", "검정예정일", "잔존일", "상태", "관리"]
    for i, h in enumerate(headers):
        align = "center" if h in ["상태", "관리"] else "left"
        hcols[i].markdown(f"<div style='font-size: {TABLE_HEADER_SIZE}; font-weight: bold; color: #2C3E50; padding: 12px 5px; border-bottom: 2px solid #E2E8F0; text-align: {align};'>{h}</div>", unsafe_allow_html=True)
    st.markdown("</div>", unsafe_allow_html=True)

    for _, row in df_calc.iterrows():
        done_str = row.get('현물검정완료일', '') if str(row.get('현물검정완료일', '')).strip() else "미정"
        next_str = row.get('검정예정일', '') if str(row.get('검정예정일', '')).strip() else "미정"

        with st.container():
            bcols = st.columns(col_ratios)
            cell_style = f"font-size: {TABLE_BODY_SIZE}; color: #333; padding-top: 5px;"

            bcols[0].markdown(f"<div style='{cell_style}'><b>{row.get('사료명칭', '')}</b></div>", unsafe_allow_html=True)
            bcols[1].markdown(f"<div style='{cell_style}'>{row.get('제품종류', '')}</div>", unsafe_allow_html=True)
            bcols[2].markdown(f"<div style='{cell_style}'>{row.get('현물검정제품', '')}</div>", unsafe_allow_html=True)
            bcols[3].markdown(f"<div style='{cell_style}'>{row.get('관련제품', '')}</div>", unsafe_allow_html=True)
            bcols[4].markdown(f"<div style='{cell_style} color:#555;'>{done_str}</div>", unsafe_allow_html=True)
            bcols[5].markdown(f"<div style='{cell_style} font-weight:600;'>{next_str}</div>", unsafe_allow_html=True)
            bcols[6].markdown(f"<div style='{cell_style} font-weight:bold;'>{row['잔존일']}</div>", unsafe_allow_html=True)
            bcols[7].markdown(f"<div style='{cell_style} text-align:center;'><span style='{row['상태스타일']}'>{row['상태']}</span></div>", unsafe_allow_html=True)

            with bcols[8]:
                if st.button("✏️", key=f"btn_insp_edit_{row['검정ID']}", use_container_width=True):
                    inspection_form_dialog(mode="edit", insp_data=row)

            st.markdown("<hr style='margin: 0; border: none; border-bottom: 1px solid #E2E8F0;'>", unsafe_allow_html=True)
