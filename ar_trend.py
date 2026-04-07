import streamlit as st
import pandas as pd
import pandas.io.formats.style

def run(load_data_func):
    # 담당자 매핑
    MANAGER_MAP = {
        "001": "001:이계성", "002": "002:이계흥", "004": "004:황일용",
        "00026": "00026:신의명", "007": "007:정상영", "009": "009:이경옥"
    }
    MANAGER_ORDER = ["001:이계성", "002:이계흥", "004:황일용", "00026:신의명", "007:정상영", "009:이경옥"]

    st.title("💳 채권(미수금) 현황 분석기")

    # 메모 데이터 로드 (구글 시트)
    try:
        df_memo_gs = load_data_func("ar_memo")
    except:
        df_memo_gs = pd.DataFrame(columns=['거래처명', '메모'])

    uploaded_file = st.file_uploader("이카운트 [월별채권증감내역] 업로드", type=['csv', 'xlsx', 'xls'])
    if not uploaded_file: return

    try:
        # 데이터 로드 로직
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
            df[manager_col] = df[manager_col].ffill().astype(str).str.strip().apply(lambda x: MANAGER_MAP.get(x, f"{x}:미등록"))

        month_cols = [c for c in df.columns if '20' in str(c) and ('/' in str(c) or '-' in str(c))]
        df_melt = df.melt(id_vars=['거래처명', '구분'] + ([manager_col] if manager_col else []), value_vars=month_cols, var_name='기준월', value_name='금액')
        df_melt['금액'] = pd.to_numeric(df_melt['금액'].astype(str).str.replace(',', ''), errors='coerce').fillna(0)
        df_pivot = df_melt.pivot_table(index=['거래처명', '기준월'] + ([manager_col] if manager_col else []), columns='구분', values='금액', aggfunc='sum').reset_index()

        month_list = sorted(list(df_pivot['기준월'].unique()), reverse=True)
        m0, m1 = month_list[0], (month_list[1] if len(month_list) > 1 else None)
        
        # 12개월 추이 스파크라인 데이터
        past_12 = sorted(month_list[:12])
        trend_series = df_pivot[df_pivot['기준월'].isin(past_12)].sort_values('기준월').groupby('거래처명')['잔액'].apply(list).reset_index(name='trend')

        # 분석 데이터 생성
        final_list = []
        for trader, group in df_pivot.groupby('거래처명'):
            def get_dso(offset):
                target = month_list[offset : offset+12]
                sub = group[group['기준월'].isin(target)]
                s, b = sub['매출'].sum(), sub['잔액'].sum()
                return 9999 if s < 1 else int(round((b/s)*30))
            
            d0, d1, d2 = get_dso(0), get_dso(1), get_dso(2)
            curr = group[group['기준월'] == m0].iloc[0]
            prev = group[group['기준월'] == m1].iloc[0] if m1 in group['기준월'].values else None

            final_list.append({
                '거래처명': trader,
                '담당자': curr[manager_col] if manager_col else "미지정",
                '📈 추이': trend_series[trend_series['거래처명']==trader]['trend'].iloc[0],
                '전월_매출': int(prev['매출']) if prev is not None else 0,
                '전월_수금': int(prev['수금']) if prev is not None else 0,
                '전월_잔액': int(prev['잔액']) if prev is not None else 0,
                '당월_매출': int(curr['매출']),
                '당월_수금': int(curr['수금']),
                '당월_잔액': int(curr['잔액']),
                'DSO_당월': d0, 'DSO_전월': d1, 'DSO_전전월': d2
            })

        res_df = pd.DataFrame(final_list)

        # 🚀 [복구] 사이드바 담당자 선택
        st.sidebar.markdown("### 🔍 필터 설정")
        if manager_col:
            m_list = ["전체보기"] + [m for m in MANAGER_ORDER if m in res_df['담당자'].unique()]
            selected_manager = st.sidebar.selectbox("1. 담당자 선택", m_list)
            if selected_manager != "전체보기":
                res_df = res_df[res_df['담당자'] == selected_manager]
        
        min_dso = st.sidebar.slider("2. DSO 필터 (45일 이상)", 0, 120, 45, step=15)
        res_df = res_df[(res_df['당월_잔액'] > 0) & (res_df['DSO_당월'] >= min_dso)]

        # 🚀 [UI] 다중 헤더(병합) 구조 만들기
        display_df = res_df.copy()
        
        # 신호등 및 기호 로직
        def fmt_dso(v):
            if v == 9999: return "🔴 F"
            if v > 365: return "🔴 ▲"
            return f"🔴 {v}일" if v > 90 else (f"🟡 {v}일" if v > 45 else f"🟢 {v}일")

        display_df['🚨 당월'] = display_df['DSO_당월'].apply(fmt_dso)
        display_df['🚨 전월'] = display_df['DSO_전월'].apply(fmt_dso)
        display_df['🚨 전전월'] = display_df['DSO_전전월'].apply(fmt_dso)
        
        # 메모 매칭
        display_df = pd.merge(display_df, df_memo_gs[['거래처명', '메모']], on='거래처명', how='left').fillna({'메모': ""})

        # 컬럼 구조 재편 (병합용 튜플 생성)
        columns = [
            ("기본 정보", "거래처명"), ("기본 정보", "담당자"), ("기본 정보", "📈 추이"),
            ("전월 (원)", "매출"), ("전월 (원)", "수금"), ("전월 (원)", "잔액"),
            ("당월 (원)", "매출"), ("당월 (원)", "수금"), ("당월 (원)", "잔액"),
            ("DSO 회수일수", "전전월"), ("DSO 회수일수", "전월"), ("DSO 회수일수", "당월"),
            ("비고", "영업 메모")
        ]
        
        final_table = display_df[[
            '거래처명', '담당자', '📈 추이', 
            '전월_매출', '전월_수금', '전월_잔액', 
            '당월_매출', '당월_수금', '당월_잔액',
            '🚨 전전월', '🚨 전월', '🚨 당월', '메모'
        ]]
        final_table.columns = pd.MultiIndex.from_tuples(columns)

        # 🚀 [UI 핵심] 조회 전용으로 설정하여 병합 헤더와 그래프 동시 구현
        st.subheader(f"📋 채권 상세 리포트 ({m0} 기준)")
        st.dataframe(
            final_table,
            use_container_width=True,
            hide_index=True,
            height=600,
            column_config={
                ("기본 정보", "📈 추이"): st.column_config.LineChartColumn(width="medium"),
                ("전월 (원)", "매출"): st.column_config.NumberColumn(format="%d"),
                ("전월 (원)", "수금"): st.column_config.NumberColumn(format="%d"),
                ("전월 (원)", "잔액"): st.column_config.NumberColumn(format="%d"),
                ("당월 (원)", "매출"): st.column_config.NumberColumn(format="%d"),
                ("당월 (원)", "수금"): st.column_config.NumberColumn(format="%d"),
                ("당월 (원)", "잔액"): st.column_config.NumberColumn(format="%d"),
            }
        )

        # 메모 수정은 하단에서 따로 하거나 팝업으로 처리하는 방식 제안
        st.info("💡 메모 수정 기능은 병합 헤더와 기술적 충돌로 인해 별도의 입력창을 준비 중입니다.")

    except Exception as e:
        st.error(f"오류 발생: {e}")
