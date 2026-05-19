import streamlit as st
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime
import time

# =====================================================================
# 🔑 [1] 구글 시트 연동 및 데이터 로드 함수
# =====================================================================
@st.cache_resource
def init_gspread():
    """구글 시트 API 인증 및 연결"""
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    # 대표님의 기존 json 키 파일 경로를 적어주세요.
    creds = ServiceAccountCredentials.from_json_keyfile_name("google_creds.json", scope) 
    client = gspread.authorize(creds)
    # 대표님이 사용 중인 스프레드시트 이름을 적어주세요.
    doc = client.open("자사_재고_및_물류_관리_시트") 
    return doc

def load_data():
    """시트에서 제조사 및 컨테이너 전체 데이터를 읽어와 DataFrame으로 반환"""
    doc = init_gspread()
    
    # 1. 제조사 마스터 로드
    sheet_m = doc.worksheet("Manufacturers")
    df_m = pd.DataFrame(sheet_m.get_all_records())
    
    # 2. 컨테이너 데이터 로드
    sheet_c = doc.worksheet("Containers")
    df_c = pd.DataFrame(sheet_c.get_all_records())
    
    # 데이터 타입을 문자열/날짜 등으로 정돈
    if not df_c.empty:
        df_c['제조사ID'] = df_c['제조사ID'].astype(str)
        df_m['제조사ID'] = df_m['제조사ID'].astype(str)
        
        # 정렬을 위해 ID와 차수 기준으로 정렬
        df_c = df_c.sort_values(by=['제조사ID', '차수'], ascending=[True, False])
        
    return df_m, df_c

# =====================================================================
# 🚀 [2] 최신 st.dialog를 활용한 입력/수정 팝업 모달창
# =====================================================================
@st.dialog("📦 컨테이너 정보 관리")
def container_form_dialog(mode="add", container_data=None, df_m=None):
    """신규 추가 및 수정을 하나의 팝업에서 처리하는 유연한 폼"""
    doc = init_gspread()
    sheet_c = doc.worksheet("Containers")
    
    st.write(f"### {'✨ 신규 컨테이너 등록' if mode=='add' else '📝 컨테이너 정보 수정'}")
    
    # 제조사 선택 리스트 구성
    m_options = {row['제조사명']: row['제조사ID'] for _, row in df_m.iterrows()}
    
    with st.form("container_form", clear_on_submit=True):
        # 1. 제조사 선택 (수정 모드일 때는 기존 값 매칭)
        default_m_idx = 0
        if mode == "edit" and container_data is not None:
            current_m_id = str(container_data['제조사ID'])
            current_m_name = [name for name, m_id in m_options.items() if m_id == current_m_id]
            if current_m_name:
                default_m_idx = list(m_options.keys()).index(current_m_name[0])
                
        selected_m_name = st.selectbox("제조사 선택", list(m_options.keys()), index=default_m_idx)
        chosen_m_id = m_options[selected_m_name]
        
        # 2. 나머지 정보 입력칸 구성
        cha_su = st.number_input("차수", min_value=1, value=int(container_data['차수']) if mode=='edit' else 1)
        
        # 날짜 도우미 변환 함수
        def safe_date_parse(date_str):
            try: return datetime.strptime(str(date_str), "%Y-%m-%d").date()
            except: return datetime.today().date()

        order_d = st.date_input("발주일", safe_date_parse(container_data['발주일']) if mode=='edit' else datetime.today())
        dept_d = st.date_input("출항일", safe_date_parse(container_data['출항일']) if mode=='edit' else datetime.today())
        arr_d = st.date_input("입항일", safe_date_parse(container_data['입항일']) if mode=='edit' else datetime.today())
        
        # 입고일은 미지정 상태를 표현하기 위해 체크박스 연동 처리
        has_inbound_date = True
        init_inbound_val = datetime.today().date()
        if mode == "edit":
            if not container_data['입고일'] or container_data['입고일'] == "":
                has_inbound_date = False
            else:
                init_inbound_val = safe_date_parse(container_data['입고일'])
                
        is_inbound_checked = st.checkbox("✅ 입고 완료 (입고일 지정)", value=has_inbound_date)
        inbound_d = st.date_input("입고일", init_inbound_val if is_inbound_checked else None, disabled=not is_inbound_checked)
        
        summary = st.text_input("적요", value=str(container_data['적요']) if mode=='edit' else "")
        feet = st.selectbox("피트 (FT)", ["20FT", "40FT", "40HQ", "기타"], index=["20FT", "40FT", "40HQ", "기타"].index(str(container_data['피트'])) if mode=='edit' else 1)
        
        # 저장 버튼
        submit_btn = st.form_submit_button("💾 데이터 저장하기")
        
        if submit_btn:
            final_inbound_str = str(inbound_d) if is_inbound_checked else ""
            
            if mode == "add":
                # 신규 추가 로직: 새로운 고유 ID 생성 후 행 추가
                new_id = str(int(time.time()))
                sheet_c.append_row([
                    new_id, chosen_m_id, cha_su, str(order_d), str(dept_d), str(arr_d), final_inbound_str, summary, feet
                ])
                st.success("🎉 성공적으로 신규 컨테이너가 등록되었습니다!")
            
            elif mode == "edit":
                # 수정 로직: 셀 위치를 찾아 매칭 후 셀 업데이트
                c_id_list = sheet_c.col_values(1) # 첫 번째 열(컨테이너ID) 전체 가져오기
                try:
                    row_idx = c_id_list.index(str(container_data['컨테이너ID'])) + 1
                    # 한 줄 업데이트 (gspread 범위 지정 업데이트로 속도 향상)
                    update_range = f"B{row_idx}:I{row_idx}"
                    sheet_c.update(update_range, [[
                        chosen_m_id, cha_su, str(order_d), str(dept_d), str(arr_d), final_inbound_str, summary, feet
                    ]])
                    st.success("✅ 컨테이너 정보가 성공적으로 수정되었습니다!")
                except ValueError:
                    st.error("데이터를 찾는 데 실패했습니다.")
            
            time.sleep(1)
            st.rerun()

