import streamlit as st
import pandas as pd

def run():
    # 담당자 매핑
    MANAGER_MAP = {
        "001": "001:이계성", "002": "002:이계흥", "004": "004:황일용",
        "00026": "00026:신의명", "007": "007:정상영", "009": "009:이경옥"
    }
    MANAGER_ORDER = ["001:이계성", "002:이계흥", "004:황일용", "00026:신의명", "007:정상영", "009:이경옥"]

    try:
        with open("sales_trend.css", "r", encoding="utf-8") as f:
            st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)
    except FileNotFoundError:
        pass

    st.title("💳 채권(미수금) 현황 분석기")
    
    # ---------------------------------------------------------
    # 1. 파일 업로드 및 데이터 로드
    # ---------------------------------------------------------
    uploaded_file = st.file_uploader("이카운트 [월별채권증감내역] 업로드", type=['csv', 'xlsx', 'xls'])

    if uploaded_file is None:
        st.info("💡 분석할 파일을 업로드하면 12개월 추이와 DSO 분석이 시작됩니다.")
        return

    try:
        if uploaded_file.name.endswith('.csv'):
            try: df_raw = pd.read_csv(uploaded_file, encoding='utf-8')
            except: df_raw = pd.read_csv(uploaded_file, encoding='cp949')
        else:
            df_raw = pd.read_excel(uploaded_file)

        # 헤더 찾기 및 정제
        header_idx = df_raw[df_raw.apply(lambda r: r.astype(str).str.contains('거래처명').any(), axis=1)].index[0]
        df_raw.columns = df_raw.iloc[header_idx]
        df = df_raw.iloc[header_idx+1:].reset_index(drop=True)

        # 전처리
        manager_col = next((c for c in df.columns if '담당자' in str(c)), None)
        df['거래처명'] = df['거래처명'].ffill()
        if manager_col:
            df[manager_col] = df[manager_col].ffill().astype(str).str.strip().apply(lambda x: MANAGER_MAP.get(x, f"{x}:미등록"))
        
        df = df.dropna(subset=['구분'])
        month_cols = [c for c in df.columns if '20' in str(c) and ('/' in str(c) or '-' in str(c))]

        # 데이터 재구조화 (Melt & Pivot)
        id_vars = ['거래처명', '구분'] + ([manager_col] if manager_col else [])
        df_melt = df.melt(id_vars=id_vars, value_vars=month_cols, var_name='기준월', value_name='금액')
        df_melt['금액'] = pd.to_numeric(df_melt['금액'].astype(str).str.replace(',', ''), errors='coerce').fillna(0)
        
        pivot_idx = ['거래처명', '기준월'] + ([manager_col] if manager_col else [])
        df_pivot = df_melt.pivot_table(index=pivot_idx, columns='구분', values='금액', aggfunc='sum').reset_index()

        # DSO 및 12개월 추이 계산
        month_list = sorted(list(df_pivot['기준월'].unique()), reverse=True)
        m0, m1 = month_list[0], (month_list[1] if len(month_list) > 1 else None)
        
        # 🚀 스파크라인용 데이터 (순수 숫자 리스트 유지)
        past_12 = sorted(month_list[:12])
        trend_series = df_pivot[df_pivot['기준월'].isin(past_12)].sort_values('기준월').groupby('거래처명')['잔액'].apply(list).reset_index(name='trend_data')

        dso_results = []
        for trader, group in df_pivot.groupby('거래처명'):
            def get_dso(offset):
                target = month_list[offset : offset+12]
                sub = group[group['기준월'].isin(target)]
                s, b = sub['매출'].sum(), sub['잔액'].sum()
                return 9999 if s < 1 else int(round((b/s)*30))
            dso_results.append({'거래처명': trader, 'd0': get_dso(0), 'd1': get_dso(1), 'd2': get_dso(2)})
        
        # 데이터 병합
        final_df = df_pivot[df_pivot['기준월'] == m0].rename(columns={'매출':'당월 매출','수금':'당월 수금','잔액':'당월 잔액'})
        if m1:
            df_m1 = df_pivot[df_pivot['기준월'] == m1][['거래처명','매출','수금','잔액']].rename(columns={'매출':'전월 매출','수금':'전월 수금','잔액':'전월 잔액'})
            final_df = pd.merge(final_df, df_m1, on='거래처명', how='left')
        
        final_df = pd.merge(final_df, pd.DataFrame(dso_results), on='거래처명')
        final_df = pd.merge(final_df, trend_series, on='거래처명')

        # ---------------------------------------------------------
        # 2. 사이드바 필터 및 정렬
        # ---------------------------------------------------------
        st.sidebar.markdown("### 🔍 필터 설정")
        if manager_col:
            m_list = ["전체보기"] + [m for m in MANAGER_ORDER if m in final_df[manager_col].unique()]
            sel_m = st.sidebar.selectbox("담당자 선택", m_list)
            if sel_m != "전체보기": final_df = final_df[final_df[manager_col] == sel_m]
        
        min_dso = st.sidebar.slider("DSO 위험도 필터 (45일 이상)", 0, 120, 45, step=15)
        final_df = final_df[(final_df['당월 잔액'] > 0) & (final_df['d0'] >= min_dso)]
        
        sort_opt = st.sidebar.radio("정렬 기준", ["잔액 많은 순", "DSO 위험 순", "가나다 순"])
        sort_map = {"잔액 많은 순":('당월 잔액', False), "DSO 위험 순":('d0', False), "가나다 순":('거래처명', True)}
        final_df = final_df.sort_values(by=sort_map[sort_opt][0], ascending=sort_map[sort_opt][1])

        # ---------------------------------------------------------
        # 3. 메인 표 구성 (디자인 튜닝)
        # ---------------------------------------------------------
        # 신호등 로직
        def get_status(v):
            if v == 9999: return "🔴 F(장기)"
            if v > 365: return "🔴 ▲"
            if v > 90: return f"🔴 {v}일"
            if v > 45: return f"🟡 {v}일"
            return f"🟢 {v}일"

        # 표 표시용 가공
        res = final_df.copy()
        res['회수(전전월)'] = res['d2'].apply(get_status)
        res['회수(전월)'] = res['d1'].apply(get_status)
        res['회수(당월)'] = res['d0'].apply(get_status)
        res['비고(메모)'] = "" # 🚀 실제론 구글 시트에서 불러올 자리

        # 컬럼명 정리
        disp_cols = {
            '거래처명': '거래처명',
            'trend_data': '📈 1년 잔액 추이',
            '전월 매출': '⏮️ 전월 매출', '전월 수금': '⏮️ 전월 수금', '전월 잔액': '⏮️ 전월 잔액',
            '당월 매출': '⬇️ 당월 매출', '당월 수금': '⬇️ 당월 수금', '당월 잔액': '⬇️ 당월 잔액',
            '회수(전전월)': '🚨 전전월', '회수(전월)': '🚨 전월', '회수(당월)': '🚨 당월',
            '비고(메모)': '📝 영업 의견/메모'
        }
        res = res[list(disp_cols.keys())].rename(columns=disp_cols)

        # 🚀 [디자인의 핵심] st.data_editor 설정
        st.data_editor(
            res,
            use_container_width=True,
            hide_index=True,
            height=(len(res) + 1) * 38 + 100,
            column_config={
                "📈 1년 잔액 추이": st.column_config.LineChartColumn(width="medium"),
                "📝 영업 의견/메모": st.column_config.TextColumn(width="large", disabled=False),
                "⏮️ 전월 매출": st.column_config.NumberColumn(format="%d"),
                "⏮️ 전월 수금": st.column_config.NumberColumn(format="%d"),
                "⏮️ 전월 잔액": st.column_config.NumberColumn(format="%d"),
                "⬇️ 당월 매출": st.column_config.NumberColumn(format="%d"),
                "⬇️ 당월 수금": st.column_config.NumberColumn(format="%d"),
                "⬇️ 당월 잔액": st.column_config.NumberColumn(format="%d"),
            },
            disabled=[c for c in disp_cols.values() if "메모" not in c] # 메모 빼고 다 잠금
        )

        st.success(f"✅ {len(res)}개 거래처 분석 완료 (기준: {m0})")

    except Exception as e:
        st.error(f"데이터 처리 중 오류 발생: {e}")
