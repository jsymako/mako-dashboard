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
    st.markdown("이카운트에서 다운로드한 **[월별채권증감내역]** 파일을 올려주세요.")

    uploaded_file = st.file_uploader("엑셀/CSV 파일 업로드", type=['csv', 'xlsx', 'xls'])

    if uploaded_file is None:
        return

    try:
        # 1. 데이터 로딩
        if uploaded_file.name.endswith('.csv'):
            try:
                df_raw = pd.read_csv(uploaded_file, encoding='utf-8')
            except UnicodeDecodeError:
                uploaded_file.seek(0)
                df_raw = pd.read_csv(uploaded_file, encoding='cp949') 
        else:
            df_raw = pd.read_excel(uploaded_file)

        # 2. 양식 정제
        header_idx = df_raw[df_raw.apply(lambda r: r.astype(str).str.contains('거래처명').any(), axis=1)].index
        if len(header_idx) > 0:
            df_raw.columns = df_raw.iloc[header_idx[0]]
            df = df_raw.iloc[header_idx[0]+1:].reset_index(drop=True)
        else:
            st.error("올바른 이카운트 양식이 아닙니다.")
            return

        manager_col = next((c for c in df.columns if '담당자' in str(c)), None)
        df['거래처명'] = df['거래처명'].ffill()
        
        if manager_col:
            df[manager_col] = df[manager_col].ffill().astype(str).str.strip()
            df[manager_col] = df[manager_col].apply(lambda x: MANAGER_MAP.get(x, f"{x}:미등록"))
            
        df = df.dropna(subset=['구분']) 
        month_cols = [c for c in df.columns if '20' in str(c) and ('/' in str(c) or '-' in str(c))]

        id_vars_list = ['거래처명', '구분']
        if manager_col: id_vars_list.insert(1, manager_col)

        df_melt = df.melt(id_vars=id_vars_list, value_vars=month_cols, var_name='기준월', value_name='금액')
        df_melt['금액'] = pd.to_numeric(df_melt['금액'].astype(str).str.replace(',', ''), errors='coerce').fillna(0)
        
        pivot_idx = ['거래처명', '기준월']
        if manager_col: pivot_idx.insert(1, manager_col)
        df_pivot = df_melt.pivot_table(index=pivot_idx, columns='구분', values='금액', aggfunc='sum').reset_index()
        
        for col in ['잔액', '매출', '수금']:
            if col not in df_pivot.columns: df_pivot[col] = 0

        # 3. DSO 및 스파크라인(1년 흐름) 데이터 생성
        month_list = sorted(list(df_pivot['기준월'].unique()), reverse=True)
        past_12_months = sorted(month_list[:12]) 
        
        traders = df_pivot['거래처명'].unique()
        grid = pd.MultiIndex.from_product([traders, past_12_months], names=['거래처명', '기준월']).to_frame(index=False)
        trend_full = pd.merge(grid, df_pivot[['거래처명', '기준월', '잔액']], on=['거래처명', '기준월'], how='left').fillna(0)
        trend_series = trend_full.groupby('거래처명')['잔액'].apply(list).reset_index(name='12개월 추이')

        dso_data = []
        for trader, group in df_pivot.groupby('거래처명'):
            def get_12m_dso(m_idx):
                target_m = month_list[m_idx : m_idx+12]
                sub = group[group['기준월'].isin(target_m)]
                s_sum = sub['매출'].sum()
                b_sum = sub['잔액'].sum()
                if s_sum < 1: return 9999 
                return int(round((b_sum / s_sum) * 30))
                
            d0 = get_12m_dso(0) if len(month_list) > 0 else 0
            d1 = get_12m_dso(1) if len(month_list) > 1 else 0
            d2 = get_12m_dso(2) if len(month_list) > 2 else 0
            dso_data.append({'거래처명': trader, '당월 DSO': d0, '전월 DSO': d1, '전전월 DSO': d2})
            
        df_dso = pd.DataFrame(dso_data)

        # 4. 전월/당월 데이터 분리 및 병합
        m0 = month_list[0] 
        m1 = month_list[1] if len(month_list) > 1 else None 

        df_m0 = df_pivot[df_pivot['기준월'] == m0].copy()
        df_m0 = df_m0.rename(columns={'매출': '당월 매출', '수금': '당월 수금', '잔액': '당월 잔액'})

        if m1:
            df_m1 = df_pivot[df_pivot['기준월'] == m1][['거래처명', '매출', '수금', '잔액']]
            df_m1 = df_m1.rename(columns={'매출': '전월 매출', '수금': '전월 수금', '잔액': '전월 잔액'})
            df_m0 = pd.merge(df_m0, df_m1, on='거래처명', how='left').fillna(0)
        else:
            df_m0['전월 매출'] = df_m0['전월 수금'] = df_m0['전월 잔액'] = 0

        df_m0 = pd.merge(df_m0, df_dso, on='거래처명', how='left')
        df_m0 = pd.merge(df_m0, trend_series, on='거래처명', how='left') 
        df_m0['메모 (더블클릭)'] = ""

        # 5. 사이드바 필터
        st.sidebar.markdown("### 🔍 분석 조건")
        st.sidebar.info(f"**기준월:** {m0}")
        
        selected_manager = "전체보기"
        if manager_col:
            available_managers = [m for m in MANAGER_ORDER if m in df_m0[manager_col].unique()]
            manager_options = ["전체보기"] + available_managers
            selected_manager = st.sidebar.selectbox("1. 담당자 선택", manager_options)
        
        st.sidebar.markdown("---")
        st.sidebar.markdown("### ⚠️ 위험 채권 필터")
        hide_zero = st.sidebar.checkbox("✅ 잔액 0원 거래처 숨기기", value=True)
        min_dso = st.sidebar.slider("최소 당월 회수일수(DSO) 기준", 0, 120, 45, step=15)

        st.sidebar.markdown("---")
        st.sidebar.markdown("### 📊 목록 정렬 기준")
        sort_option = st.sidebar.radio(
            "어떤 기준으로 줄을 세울까요?",
            ["당월 잔액순 (많은 순)", "당월 DSO순 (위험순)", "가나다순 (거래처명)"]
        )

        display_df = df_m0.copy()
        if manager_col and selected_manager != "전체보기":
            display_df = display_df[display_df[manager_col] == selected_manager]
        if hide_zero:
            display_df = display_df[display_df['당월 잔액'] > 0]
        if min_dso > 0:
            display_df = display_df[display_df['당월 DSO'] >= min_dso]

        # 6. 상단 KPI
        total_balance = display_df['당월 잔액'].sum()
        total_sales = display_df['당월 매출'].sum()
        c1, c2, c3 = st.columns(3)
        c1.metric("💰 당월 총 미수금", f"{int(total_balance / 10000):,}만 원")
        c2.metric("📈 당월 총 매출", f"{int(total_sales / 10000):,}만 원")
        c3.metric("🚨 대상 업체수", f"{len(display_df)} 곳")
        
        st.markdown("---")
        
        if display_df.empty:
            st.success("🎉 조건에 해당하는 내역이 없습니다!")
            return

        # 7. 상세 리포트
        st.subheader(f"📋 {sort_option.split(' ')[0]} 채권 상세 리포트")
        st.caption("💡 표 맨 우측의 **'📝 메모장'** 칸을 더블클릭하시면 자유롭게 내용을 입력하고 저장하실 수 있습니다.")
        
        if "당월 잔액순" in sort_option: sorted_df = display_df.sort_values(by='당월 잔액', ascending=False)
        elif "가나다순" in sort_option: sorted_df = display_df.sort_values(by='거래처명', ascending=True)
        elif "DSO순" in sort_option: sorted_df = display_df.sort_values(by='당월 DSO', ascending=False) 

        cols = ['거래처명']
        if manager_col: cols.append(manager_col)
        cols.append('12개월 추이')
        
        cols.extend([
            '전월 매출', '전월 수금', '전월 잔액', 
            '당월 매출', '당월 수금', '당월 잔액', 
            '전전월 DSO', '전월 DSO', '당월 DSO',
            '메모 (더블클릭)'
        ])
        
        show_df = sorted_df[cols].copy()
        
        # 신호등 이모지 적용
        def format_dso(val):
            if val == 9999: return "🔴 F(장기)"
            elif val > 365: return "🔴 ▲ (>365)"
            elif val > 90: return f"🔴 {int(val)}일"
            elif val > 45: return f"🟡 {int(val)}일"
            elif val == 0: return "-"
            else: return f"🟢 {int(val)}일"

        dso_cols = ['전전월 DSO', '전월 DSO', '당월 DSO']
        krw_cols = ['전월 매출', '전월 수금', '전월 잔액', '당월 매출', '당월 수금', '당월 잔액']

        for c in dso_cols: show_df[c] = show_df[c].apply(format_dso)
        for c in krw_cols: show_df[c] = show_df[c].apply(lambda x: f"{int(x):,}")

        # 🚀 [핵심] 제목 병합 기능을 포기하는 대신, 직관적인 이름표(Prefix)로 대체!
        rename_dict = {
            '12개월 추이': '📈 1년 흐름',
            '전월 매출': '⏮️ [전월] 매출',
            '전월 수금': '⏮️ [전월] 수금',
            '전월 잔액': '⏮️ [전월] 잔액',
            '당월 매출': '⬇️ [당월] 매출',
            '당월 수금': '⬇️ [당월] 수금',
            '당월 잔액': '⬇️ [당월] 잔액',
            '전전월 DSO': '🚨 회수(전전월)',
            '전월 DSO': '🚨 회수(전월)',
            '당월 DSO': '🚨 회수(당월)',
            '메모 (더블클릭)': '📝 메모장'
        }
        show_df.rename(columns=rename_dict, inplace=True)

        # 🚀 색상 칠하기 로직 (이모지 기반)
        def style_dso(val):
            val_str = str(val)
            if "🔴" in val_str: return 'background-color: #FFCCCC; color: #000; font-weight: bold;'
            if "🟡" in val_str: return 'background-color: #FFFFCC; color: #000; font-weight: bold;'
            return ''

        styled_df = show_df.style.set_properties(**{'font-size': '15px', 'text-align': 'right'})\
                           .set_properties(subset=['거래처명'], **{'text-align': 'left'})
        
        # 신호등 칸에만 색상 적용
        dso_renamed = ['🚨 회수(전전월)', '🚨 회수(전월)', '🚨 회수(당월)']
        for dso_c in dso_renamed:
            styled_df = styled_df.map(style_dso, subset=[dso_c])

        # 🚀 스트림릿의 컬럼 세부 설정 (스파크라인 & 메모장 활성화)
        config_dict = {}
        for c in show_df.columns:
            if c == '📈 1년 흐름':
                config_dict[c] = st.column_config.LineChartColumn("📈 1년 잔액 흐름", width="medium")
            elif c == '📝 메모장':
                config_dict[c] = st.column_config.TextColumn("📝 메모장", disabled=False) # 👈 이것만 수정 가능!
            else:
                config_dict[c] = st.column_config.Column(disabled=True) # 나머지는 잠금

        dynamic_height = max(400, len(show_df) * 35 + 150)

        # 🚀 st.data_editor로 출력!
        st.data_editor(
            styled_df, 
            use_container_width=True, 
            hide_index=True, 
            height=dynamic_height,
            column_config=config_dict
        )

    except Exception as e:
        st.error(f"오류: {e}")
