import streamlit as st
import pandas as pd
import gspread
import json
from oauth2client.service_account import ServiceAccountCredentials

# 🚀 [최적화 1] 구글 시트 접속(인증) 기능을 딱 한 번만 수행하도록 캐싱합니다.
# 이 기능 덕분에 저장 버튼을 누를 때 로그인 과정 없이 즉시 저장이 시작됩니다.
@st.cache_resource
def get_gspread_client():
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    creds_dict = json.loads(st.secrets["gcp_service_account"])
    creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
    return gspread.authorize(creds)

def run(load_data_func):
    st.title("💳 채권 분석")

    # CSS 로드 및 스타일 정의 (기존 동일)
    try:
        with open("ar_trend.css", "r", encoding="utf-8") as f:
            st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)
    except FileNotFoundError: pass

    # 매니저 맵 및 스타일 (기존 동일)
    MANAGER_MAP = {"001": "이계성", "002": "이계흥", "004": "황일용", "00026": "신의명", "007": "정상영", "009": "이경옥"}
    MANAGER_ORDER = ["이계성", "이계흥", "황일용", "신의명", "정상영", "이경옥"]

    # 🚀 [최적화 2] 메모(코멘트) 데이터 세션 관리
    if "ar_memo_data" not in st.session_state:
        try:
            st.session_state.ar_memo_data = load_data_func("ar_memo")
        except:
            st.session_state.ar_memo_data = pd.DataFrame(columns=['거래처명', '메모'])
    
    df_memo_gs = st.session_state.ar_memo_data

    # 파일 업로더
    uploaded_file = st.file_uploader("", type=['csv', 'xlsx', 'xls'], label_visibility="collapsed")
    if not uploaded_file:
        st.info("👆 이카운트 생성 DATA파일을 업로드 해주세요.")
        return

    # 🚀 [최적화 3] 엑셀 파싱 결과 캐싱 (이전과 동일하게 유지)
    try:
        file_id = uploaded_file.name + str(uploaded_file.size)
        if "cached_file_id" not in st.session_state or st.session_state.cached_file_id != file_id:
            with st.spinner("📊 대용량 데이터를 분석 중입니다..."):
                if uploaded_file.name.endswith('.csv'):
                    try: df_raw = pd.read_csv(uploaded_file, encoding='utf-8')
                    except: df_raw = pd.read_csv(uploaded_file, encoding='cp949')
                else: df_raw = pd.read_excel(uploaded_file)

                header_idx = df_raw[df_raw.apply(lambda r: r.astype(str).str.contains('거래처명').any(), axis=1)].index[0]
                df_raw.columns = df_raw.iloc[header_idx]
                df = df_raw.iloc[header_idx+1:].reset_index(drop=True)
                df = df[~df['거래처명'].astype(str).str.contains('계|합계|누계', na=False)]
                df['거래처명'] = df['거래처명'].ffill().astype(str).str.strip()
                
                manager_col = next((c for c in df.columns if '담당자' in str(c)), None)
                if manager_col:
                    df[manager_col] = df[manager_col].ffill().astype(str).str.strip().apply(lambda x: MANAGER_MAP.get(x, "기타/미지정"))

                month_cols = [c for c in df.columns if '20' in str(c) and ('/' in str(c) or '-' in str(c))]
                df_melt = df.melt(id_vars=['거래처명', '구분'] + ([manager_col] if manager_col else []), value_vars=month_cols, var_name='기준월', value_name='금액')
                df_melt['금액'] = pd.to_numeric(df_melt['금액'].astype(str).str.replace(',', ''), errors='coerce').fillna(0)
                df_pivot = df_melt.pivot_table(index=['거래처명', '기준월'] + ([manager_col] if manager_col else []), columns='구분', values='금액', aggfunc='sum').reset_index()

                st.session_state.cached_file_id = file_id
                st.session_state.cached_df_pivot = df_pivot
                st.session_state.cached_manager_col = manager_col
        
        df_pivot = st.session_state.cached_df_pivot
        manager_col = st.session_state.cached_manager_col

        # 데이터 필터링 및 카드 생성 로직 (기존 동일)
        month_list = sorted(list(df_pivot['기준월'].unique()), reverse=True)
        m0, m1, m2 = month_list[0], (month_list[1] if len(month_list) > 1 else None), (month_list[2] if len(month_list) > 2 else None)
        
        valid_mgrs = [m for m in MANAGER_ORDER if m in df_pivot[manager_col].unique()]
        sel_m = st.sidebar.selectbox("담당자 선택", ["전체보기"] + valid_mgrs) if manager_col else "전체보기"
        
        # 🚀 [사용성 개선] 업체가 너무 많으면 로딩이 느려지므로 '검색' 기능을 추가하면 좋습니다.
        search_q = st.sidebar.text_input("🔍 업체명 검색", "")

        cards_data = []
        for trader, group in df_pivot.groupby('거래처명'):
            # 필터링 로직... (생략)
            curr = group[group['기준월'] == m0].iloc[0]
            if sel_m != "전체보기" and curr[manager_col] != sel_m: continue
            if search_q and search_q not in trader: continue
            # ... 카드 데이터 구성 ...
            # (중략: 기존 cards_data.append 로직)
            cards_data.append({'name': trader, 'mgr': curr[manager_col], 'j0': curr['잔액'], 'm0': curr['매출'], 's0': curr['수금'], 'd0': 0, 'trend': [0]*12}) # 예시용

        final_df = pd.DataFrame(cards_data)
        
        if not final_df.empty:
            # 상단 KPI 및 리스트 루프
            for _, row in final_df.iterrows():
                # 카드 UI 생성...
                
                # 🚀 [메모 섹션 수정]
                memo_v = df_memo_gs[df_memo_gs['거래처명'] == row['name']]['메모'].iloc[0] if row['name'] in df_memo_gs['거래처명'].values else ""
                m_col, b_col = st.columns([6, 1])
                with m_col:
                    memo_input = st.text_input(f"메모 ({row['name']})", value=memo_v, key=f"input_{row['name']}", label_visibility="collapsed")
                
                with b_col:
                    if st.button("💾 저장", key=f"save_{row['name']}", use_container_width=True):
                        # 1. 화면 중앙 팝업 표시
                        placeholder = st.empty()
                        placeholder.markdown(f"""
                            <div style='position: fixed; top: 50%; left: 50%; transform: translate(-50%, -50%); 
                                        background-color: rgba(0, 0, 0, 0.9); color: #fff; padding: 40px; 
                                        border-radius: 20px; font-size: 24px; font-weight: bold; z-index: 99999;
                                        box-shadow: 0 0 20px rgba(0,0,0,0.5); text-align: center; width: 400px;'>
                                <div style='font-size: 40px; margin-bottom: 20px;'>💾</div>
                                {row['name']}<br><br>코멘트를 저장하고 있습니다...
                            </div>
                        """, unsafe_allow_html=True)

                        # 2. 미리 캐싱된 클라이언트로 즉시 저장
                        try:
                            client = get_gspread_client() # 🚀 여기서 로그인 과정 없이 바로 가져옴!
                            doc = client.open("통합재고관리")
                            sheet = doc.worksheet("ar_memo")
                            
                            all_memos = df_memo_gs.set_index('거래처명')['메모'].to_dict()
                            all_memos[row['name']] = memo_input
                            sheet.clear()
                            sheet.update([['거래처명', '메모']] + [[k, v] for k, v in all_memos.items()])
                            
                            # 세션 상태 업데이트
                            st.session_state.ar_memo_data = pd.DataFrame(list(all_memos.items()), columns=['거래처명', '메모'])
                            st.toast("성공적으로 저장되었습니다!")
                        except Exception as e:
                            st.error(f"저장 실패: {e}")
                        
                        placeholder.empty() # 팝업 제거
                        st.rerun()

    except Exception as e:
        st.error(f"오류: {e}")
