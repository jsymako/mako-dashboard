import streamlit as st
import pandas as pd
import gspread
import json
from oauth2client.service_account import ServiceAccountCredentials

def run(load_data_func):


        
    MANAGER_MAP = {
        "001": "이계성", "002": "이계흥", "004": "황일용",
        "00026": "신의명", "007": "정상영", "009": "이경옥"
    }
    MANAGER_ORDER = ["이계성", "이계흥", "황일용", "신의명", "정상영", "이경옥"]

    # 🎨 [CSS] 데이터 카드 디자인 (업로더 관련 억지 CSS는 없습니다)
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

    st.title("💳 채권 분석")

    try:
        df_memo_gs = load_data_func("ar_memo")
    except:
        df_memo_gs = pd.DataFrame(columns=['거래처명', '메모'])

    # =================================================================
    # 🚀 [UI 혁신] 뚱뚱한 박스를 안 보이게 접어두는 얇은 바(Expander) 적용
    # =================================================================
    with st.expander("📂 분석할 이카운트 엑셀 파일 업로드 (여기를 클릭하세요!)", expanded=True):
        uploaded_file = st.file_uploader("", type=['csv', 'xlsx', 'xls'], label_visibility="collapsed")

    if not uploaded_file:
        st.info("👆 위 탭을 열어서 파일을 끌어다 놓아주세요. (글자 겹침 문제가 완벽히 사라집니다.)")
        return

    try:
        if uploaded_file.name.endswith('.csv'):
            try: df_raw = pd.read_csv(uploaded_file, encoding='utf-8')
            except: df_raw = pd.read_csv(uploaded_file, encoding='cp949')
        else:
            df_raw = pd.read_excel(uploaded_file)

        header_idx = df_raw[df_raw.apply(lambda r: r.astype(str).str.contains('거래처명').any(), axis=1)].index[0]
        df_raw.columns = df_raw.iloc[header_idx]
        df = df_raw.iloc[header_idx+1:].reset_index(drop=True)
        
        df = df[~df['거래처명'].astype(str).str.contains('계|합계|누계', na=False)]
        df['거래처명'] = df['거래처명'].ffill()
        
        manager_col = next((c for c in df.columns if '담당자' in str(c)), None)
        if manager_col:
            df[manager_col] = df[manager_col].ffill().astype(str).str.strip().apply(lambda x: MANAGER_MAP.get(x, "기타/미지정"))

        month_cols = [c for c in df.columns if '20' in str(c) and ('/' in str(c) or '-' in str(c))]
        df_melt = df.melt(id_vars=['거래처명', '구분'] + ([manager_col] if manager_col else []), value_vars=month_cols, var_name='기준월', value_name='금액')
        df_melt['금액'] = pd.to_numeric(df_melt['금액'].astype(str).str.replace(',', ''), errors='coerce').fillna(0)
        df_pivot = df_melt.pivot_table(index=['거래처명', '기준월'] + ([manager_col] if manager_col else []), columns='구분', values='금액', aggfunc='sum').reset_index()

        month_list = sorted(list(df_pivot['기준월'].unique()), reverse=True)
        m0, m1, m2 = month_list[0], (month_list[1] if len(month_list) > 1 else None), (month_list[2] if len(month_list) > 2 else None)

        st.sidebar.subheader("🔍 필터")
        valid_mgrs = [m for m in MANAGER_ORDER if m in df_pivot[manager_col].unique()]
        sel_m = st.sidebar.selectbox("담당자 선택", ["전체보기"] + valid_mgrs) if manager_col else "전체보기"
        hide_zero = st.sidebar.checkbox("✅ 당월 잔액 0원 숨기기", value=True)
        min_dso = st.sidebar.slider("DSO 필터 (최소 일수)", 0, 120, 45, 15)
        sort_opt = st.sidebar.radio("목록 정렬 기준", ["잔액순", "DSO 위험순", "가나다순"])

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
            trend = group[group['기준월'].isin(sorted(month_list[:12]))].sort_values('기준월')['잔액'].tolist()
            
            cards_data.append({
                'name': trader, 'mgr': curr[manager_col], 'trend': trend,
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
            c1.metric("💰 총 미수잔액", f"{int(final_df['j0'].sum() / 10000):,}만")
            c2.metric("📈 당월 총 매출", f"{int(final_df['m0'].sum() / 10000):,}만")
            c3.metric("🚨 대상 업체수", f"{len(final_df)}개")
            st.markdown("---")

            for _, row in final_df.iterrows():
                st.markdown(f"""
                    <div class="ar-container">
                        <div class="header-row">
                            <span class="title-txt">{row['name']}</span>
                            <span class="mgr-txt">🙍‍♂️ {row['mgr']}</span>
                        </div>
                """, unsafe_allow_html=True)

                col_data, col_graph = st.columns([3.5, 1])
                
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
                    st.markdown('<p style="font-size:1.0rem; color:#000; text-align:center; font-weight:900;">📈 12개월 추이</p>', unsafe_allow_html=True)
                    st.line_chart(row['trend'], height=240, use_container_width=True)

                st.markdown('<div class="memo-section">', unsafe_allow_html=True)
                memo_v = df_memo_gs[df_memo_gs['거래처명'] == row['name']]['메모'].iloc[0] if row['name'] in df_memo_gs['거래처명'].values else ""
                m_col, b_col = st.columns([6, 1])
                with m_col:
                    memo_input = st.text_input(f"메모 ({row['name']})", value=memo_v, key=f"input_{row['name']}", label_visibility="collapsed")
                with b_col:
                    if st.button("💾 저장", key=f"save_{row['name']}", use_container_width=True):
                        scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
                        creds_dict = json.loads(st.secrets["gcp_service_account"])
                        creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
                        client = gspread.authorize(creds)
                        doc = client.open("통합재고관리")
                        sheet = doc.worksheet("ar_memo")
                        
                        all_memos = df_memo_gs.set_index('거래처명')['메모'].to_dict()
                        all_memos[row['name']] = memo_input
                        sheet.clear()
                        sheet.update([['거래처명', '메모']] + [[k, v] for k, v in all_memos.items()])
                        st.toast(f"{row['name']} 저장!", icon="✅")
                st.markdown('</div></div>', unsafe_allow_html=True)

    except Exception as e:
        st.error(f"오류: {e}")
