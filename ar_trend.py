import streamlit as st
import pandas as pd
import gspread
import json
from oauth2client.service_account import ServiceAccountCredentials

def run(load_data_func):
    MANAGER_MAP = {
        "001": "001:이계성", "002": "002:이계흥", "004": "004:황일용",
        "00026": "00026:신의명", "007": "007:정상영", "009": "009:이경옥"
    }
    MANAGER_ORDER = ["001:이계성", "002:이계흥", "004:황일용", "00026:신의명", "007:정상영", "009:이경옥"]

    st.title("💳 채권(미수금) 현황 분석기")

    # 1. 메모 로드
    try:
        df_memo_gs = load_data_func("ar_memo")
        if df_memo_gs.empty: df_memo_gs = pd.DataFrame(columns=['거래처명', '메모'])
    except:
        df_memo_gs = pd.DataFrame(columns=['거래처명', '메모'])

    uploaded_file = st.file_uploader("이카운트 [월별채권증감내역] 업로드", type=['csv', 'xlsx', 'xls'])
    if not uploaded_file:
        return

    try:
        # 데이터 로드
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
        
        df = df.dropna(subset=['구분'])
        month_cols = [c for c in df.columns if '20' in str(c) and ('/' in str(c) or '-' in str(c))]

        # 데이터 피벗
        id_vars = ['거래처명', '구분'] + ([manager_col] if manager_col else [])
        df_melt = df.melt(id_vars=id_vars, value_vars=month_cols, var_name='기준월', value_name='금액')
        df_melt['금액'] = pd.to_numeric(df_melt['금액'].astype(str).str.replace(',', ''), errors='coerce').fillna(0)
        pivot_idx = ['거래처명', '기준월'] + ([manager_col] if manager_col else [])
        df_pivot = df_melt.pivot_table(index=pivot_idx, columns='구분', values='금액', aggfunc='sum').reset_index()

        # 🚀 12개월 추이 데이터 (그래프용)
        month_list = sorted(list(df_pivot['기준월'].unique()), reverse=True)
        past_12 = sorted(month_list[:12])
        trend_series = df_pivot[df_pivot['기준월'].isin(past_12)].sort_values('기준월').groupby('거래처명')['잔액'].apply(list).reset_index(name='trend')

        # 분석 리스트 생성
        m0, m1 = month_list[0], (month_list[1] if len(month_list) > 1 else None)
        final_list = []
        for trader, group in df_pivot.groupby('거래처명'):
            def get_dso(offset):
                target = month_list[offset : offset+12]
                sub = group[group['기준월'].isin(target)]
                s, b = sub['매출'].sum(), sub['잔액'].sum()
                return 9999 if s < 1 else int(round((b/s)*30))
            
            curr = group[group['기준월'] == m0].iloc[0]
            prev = group[group['기준월'] == m1].iloc[0] if m1 in group['기준월'].values else None

            final_list.append({
                '거래처명': trader,
                '담당자': curr[manager_col] if manager_col else "미지정",
                '전월_매출': int(prev['매출']) if prev is not None else 0,
                '전월_수금': int(prev['수금']) if prev is not None else 0,
                '전월_잔액': int(prev['잔액']) if prev is not None else 0,
                '당월_매출': int(curr['매출']),
                '당월_수금': int(curr['수금']),
                '당월_잔액': int(curr['잔액']),
                'd0': get_dso(0), 'd1': get_dso(1), 'd2': get_dso(2)
            })

        res_df = pd.DataFrame(final_list)

        # ---------------------------------------------------------
        # 🚀 [복구 완료] 사이드바 필터 및 정렬
        # ---------------------------------------------------------
        st.sidebar.markdown("### 🔍 필터 설정")
        if manager_col:
            m_list = ["전체보기"] + [m for m in MANAGER_ORDER if m in res_df['담당자'].unique()]
            sel_m = st.sidebar.selectbox("1. 담당자 선택", m_list)
            if sel_m != "전체보기": res_df = res_df[res_df['담당자'] == sel_m]
        
        min_dso = st.sidebar.slider("2. DSO 필터 (45일 이상)", 0, 120, 45, step=15)
        
        st.sidebar.markdown("---")
        sort_option = st.sidebar.radio("3. 목록 정렬 기준", ["당월 잔액순", "DSO 위험순", "가나다순"])

        # 필터 적용
        res_df = res_df[(res_df['당월_잔액'] > 0) & (res_df['d0'] >= min_dso)]
        
        # 정렬 적용
        if sort_option == "당월 잔액순": res_df = res_df.sort_values("당월_잔액", ascending=False)
        elif sort_option == "DSO 위험순": res_df = res_df.sort_values("d0", ascending=False)
        else: res_df = res_df.sort_values("거래처명", ascending=True)

        # 데이터 가공 및 메모 결합
        def fmt_dso(v):
            if v == 9999: return "🔴 F"
            if v > 365: return "🔴 ▲"
            return f"🔴 {v}일" if v > 90 else (f"🟡 {v}일" if v > 45 else f"🟢 {v}일")

        res_df['🚨당월'] = res_df['d0'].apply(fmt_dso)
        res_df['🚨전월'] = res_df['d1'].apply(fmt_dso)
        res_df['🚨전전월'] = res_df['d2'].apply(fmt_dso)
        res_df = pd.merge(res_df, df_memo_gs[['거래처명', '메모']], on='거래처명', how='left').fillna({'메모': ""})
        res_df = pd.merge(res_df, trend_series, on='거래처명', how='left')

        # ---------------------------------------------------------
        # 🚀 [UI] 단일 헤더 리포트 (그래프 + 메모 완벽 호환)
        # ---------------------------------------------------------
        view_df = res_df[[
            '거래처명', '담당자', 'trend', 
            '전월_매출', '전월_수금', '전월_잔액', 
            '당월_매출', '당월_수금', '당월_잔액',
            '🚨전전월', '🚨전월', '🚨당월', '메모'
        ]].copy()
        
        view_df.columns = [
            '거래처명', '담당자', '📈 1년 추이',
            '⏮️[전월] 매출', '⏮️[전월] 수금', '⏮️[전월] 잔액',
            '⬇️[당월] 매출', '⬇️[당월] 수금', '⬇️[당월] 잔액',
            'DSO(전전)', 'DSO(전월)', 'DSO(당월)', '📝 메모'
        ]

        st.subheader(f"📋 채권 상세 리포트 ({m0} 기준)")
        st.dataframe(
            view_df,
            use_container_width=True,
            hide_index=True,
            height=600,
            column_config={
                "📈 1년 추이": st.column_config.LineChartColumn(width="medium"),
                "⏮️[전월] 매출": st.column_config.NumberColumn(format="%d"),
                "⏮️[전월] 수금": st.column_config.NumberColumn(format="%d"),
                "⏮️[전월] 잔액": st.column_config.NumberColumn(format="%d"),
                "⬇️[당월] 매출": st.column_config.NumberColumn(format="%d"),
                "⬇️[당월] 수금": st.column_config.NumberColumn(format="%d"),
                "⬇️[당월] 잔액": st.column_config.NumberColumn(format="%d"),
                "📝 메모": st.column_config.Column(width="large")
            }
        )

        # 메모 수정 및 저장 섹션
        st.markdown("---")
        with st.expander("📝 메모 수정 및 구글 시트 저장"):
            final_edit = st.data_editor(
                res_df[['거래처명', '담당자', '메모']],
                use_container_width=True,
                hide_index=True,
                column_config={"메모": st.column_config.TextColumn("📝 메모 수정", width="large", disabled=False)},
                disabled=['거래처명', '담당자']
            )

            if st.button("💾 메모 내용 저장하기"):
                scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
                creds_dict = json.loads(st.secrets["gcp_service_account"])
                creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
                client = gspread.authorize(creds)
                doc = client.open("통합재고관리")
                sheet = doc.worksheet("ar_memo")
                sheet.clear()
                sheet.update([['거래처명', '메모']] + final_edit[['거래처명', '메모']].values.tolist())
                st.success("✅ 메모가 저장되었습니다!")
                st.cache_data.clear()

    except Exception as e:
        st.error(f"오류 발생: {e}")
