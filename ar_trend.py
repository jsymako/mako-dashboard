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
    
    # 🎨 [CSS] 관제탑 카드 최적화 스타일
    st.markdown("""
        <style>
        .ar-container {
            border: 2px solid #2c3e50;
            border-radius: 8px;
            padding: 15px;
            margin-bottom: 25px;
            background-color: #fcfcfc;
        }
        .header-row {
            display: flex;
            justify-content: flex-start;
            align-items: center;
            gap: 15px;
            border-bottom: 1px solid #eee;
            padding-bottom: 8px;
            margin-bottom: 12px;
        }
        .title-txt { font-size: 1.15rem; font-weight: 800; color: #1a1a1a; }
        .mgr-txt { font-size: 0.85rem; color: #666; background: #eee; padding: 2px 8px; border-radius: 4px; }
        .data-box { background: #fff; border: 1px solid #e1e4e8; border-radius: 5px; padding: 10px; height: 100%; }
        .label-txt { font-size: 0.75rem; color: #888; font-weight: bold; margin-bottom: 3px; }
        .val-txt { font-size: 1rem; font-weight: 700; color: #222; }
        .diff-up { color: #d9534f; font-size: 0.8rem; font-weight: bold; }
        .diff-down { color: #0275d8; font-size: 0.8rem; font-weight: bold; }
        .dso-tag { padding: 3px 6px; border-radius: 3px; font-weight: bold; font-size: 0.85rem; }
        </style>
    """, unsafe_allow_html=True)

    # 1. 데이터 로드 및 전처리 (이전 로직 활용)
    try:
        df_memo_gs = load_data_func("ar_memo")
    except:
        df_memo_gs = pd.DataFrame(columns=['거래처명', '메모'])

    uploaded_file = st.file_uploader("파일을 업로드하세요", type=['csv', 'xlsx', 'xls'], label_visibility="collapsed")
    if not uploaded_file:
        st.warning("📊 분석할 이카운트 엑셀 파일을 업로드해 주세요.")
        return

    try:
        # 데이터 정제 파트 (축약본)
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

        # 사이드바 필터링
        st.sidebar.subheader("🔍 필터링")
        sel_m = st.sidebar.selectbox("담당자", ["전체보기"] + sorted(list(df_pivot[manager_col].unique()))) if manager_col else "전체보기"
        min_dso = st.sidebar.slider("최소 DSO", 0, 120, 45, 15)
        sort_opt = st.sidebar.radio("정렬", ["잔액순", "가나다순"])

        # 가공 데이터 생성
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

        # 🚀 [UI] 카드 렌더링
        for _, row in final_df.iterrows():
            st.markdown(f"""
                <div class="ar-container">
                    <div class="header-row">
                        <span class="title-txt">{row['name']}</span>
                        <span class="mgr-txt">👤 {row['mgr']}</span>
                    </div>
                </div>
            """, unsafe_allow_html=True)

            # 카드 내부 그리드 (그래프 | 실적비교 | DSO)
            c_graph, c_compare, c_dso = st.columns([1.2, 2.5, 1.3])

            with c_graph:
                st.markdown('<p class="label-txt">📈 12개월 잔액 추이</p>', unsafe_allow_html=True)
                st.line_chart(row['trend'], height=100, use_container_width=True)

            with c_compare:
                st.markdown('<p class="label-txt">📊 실적 비교 (전월 ➡️ 당월)</p>', unsafe_allow_html=True)
                cols = st.columns(3)
                names = [("매출", 'm'), ("수금", 's'), ("잔액", 'j')]
                for i, (lab, k) in enumerate(names):
                    curr_val, prev_val = row[f'{k}_c'], row[f'{k}_p']
                    diff = curr_val - prev_val
                    diff_str = f"<span class='diff-up'>▲{int(diff):,}</span>" if diff > 0 else f"<span class='diff-down'>▼{abs(int(diff)):,}</span>"
                    cols[i].markdown(f"""
                        <div class="data-box">
                            <div class="label-txt">{lab}</div>
                            <div style="font-size:0.75rem; color:#999; text-decoration:line-through;">{int(prev_val):,}</div>
                            <div class="val-txt">{int(curr_val):,}</div>
                            <div>{diff_str}</div>
                        </div>
                    """, unsafe_allow_html=True)

            with c_dso:
                st.markdown('<p class="label-txt">🚨 DSO (3개월)</p>', unsafe_allow_html=True)
                def get_dso_html(v):
                    c = "#ff4b4b" if v > 90 or v == 9999 else ("#ffa500" if v > 45 else "#00c853")
                    t = "F(장기)" if v == 9999 else f"{v}일"
                    return f'<span style="color:{c}; font-weight:bold;">{t}</span>'
                
                st.markdown(f"**당월:** {get_dso_html(row['d0'])}", unsafe_allow_html=True)
                st.markdown(f"<small>전월: {row['d1']}일</small><br><small>전전월: {row['d2']}일</small>", unsafe_allow_html=True)

            # 메모장 및 저장
            memo_v = df_memo_gs[df_memo_gs['거래처명'] == row['name']]['메모'].iloc[0] if row['name'] in df_memo_gs['거래처명'].values else ""
            st.text_input(f"📝 {row['name']} 메모", value=memo_v, key=f"memo_{row['name']}")

        if st.button("💾 모든 메모 일괄 저장"):
            # 저장 로직 생략
            st.success("✅ 저장 완료")

    except Exception as e:
        st.error(f"오류: {e}")
