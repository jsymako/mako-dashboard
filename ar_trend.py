import streamlit as st
import pandas as pd
import gspread
import json
import altair as alt
from oauth2client.service_account import ServiceAccountCredentials
from utils import custom_fullscreen_spinner

# 🚀 [최적화 1] 구글 시트 접속(인증) 기능을 딱 한 번만 수행하도록 캐싱합니다.
# 이 기능 덕분에 저장 버튼을 누를 때 로그인 과정 없이 즉시 저장이 시작됩니다.
@st.cache_resource
def get_gspread_client():
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    creds_dict = json.loads(st.secrets["gcp_service_account"])
    creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
    return gspread.authorize(creds)

def run(load_data_func):
    st.title("채권 분석")

    # 🚀 방금 만든 안전한 'ar_trend.css'를 불러옵니다.
    try:
        with open("style.css", "r", encoding="utf-8") as f:
            st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)
    except FileNotFoundError:
        pass

    # =================================================================
    # 🚀 [핵심 추가] 하드코딩 맵 삭제 및 Employees 시트 동적 로드
    # =================================================================
    try:
        df_emp = load_data_func("Employees")
        # 직원ID를 키(Key), 성명을 값(Value)으로 하는 자동 매핑 사전(Dictionary) 생성
        dynamic_manager_map = {str(row['직원ID']).strip(): str(row['성명']).strip() for _, row in df_emp.iterrows()}
        # 드롭다운에 표시할 직원 이름 목록 (가나다순 정렬)
        manager_list = sorted(list(set(dynamic_manager_map.values())))
    except Exception as e:
        # 혹시 시트 로드에 실패할 경우를 대비한 안전장치 (기존 데이터)
        dynamic_manager_map = {
            "001": "이계성", "002": "이계흥", "004": "황일용",
            "00026": "신의명", "007": "정상영", "009": "이경옥"
        }
        manager_list = ["신의명", "이경옥", "이계성", "이계흥", "정상영", "황일용"]

    # 🎨 [CSS] 데이터 카드 디자인
    st.markdown("""
        <style>
        .ar-container {
            border: 2px solid #222; border-radius: 10px; padding: 5px; margin-bottom: 20px; background-color: #fff;
        }
        .header-row {
            display: flex; align-items: center; gap: 15px; padding: 0px 0px 0px 5px; margin-bottom: 0px;
        }
        .title-txt { font-size: 1.5rem; font-weight: 600; color: #000; }
        .mgr-txt { font-size: 1.1rem; font-weight: bold; }
        
        .data-column { 
            background: #ffffff; border: 1px solid #e0e0e0; border-radius: 8px; padding: 15px;
            min-height: 260px; height: 100%; display: flex; flex-direction: column; justify-content: space-between;
        }
        .col-title { 
            font-size: 1.3rem; font-weight: 600; margin-bottom: 15px; 
            text-align: center; color: #000; border-bottom: 3px solid #333; padding-bottom: 5px; 
        }
        .row-item { display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px; }
        
        .label-xl { font-size: 1.1rem; color: #555; font-weight: 600; }
        .val-xl { font-size: 1.4rem; font-weight: 600; color: #111; }
        
        .diff-up { color: #d9534f; font-weight: bold; font-size: 1.0rem; }
        .diff-down { color: #0055ff; font-weight: bold; font-size: 1.0rem; } 
        .traffic-light { font-size: 1.5rem; margin-right: 5px; }
        
        .memo-section { margin-top: 15px; padding-top: 15px; border-top: 1px solid #eee; }
        </style>
    """, unsafe_allow_html=True)

    # 🚀 [최적화 2] 메모(코멘트) 데이터 세션 관리
    if "ar_memo_data" not in st.session_state:
        try:
            st.session_state.ar_memo_data = load_data_func("ar_memo")
        except:
            st.session_state.ar_memo_data = pd.DataFrame(columns=['거래처명', '메모'])
    
    df_memo_gs = st.session_state.ar_memo_data

    # =================================================================
    # 🚀 [UI 혁신] 뚱뚱한 박스를 안 보이게 접어두는 얇은 바(Expander) 적용
    # =================================================================
    
    uploaded_file = st.file_uploader("", type=['csv', 'xlsx', 'xls'], label_visibility="collapsed")

    if not uploaded_file:
        st.info("👆 이카운트 채권 DATA파일을 업로드 해주세요.")
        return

    try:
        file_id = uploaded_file.name + str(uploaded_file.size)
        if "cached_file_id" not in st.session_state or st.session_state.cached_file_id != file_id:
            with st.spinner("엑셀 데이터를 불러오고 있습니다..."):
                if uploaded_file.name.endswith('.csv'):
                    try: df_raw = pd.read_csv(uploaded_file, encoding='utf-8', dtype=str)
                    except: df_raw = pd.read_csv(uploaded_file, encoding='cp949', dtype=str)
                else: df_raw = pd.read_excel(uploaded_file, dtype=str)

                header_idx = df_raw[df_raw.apply(lambda r: r.astype(str).str.contains('거래처명').any(), axis=1)].index[0]
                df_raw.columns = df_raw.iloc[header_idx]
                df = df_raw.iloc[header_idx+1:].reset_index(drop=True)
                df = df[~df['거래처명'].astype(str).str.contains('계|합계|누계', na=False)]
                df['거래처명'] = df['거래처명'].ffill().astype(str).str.strip()
                
                manager_col = next((c for c in df.columns if '담당자' in str(c)), None)
                if manager_col:
                    # 💡 [핵심 연동] 이카운트 데이터의 코드값을 Employees 시트 기반으로 매핑 (이름이면 그대로, 매핑 안 되면 기타/미지정)
                    df[manager_col] = df[manager_col].ffill().astype(str).str.strip().apply(
                        lambda x: dynamic_manager_map.get(x, x if x in manager_list else "기타/미지정")
                    )

                month_cols = [c for c in df.columns if '20' in str(c) and ('/' in str(c) or '-' in str(c))]
                df_melt = df.melt(id_vars=['거래처명', '구분'] + ([manager_col] if manager_col else []), value_vars=month_cols, var_name='기준월', value_name='금액')
                df_melt['금액'] = pd.to_numeric(df_melt['금액'].astype(str).str.replace(',', ''), errors='coerce').fillna(0)
                df_pivot = df_melt.pivot_table(index=['거래처명', '기준월'] + ([manager_col] if manager_col else []), columns='구분', values='금액', aggfunc='sum').reset_index()

                st.session_state.cached_file_id = file_id
                st.session_state.cached_df_pivot = df_pivot
                st.session_state.cached_manager_col = manager_col
        
        # 🚀 저장을 눌러서 화면이 새로고침 되더라도, 메모리에서 0.1초 만에 완성본을 꺼내옵니다!
        df_pivot = st.session_state.cached_df_pivot
        manager_col = st.session_state.cached_manager_col
        
        month_list = sorted(list(df_pivot['기준월'].unique()), reverse=True)
        m0, m1, m2 = month_list[0], (month_list[1] if len(month_list) > 1 else None), (month_list[2] if len(month_list) > 2 else None)

        # 💡 [드롭다운 수정] 데이터 존재 유무와 무관하게 Employees에 등록된 모든 직원을 드롭다운에 노출합니다.
        sel_m = st.sidebar.selectbox("담당자 선택", ["전체보기"] + manager_list) if manager_col else "전체보기"
        
        hide_zero = st.sidebar.checkbox("당월 잔액 0원 숨기기", value=True)
        min_dso = st.sidebar.slider("DSO 필터 (최소 일수)", 0, 120, 45, 15)
        sort_opt = st.sidebar.radio("목록 정렬 기준", ["잔액순", "DSO 위험순", "가나다순"])

        with custom_fullscreen_spinner("채권 데이터를 분석하고 대시보드를 생성 중입니다. 잠시만 기다려주세요."):
            cards_data = []
            for trader, group in df_pivot.groupby('거래처명'):
                def get_dso(off):
                    sub = group[group['기준월'].isin(month_list[off:off+12])]
                    s, b = sub['매출'].sum(), sub['잔액'].sum()
                    return 9999 if s < 1 else int(round((b/s)*30))
                
                d0 = get_dso(0)
                curr = group[group['기준월'] == m0].iloc[0]
                
                if hide_zero and curr['잔액'] <= 0: continue
                if d0 < min_dso: continue
                if sel_m != "전체보기" and curr[manager_col] != sel_m: continue
    
                p1 = group[group['기준월'] == m1].iloc[0] if m1 in group['기준월'].values else None
                p2 = group[group['기준월'] == m2].iloc[0] if m2 in group['기준월'].values else None
                
                trend_df = group[group['기준월'].isin(sorted(month_list[:12]))].sort_values('기준월')
                trend_data = trend_df.set_index('기준월')[['잔액', '매출', '수금']]
                
                cards_data.append({
                    'name': trader, 'mgr': curr[manager_col], 'trend': trend_data,
                    'm0': curr['매출'], 's0': curr['수금'], 'j0': curr['잔액'], 'd0': d0,
                    'm1': p1['매출'] if p1 is not None else 0, 's1': p1['수금'] if p1 is not None else 0, 'j1': p1['잔액'] if p1 is not None else 0, 'd1': get_dso(1),
                    'm2': p2['매출'] if p2 is not None else 0, 's2': p2['수금'] if p2 is not None else 0, 'j2': p2['잔액'] if p2 is not None else 0, 'd2': get_dso(2)
                })
    
            final_df = pd.DataFrame(cards_data)
            if not final_df.empty:
                if sort_opt == "잔액순":
                    final_df = final_df.sort_values('j0', ascending=False)
                elif sort_opt == "DSO 위험순":
                    final_df = final_df.sort_values('d0', ascending=False)
                else:
                    final_df = final_df.sort_values('name')
    
                c1, c2, c3 = st.columns(3)
                c1.metric("총 미수잔액", f"{int(final_df['j0'].sum() / 10000):,}만")
                c2.metric("당월 총 매출", f"{int(final_df['m0'].sum() / 10000):,}만")
                c3.metric("대상 업체수", f"{len(final_df)}개")
                st.markdown("---")
    
                for _, row in final_df.iterrows():
                    st.markdown(f"""
                        <div class="ar-container">
                            <div class="header-row">
                                <span class="title-txt">{row['name']}</span>
                                <span class="mgr-txt">🙍‍♂️ {row['mgr']}</span>
                            </div>
                    """, unsafe_allow_html=True)
    
                    col_data, col_graph = st.columns([2.5, 1.5])
                    
                    with col_data:
                        c_m2, c_m1, c_m0 = st.columns(3)
                        
                        def get_diff_text(c, p):
                            diff = c - p
                            if diff == 0: return ""
                            return f"<span class='diff-up'>(🔺{int(diff):,})</span>" if diff > 0 else f"<span class='diff-down'>(🔻{abs(int(diff)):,})</span>"
    
                        def get_dso_html(v):
                            color = "🔴" if v > 90 or v == 9999 else ("🟡" if v > 45 else "🟢")
                            txt = "장기(F)" if v == 9999 else f"{v}일"
                            return f'<span class="traffic-light">{color}</span><b>{txt}</b>'
    
                        month_data = [
                            (c_m2, m2, row['m2'], row['s2'], row['j2'], row['d2'], ""),
                            (c_m1, m1, row['m1'], row['s1'], row['j1'], row['d1'], get_diff_text(row['j1'], row['j2'])),
                            (c_m0, f"{m0} (당월)", row['m0'], row['s0'], row['j0'], row['d0'], get_diff_text(row['j0'], row['j1']))
                        ]
    
                        for col, title, m, s, j, d, j_diff in month_data:
                            with col:
                                st.markdown(f"""
                                    <div class="data-column">
                                        <div>
                                            <div class="col-title">{title}</div>
                                            <div class="row-item"><span class="label-xl">매출</span><span class="val-xl">{int(m):,}</span></div>
                                            <div class="row-item"><span class="label-xl">수금</span><span class="val-xl">{int(s):,}</span></div>
                                            <div class="row-item"><span class="label-xl">잔액</span><span class="val-xl">{int(j):,}</span></div>
                                            <div style="text-align:right; font-size:0.9rem; min-height:22px;">{j_diff}</div>
                                        </div>
                                        <div style="text-align:center; margin-top:10px; border-top:1px dashed #ccc; padding-top:12px;">
                                            {get_dso_html(d)}
                                        </div>
                                    </div>
                                """, unsafe_allow_html=True)
    
                    with col_graph:
                        st.markdown('<div class="graph-title">📈 12개월 추이</div>', unsafe_allow_html=True)
                        
                        plot_df = row['trend'].copy().reset_index(drop=True)
                        plot_df.index = range(1, len(plot_df) + 1)
                        plot_df.index.name = 'M'
                        plot_df = plot_df.reset_index().melt('M', var_name='항목', value_name='금액')
                        
                        chart = alt.Chart(plot_df).mark_line(point=True, strokeWidth=2.5).encode(
                            x=alt.X('M:O', title=None, axis=alt.Axis(labelAngle=0, labelColor='#555')),
                            y=alt.Y('금액:Q', title=None, axis=alt.Axis(format=',.0f', labelColor='#555')),
                            color=alt.Color(
                                '항목:N', 
                                scale=alt.Scale(domain=['잔액', '매출', '수금'], range=['#ff4b4b', '#007bff', '#28a745']),
                                legend=alt.Legend(orient='top', title=None, direction='horizontal', padding=0)
                            ),
                            tooltip=[alt.Tooltip('M:O', title='개월차'), '항목', alt.Tooltip('금액:Q', format=',')]
                        ).properties(
                            height=280
                        )
                        
                        st.altair_chart(chart, use_container_width=True, theme=None)
    
                    memo_v = df_memo_gs[df_memo_gs['거래처명'] == row['name']]['메모'].iloc[0] if row['name'] in df_memo_gs['거래처명'].values else ""
                    m_col, b_col = st.columns([6, 1])
                    with m_col:
                        memo_input = st.text_input(f"메모 ({row['name']})", value=memo_v, key=f"input_{row['name']}", label_visibility="collapsed")
                    with b_col:
                        if st.button("💾 저장", key=f"save_{row['name']}", use_container_width=True):
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
    
                            try:
                                client = get_gspread_client() 
                                doc = client.open("통합재고관리")
                                sheet = doc.worksheet("ar_memo")
                                
                                all_memos = df_memo_gs.set_index('거래처명')['메모'].to_dict()
                                all_memos[row['name']] = memo_input
                                sheet.clear()
                                sheet.update([['거래처명', '메모']] + [[k, v] for k, v in all_memos.items()])
                                
                                st.session_state.ar_memo_data = pd.DataFrame(list(all_memos.items()), columns=['거래처명', '메모'])
                                st.toast("성공적으로 저장되었습니다!")
                            except Exception as e:
                                st.error(f"저장 실패: {e}")
                            
                            placeholder.empty()
                            st.rerun()
                    st.markdown('</div></div>', unsafe_allow_html=True)
    
    except Exception as e:
        st.error(f"오류: {e}")
