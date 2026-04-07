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

    # 🎨 [CSS] 초슬림 카드 및 레이아웃 최적화
    st.markdown("""
        <style>
        .ar-container {
            border: 1px solid #333;
            border-radius: 6px;
            padding: 12px;
            margin-bottom: 15px;
            background-color: #fff;
        }
        .header-row {
            display: flex;
            align-items: center;
            gap: 10px;
            margin-bottom: 8px;
        }
        .title-txt { font-size: 1.1rem; font-weight: 800; color: #000; }
        .mgr-txt { font-size: 0.8rem; color: #555; background: #f0f0f0; padding: 1px 6px; border-radius: 3px; }
        .data-column { background: #f9f9f9; border: 1px solid #eee; border-radius: 4px; padding: 8px; }
        .row-item { display: flex; justify-content: space-between; font-size: 0.85rem; margin-bottom: 2px; }
        .label-sm { color: #888; }
        .val-sm { font-weight: 700; }
        .diff-up { color: #d9534f; font-size: 0.75rem; font-weight: bold; }
        .diff-down { color: #0275d8; font-size: 0.75rem; font-weight: bold; }
        </style>
    """, unsafe_allow_html=True)

    st.title("💳 채권 현황 분석 관제탑")

    # 1. 데이터 로드 및 전처리
    try:
        df_memo_gs = load_data_func("ar_memo")
    except:
        df_memo_gs = pd.DataFrame(columns=['거래처명', '메모'])

    uploaded_file = st.file_uploader("파일 업로드", type=['csv', 'xlsx', 'xls'], label_visibility="collapsed")
    if not uploaded_file:
        st.info("📊 분석할 이카운트 엑셀 파일을 업로드해 주세요.")
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
        m0, m1 = month_list[0], (month_list[1] if len(month_list) > 1 else None)

        # 사이드바 설정
        st.sidebar.subheader("🔍 분석 조건")
        sel_m = st.sidebar.selectbox("담당자", ["전체보기"] + sorted(list(df_pivot[manager_col].unique()))) if manager_col else "전체보기"
        min_dso = st.sidebar.slider("DSO 필터", 0, 120, 45, 15)
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

            prev = group[group['기준월'] == m1].iloc[0] if m1 in group['기준월'].values else None
            trend = group[group['기준월'].isin(sorted(month_list[:12]))].sort_values('기준월')['잔액'].tolist()
            
            cards_data.append({
                'name': trader, 'mgr': curr[manager_col], 'trend': trend,
                'm_c': curr['매출'], 'm_p': prev['매출'] if prev is not None else 0,
                's_c': curr['수금'], 's_p': prev['수금'] if prev is not None else 0,
                'j_c': curr['잔액'], 'j_p': prev['잔액'] if prev is not None else 0,
                'd0': d0, 'd1': get_dso(1), 'd2': get_dso(2)
            })

        final_df = pd.DataFrame(cards_data)
        if not final_df.empty:
            final_df = final_df.sort_values('j_c', ascending=False) if sort_opt == "잔액순" else final_df.sort_values('name')

            # 🚀 [UI] 상단 전체 현황(KPI)
            c1, c2, c3 = st.columns(3)
            c1.metric("💰 총 미수잔액", f"{int(final_df['j_c'].sum() / 10000):,}만 원")
            c2.metric("📈 당월 총 매출", f"{int(final_df['m_c'].sum() / 10000):,}만 원")
            c3.metric("🚨 대상 업체수", f"{len(final_df)}개")
            st.markdown("---")

            # 🚀 [UI] 개별 카드 렌더링
            for _, row in final_df.iterrows():
                st.markdown(f"""
                    <div class="ar-container">
                        <div class="header-row">
                            <span class="title-txt">{row['name']}</span>
                            <span class="mgr-txt">👤 {row['mgr']}</span>
                        </div>
                """, unsafe_allow_html=True)

                c_graph, c_compare, c_dso = st.columns([1, 2.5, 1.2])

                with c_graph:
                    st.line_chart(row['trend'], height=90, use_container_width=True)

                with c_compare:
                    c_prev, c_curr = st.columns(2)
                    with c_prev:
                        st.markdown(f"""
                            <div class="data-column">
                                <div style="font-size:0.7rem; color:#888; font-weight:bold; margin-bottom:5px;">⏮️ 전월 실적</div>
                                <div class="row-item"><span class="label-sm">매출</span><span class="val-sm">{int(row['m_p']):,}</span></div>
                                <div class="row-item"><span class="label-sm">수금</span><span class="val-sm">{int(row['s_p']):,}</span></div>
                                <div class="row-item"><span class="label-sm">잔액</span><span class="val-sm">{int(row['j_p']):,}</span></div>
                            </div>
                        """, unsafe_allow_html=True)
                    with c_curr:
                        def get_diff(c, p):
                            diff = c - p
                            return f"<span class='diff-up'>▲{int(diff):,}</span>" if diff > 0 else f"<span class='diff-down'>▼{abs(int(diff)):,}</span>"
                        
                        st.markdown(f"""
                            <div class="data-column" style="border-color:#333;">
                                <div style="font-size:0.7rem; color:#333; font-weight:bold; margin-bottom:5px;">⬇️ 당월 실적(증감)</div>
                                <div class="row-item"><span class="label-sm">매출</span><span class="val-sm">{int(row['m_c']):,} {get_diff(row['m_c'], row['m_p'])}</span></div>
                                <div class="row-item"><span class="label-sm">수금</span><span class="val-sm">{int(row['s_c']):,} {get_diff(row['s_c'], row['s_p'])}</span></div>
                                <div class="row-item"><span class="label-sm" style="color:#d9534f;">잔액</span><span class="val-sm" style="color:#d9534f;">{int(row['j_c']):,} {get_diff(row['j_c'], row['j_p'])}</span></div>
                            </div>
                        """, unsafe_allow_html=True)

                with c_dso:
                    def get_dso_tag(v):
                        c = "#d9534f" if v > 90 or v == 9999 else ("#f0ad4e" if v > 45 else "#5cb85c")
                        t = "F" if v == 9999 else f"{v}d"
                        return f'<span style="color:{c}; font-weight:bold;">{t}</span>'
                    
                    st.markdown(f"""
                        <div style="text-align:right; font-size:0.8rem; line-height:1.6;">
                            <div style="color:#888;">DSO 흐름</div>
                            <div>{get_dso_tag(row['d2'])} ➔ {get_dso_tag(row['d1'])} ➔ <span style="font-size:1.1rem;">{get_dso_tag(row['d0'])}</span></div>
                        </div>
                    """, unsafe_allow_html=True)

                # 🚀 메모 및 개별 저장 버튼
                memo_v = df_memo_gs[df_memo_gs['거래처명'] == row['name']]['메모'].iloc[0] if row['name'] in df_memo_gs['거래처명'].values else ""
                m_col, b_col = st.columns([5, 1])
                with m_col:
                    memo_input = st.text_input(f"메모 입력 ({row['name']})", value=memo_v, key=f"input_{row['name']}", label_visibility="collapsed")
                with b_col:
                    if st.button("💾", key=f"save_{row['name']}", help="이 업체 메모만 즉시 저장"):
                        # 구글 시트 개별 업데이트 로직
                        scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
                        creds_dict = json.loads(st.secrets["gcp_service_account"])
                        creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
                        client = gspread.authorize(creds)
                        doc = client.open("통합재고관리")
                        sheet = doc.worksheet("ar_memo")
                        
                        # 기존 메모 로드 후 해당 행만 수정하거나 전체 업데이트
                        all_memos = df_memo_gs.set_index('거래처명')['메모'].to_dict()
                        all_memos[row['name']] = memo_input
                        
                        new_data = [[k, v] for k, v in all_memos.items()]
                        sheet.clear()
                        sheet.update([['거래처명', '메모']] + new_data)
                        st.toast(f"{row['name']} 저장 완료!", icon="✅")

                st.markdown("</div>", unsafe_allow_html=True)

    except Exception as e:
        st.error(f"오류: {e}")
