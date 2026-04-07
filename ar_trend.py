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

    # 🎨 [CSS] 글자 크기 확대 및 여백 최적화
    st.markdown("""
        <style>
        .ar-container {
            border: 2px solid #333;
            border-radius: 10px;
            padding: 20px;
            margin-bottom: 30px;
            background-color: #fff;
        }
        .title-txt { font-size: 1.4rem; font-weight: 800; color: #000; }
        .mgr-txt { font-size: 1.0rem; color: #555; background: #f0f0f0; padding: 2px 10px; border-radius: 4px; }
        .data-column { 
            background: #fcfcfc; 
            border: 1px solid #ddd; 
            border-radius: 6px; 
            padding: 15px; 
            height: 100%;
        }
        .col-title { font-size: 0.95rem; font-weight: bold; margin-bottom: 10px; text-align: center; border-bottom: 1px solid #eee; padding-bottom: 5px; }
        .row-item { display: flex; justify-content: space-between; font-size: 1.1rem; margin-bottom: 8px; }
        .label-lg { color: #666; font-weight: 500; }
        .val-lg { font-weight: 700; color: #111; }
        .diff-up { color: #d9534f; font-size: 0.9rem; font-weight: bold; }
        .diff-down { color: #0275d8; font-size: 0.9rem; font-weight: bold; }
        .dso-box { text-align: center; margin-top: 10px; padding-top: 10px; border-top: 1px dashed #ccc; }
        .memo-area { margin-top: 25px; border-top: 1px solid #eee; padding-top: 15px; }
        </style>
    """, unsafe_allow_html=True)

    st.title("💳 채권 현황 3개월 통합 분석")

    # 1. 데이터 로드
    try:
        df_memo_gs = load_data_func("ar_memo")
    except:
        df_memo_gs = pd.DataFrame(columns=['거래처명', '메모'])

    uploaded_file = st.file_uploader("파일 업로드", type=['csv', 'xlsx', 'xls'], label_visibility="collapsed")
    if not uploaded_file:
        st.info("📊 최근 3개월 추적을 위해 이카운트 엑셀 파일을 업로드해 주세요.")
        return

    try:
        # 데이터 정제 로직
        if uploaded_file.name.endswith('.csv'):
            try: df_raw = pd.read_csv(uploaded_file, encoding='utf-8')
            except: df_raw = pd.read_csv(uploaded_file, encoding='cp949')
        else: df_raw = pd.read_excel(uploaded_file)

        header_idx = df_raw[df_raw.apply(lambda r: r.astype(str).str.contains('거래처명').any(), axis=1)].index[0]
        df_raw.columns = df_raw.iloc[header_idx]
        df = df_raw.iloc[header_idx+1:].reset_index(drop=True)
        df['거래처명'] = df['거래처명'].ffill()
        
        manager_col = next((c for c in df.columns if '담당자' in str(c)), None)
        if manager_col:
            df[manager_col] = df[manager_col].ffill().astype(str).str.strip().apply(lambda x: MANAGER_MAP.get(x, x))

        month_cols = [c for c in df.columns if '20' in str(c) and ('/' in str(c) or '-' in str(c))]
        df_melt = df.melt(id_vars=['거래처명', '구분'] + ([manager_col] if manager_col else []), value_vars=month_cols, var_name='기준월', value_name='금액')
        df_melt['금액'] = pd.to_numeric(df_melt['금액'].astype(str).str.replace(',', ''), errors='coerce').fillna(0)
        df_pivot = df_melt.pivot_table(index=['거래처명', '기준월'] + ([manager_col] if manager_col else []), columns='구분', values='금액', aggfunc='sum').reset_index()

        month_list = sorted(list(df_pivot['기준월'].unique()), reverse=True)
        m0, m1, m2 = month_list[0], (month_list[1] if len(month_list) > 1 else None), (month_list[2] if len(month_list) > 2 else None)

        # 사이드바
        st.sidebar.subheader("🔍 분석 조건")
        sel_m = st.sidebar.selectbox("담당자", ["전체보기"] + sorted(list(df_pivot[manager_col].unique()))) if manager_col else "전체보기"
        min_dso = st.sidebar.slider("DSO 필터 (당월 기준)", 0, 120, 45, 15)
        sort_opt = st.sidebar.radio("정렬", ["잔액순", "가나다순"])

        cards_data = []
        for trader, group in df_pivot.groupby('거래처명'):
            def get_dso(off):
                sub = group[group['기준월'].isin(month_list[off:off+12])]
                s, b = sub['매출'].sum(), sub['잔액'].sum()
                return 9999 if s < 1 else int(round((b/s)*30))
            
            d0 = get_dso(0)
            curr = group[group['기준월'] == m0].iloc[0]
            if d0 < min_dso or curr['잔액'] <= 0: continue
            if sel_m != "전체보기" and curr[manager_col] != sel_m: continue

            # 3개월치 데이터 추출
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
            final_df = final_df.sort_values('j0', ascending=False) if sort_opt == "잔액순" else final_df.sort_values('name')

            # 전체 KPI
            c1, c2, c3 = st.columns(3)
            c1.metric("💰 총 미수잔액", f"{int(final_df['j0'].sum() / 10000):,}만 원")
            c2.metric("📈 당월 총 매출", f"{int(final_df['m0'].sum() / 10000):,}만 원")
            c3.metric("🚨 대상 업체수", f"{len(final_df)}개")
            st.markdown("---")

            for _, row in final_df.iterrows():
                st.markdown(f"""
                    <div class="ar-container">
                        <div class="header-row">
                            <span class="title-txt">{row['name']}</span>
                            <span class="mgr-txt">👤 {row['mgr']}</span>
                        </div>
                """, unsafe_allow_html=True)

                col_graph, col_data = st.columns([1, 4])
                with col_graph:
                    st.markdown('<p style="font-size:0.8rem; color:#888;">📈 잔액 추이</p>', unsafe_allow_html=True)
                    st.line_chart(row['trend'], height=150, use_container_width=True)

                with col_data:
                    c_m2, c_m1, c_m0 = st.columns(3)
                    
                    def get_diff_html(c, p):
                        diff = c - p
                        if diff == 0: return ""
                        return f"<span class='diff-up'>▲{int(diff):,}</span>" if diff > 0 else f"<span class='diff-down'>▼{abs(int(diff)):,}</span>"

                    def get_dso_tag(v):
                        c = "#d9534f" if v > 90 or v == 9999 else ("#f0ad4e" if v > 45 else "#5cb85c")
                        t = "장기(F)" if v == 9999 else f"{v}일"
                        return f'<span style="color:{c}; font-weight:bold;">{t}</span>'

                    # 각 월별 기둥 렌더링
                    for col, m_idx, title in [(c_m2, '2', f"⏮️ {m2}"), (c_m1, '1', f"⬅️ {m1}"), (c_m0, '0', f"⬇️ {m0} (당월)")]:
                        with col:
                            diff_j = get_diff_html(row[f'j{m_idx}'], row[f'j{str(int(m_idx)+1)}']) if m_idx != '2' else ""
                            st.markdown(f"""
                                <div class="data-column">
                                    <div class="col-title">{title}</div>
                                    <div class="row-item"><span class="label-lg">매출</span><span class="val-lg">{int(row[f'm{m_idx}']):,}</span></div>
                                    <div class="row-item"><span class="label-lg">수금</span><span class="val-lg">{int(row[f's{m_idx}']):,}</span></div>
                                    <div class="row-item"><span class="label-lg">잔액</span><span class="val-lg">{int(row[f'j{m_idx}']):,} {diff_j}</span></div>
                                    <div class="dso-box">
                                        <div style="font-size:0.75rem; color:#888;">DSO 회수</div>
                                        <div style="font-size:1.1rem;">{get_dso_tag(row[f'd{m_idx}'])}</div>
                                    </div>
                                </div>
                            """, unsafe_allow_html=True)

                # 🚀 메모 섹션 (여백 확보 및 디자인 개선)
                st.markdown('<div class="memo-area">', unsafe_allow_html=True)
                memo_v = df_memo_gs[df_memo_gs['거래처명'] == row['name']]['메모'].iloc[0] if row['name'] in df_memo_gs['거래처명'].values else ""
                m_col, b_col = st.columns([6, 1])
                with m_col:
                    memo_input = st.text_input(f"메모 ({row['name']})", value=memo_v, key=f"input_{row['name']}", label_visibility="collapsed", placeholder="영업 의견이나 특이사항을 입력하세요...")
                with b_col:
                    if st.button("💾 저장", key=f"save_{row['name']}"):
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
                        st.toast(f"{row['name']} 저장 완료!", icon="✅")
                st.markdown('</div></div>', unsafe_allow_html=True)

    except Exception as e:
        st.error(f"데이터 처리 오류: {e}")