# =====================================================================
# 🖥️ [3] 입고 현황 메인 대시보드 화면 렌더링
# =====================================================================
def render_inbound_page():
    st.markdown("<h1>📦 입고 현황 (컨테이너 스케줄 관리)</h1>", unsafe_allow_html=True)
    st.info("💡 컨테이너별 발주, 출항, 입항 및 최종 입고 일정을 실시간으로 관리하고 수정하는 마스터 보드입니다.")
    
    # 데이터 불러오기
    try:
        df_m, df_c = load_data()
    except Exception as e:
        st.error(f"구글 시트 연동 오류: {e}")
        return

    today_str = datetime.today().strftime("%Y-%m-%d")

    # -----------------------------------------------------------------
    # ⚙️ 3-1. 사이드바 제어 UI 구성
    # -----------------------------------------------------------------
    st.sidebar.markdown("### 🔍 입고 조회 조건")
    
    # 제조사 셀렉트박스 (전체보기 + 리스트)
    m_list = ["전체보기"] + list(df_m['제조사명'].unique())
    selected_m = st.sidebar.selectbox("🏭 제조사별 분류", m_list)
    
    st.sidebar.markdown("<br>", unsafe_allow_html=True)
    
    # 모든 목록 보기 체크박스 UI
    view_all_history = st.sidebar.checkbox("📂 모든 기록(지난 기록 포함) 보기", value=False, 
                                           help="체크 해제 시 입고일이 미지정이거나 아직 지나지 않은 스케줄만 봅니다.")
    
    st.sidebar.markdown('<hr style="border-top: 1px solid rgba(255, 255, 255, 0.2); margin: 20px 0px;">', unsafe_allow_html=True)
    
    # 신규 등록 버튼을 사이드바 하단 또는 메인 상단에 배치
    if st.sidebar.button("✨ 신규 컨테이너 추가", use_container_width=True):
        container_form_dialog(mode="add", df_m=df_m)

    # -----------------------------------------------------------------
    # 📝 3-2. 데이터 필터링 엔진 작동
    # -----------------------------------------------------------------
    filtered_df = df_c.copy()

    # 조건 1: 제조사 필터링
    if selected_m != "전체보기":
        target_m_id = df_m[df_m['제조s명'] == selected_m]['제조사ID'].values[0]
        filtered_df = filtered_df[filtered_df['제조사ID'] == target_m_id]

    # 조건 2: 입고일 상태 필터링 (기본값 설정 로직)
    if not view_all_history:
        # 입고일이 없거나("") 오늘 날짜 이후인 경우만 필터링
        filtered_df = filtered_df[
            (filtered_df['입고일'] == "") | 
            (filtered_df['입고일'].astype(str) >= today_str)
        ]

    # -----------------------------------------------------------------
    # 🗂️ 3-3. 메인 화면 리스트 출력 (제조사 그룹별 분류)
    # -----------------------------------------------------------------
    if filtered_df.empty:
        st.warning("조회 조건에 일치하는 컨테이너 수입 일정이 없습니다.")
        return

    # 화면에 표시하기 위해 제조사 마스터 Merge (ID 대신 명칭 노출용)
    display_df = pd.merge(filtered_df, df_m, on='제조사ID', how='left')

    # 제조사별로 그룹 묶음 출력
    grouped = display_df.groupby('제조사명')

    for m_name, group in grouped:
        st.markdown(f"## 🏭 {m_name} 입고 스케줄")
        
        # 각 컨테이너 데이터를 대표님이 좋아하시는 와이드 리스트 카드 형태로 출력
        for _, row in group.iterrows():
            # 입고 상태에 따른 뱃지 디자인
            if row['입고일'] == "":
                status_html = "<span style='color:#E67E22; font-weight:bold;'>[⏳ 입고 대기중]</span>"
            else:
                status_html = f"<span style='color:#2ECC71; font-weight:bold;'>[✅ 입고완료: {row['입고일']}]</span>"
                
            # 카드 박스 디자인 생성 (기존 style.css와 호환)
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
                                <td>📅 <b>발주:</b> {row['발주일']}</td>
                                <td>🚢 <b>출항:</b> {row['출항일']}</td>
                                <td>🛬 <b>입항:</b> {row['입항일']}</td>
                                <td>📦 <b>입고예정:</b> {row['입고일'] if row['입고일'] != "" else "미지정"}</td>
                            </tr>
                            <tr>
                                <td colspan="4" style="padding-top:8px; color:#2C3E50;">📝 <b>적요:</b> {row['적요'] if row['적요'] != "" else "없음"}</td>
                            </tr>
                        </table>
                    </div>
                    """, unsafe_allow_html=True)
                
                with col_btn:
                    st.markdown("<div style='padding-top:25px;'></div>", unsafe_allow_html=True)
                    # 각 행 고유한 key값을 부여하여 수정 모달 팝업 연결
                    if st.button("⚙️ 수정", key=f"edit_{row['컨테이너ID']}", use_container_width=True):
                        container_form_dialog(mode="edit", container_data=row, df_m=df_m)
        
        st.markdown("<div style='margin-bottom:30px;'></div>", unsafe_allow_html=True)

# 실행 구문 (테스트용)
if __name__ == "__main__":
    render_inbound_page()
