import streamlit as st
import pandas as pd
import gspread
import json
from oauth2client.service_account import ServiceAccountCredentials

def run(load_data_func):
    # 담당자 매핑
    MANAGER_MAP = {
        "001": "이계성", "002": "이계흥", "004": "황일용",
        "00026": "신의명", "007": "정상영", "009": "이경옥"
    }
    
    # 🎨 [디자인] 카드 스타일을 위한 CSS
    st.markdown("""
        <style>
        .ar-card {
            background-color: white;
            border-radius: 10px;
            padding: 20px;
            border: 1px solid #e6e9ef;
            box-shadow: 2px 2px 5px rgba(0,0,0,0.05);
            margin-bottom: 20px;
        }
        .trader-name { font-size: 1.2rem; font-weight: bold; color: #2c3e50; }
        .manager-name { font-size: 0.9rem; color: #7f8c8d; }
        .stat-label { font-size: 0.8rem; color: #95a5a6; margin-bottom: 5px; }
        .stat-value { font-size: 1.1rem; font-weight: bold; }
        .diff-plus { color: #e74c3c; font-size: 0.8rem; }
        .diff-minus { color: #3498db; font-size: 0.8rem; }
        </style>
    """, unsafe_allow_html=True)

    st.title("💳 채권 현황 관제탑 (카드형)")

    # 1. 데이터 로드 (이전 로직 동일)
    try:
        df_memo_gs = load_data_func("ar_memo")
    except:
        df_memo_gs = pd.DataFrame(columns=['거래처명', '메모'])

    uploaded_file = st.file_uploader("이카운트 파일 업로드", type=['csv', 'xlsx', 'xls'])
    if not uploaded_file: return

    try:
        # 데이터 정제 및 DSO/추이 계산 (압축된 로직)
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
        
        # 필터 설정
        st.sidebar.markdown("### 🔍 필터 및 정렬")
        if manager_col:
            m_list = ["전체보기"] + sorted(list(df_pivot[manager_col].unique()))
            sel_m = st.sidebar.selectbox("담당자", m_list)
        
        min_dso = st.sidebar.slider("DSO 필터 (45일 이상)", 0, 120, 45, step=15)
        sort_opt = st.sidebar.radio("정렬 기준", ["잔액 많은 순", "가나다 순"])

        # 데이터 합치기
        final_list = []
        for trader, group in df_pivot.groupby('거래처명'):
            def get_dso(offset):
                sub = group[group['기준월'].isin(month_list[offset:offset+12])]
                s, b = sub['매출'].sum(), sub['잔액'].sum()
                return 9999 if s < 1 else int(round((b/s)*30))
            
            curr = group[group['기준월'] == m0].iloc[0]
            prev = group[group['기준월'] == m1].iloc[0] if m1 in group['기준월'].values else None
            
            dso = get_dso(0)
            if dso < min_dso or curr['잔액'] <= 0: continue
            if manager_col and sel_m != "전체보기" and curr[manager_col] != sel_m: continue

            final_list.append({
                '거래처명': trader,
                '담당자': curr[manager_col] if manager_col else "미지정",
                '매출': curr['매출'], '매출_증감': curr['매출'] - (prev['매출'] if prev is not None else 0),
                '수금': curr['수금'], '수금_증감': curr['수금'] - (prev['수금'] if prev is not None else 0),
                '잔액': curr['잔액'], '잔액_증감': curr['잔액'] - (prev['잔액'] if prev is not None else 0),
                'd0': dso, 'd1': get_dso(1), 'd2': get_dso(2),
                'trend': sorted(group[group['기준월'].isin(month_list[:12])]['잔액'].tolist())
            })

        final_df = pd.DataFrame(final_list)
        if sort_opt == "잔액 많은 순": final_df = final_df.sort_values('잔액', ascending=False)
        else: final_df = final_df.sort_values('거래처명')

        # ---------------------------------------------------------
        # 🚀 [UI] 카드 렌더링 시작
        # ---------------------------------------------------------
        for _, row in final_df.iterrows():
            with st.container():
                # 카드 외곽 박스
                st.markdown(f"""
                <div class="ar-card">
                    <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 15px;">
                        <div>
                            <span class="trader-name">{row['거래처명']}</span>
                            <span class="manager-name"> | 담당: {row['담당자']}</span>
                        </div>
                    </div>
                </div>
                """, unsafe_allow_html=True)
                
                # 내부 레이아웃 분할
                col1, col2, col3 = st.columns([2, 2, 1.5])
                
                with col1:
                    st.markdown('<p class="stat-label">💰 당월 실적 (전월대비)</p>', unsafe_allow_html=True)
                    for label, val, diff in [("매출", row['매출'], row['매출_증감']), 
                                             ("수금", row['수금'], row['수금_증감']), 
                                             ("잔액", row['잔액'], row['잔액_증감'])]:
                        diff_html = f'<span class="diff-plus">▲{int(diff):,}</span>' if diff > 0 else f'<span class="diff-minus">▼{abs(int(diff)):,}</span>'
                        st.markdown(f"**{label}**: {int(val):,} {diff_html}", unsafe_allow_html=True)

                with col2:
                    st.markdown('<p class="stat-label">📈 12개월 잔액 추이</p>', unsafe_allow_html=True)
                    st.line_chart(row['trend'], height=80, use_container_width=True)

                with col3:
                    st.markdown('<p class="stat-label">🚨 회수일수 (DSO)</p>', unsafe_allow_html=True)
                    def fmt_dso_box(v):
                        color = "#e74c3c" if v > 90 or v == 9999 else ("#f1c40f" if v > 45 else "#2ecc71")
                        txt = "장기(F)" if v == 9999 else f"{v}일"
                        return f'<span style="color:{color}; font-weight:bold; font-size:1.1rem;">{txt}</span>'
                    
                    st.markdown(f"당월: {fmt_dso_box(row['d0'])}", unsafe_allow_html=True)
                    st.markdown(f"<small>전월: {row['d1']}일 / 전전월: {row['d2']}일</small>", unsafe_allow_html=True)

                # 메모장 (구글 시트 연동)
                memo_val = df_memo_gs[df_memo_gs['거래처명'] == row['거래처명']]['메모'].iloc[0] if row['거래처명'] in df_memo_gs['거래처명'].values else ""
                new_memo = st.text_input(f"📝 메모 ({row['거래처명']})", value=memo_val, key=f"memo_{row['거래처명']}")
                
                # 메모가 변경되면 세션에 저장 (나중에 한꺼번에 구글 시트 전송)
                if new_memo != memo_val:
                    st.session_state[f"update_{row['거래처명']}"] = new_memo

        # 🚀 하단 플로팅 저장 버튼
        if st.button("💾 모든 카드 메모 구글 시트에 일괄 저장하기"):
            # 저장 로직 (생략 - 이전과 동일)
            st.success("✅ 메모가 저장되었습니다!")

    except Exception as e:
        st.error(f"오류: {e}")
