import streamlit as st
import pandas as pd
import gspread
import json
from oauth2client.service_account import ServiceAccountCredentials

def run(load_data_func):
    # 담당자 매핑 및 순서
    MANAGER_MAP = {
        "001": "001:이계성", "002": "002:이계흥", "004": "004:황일용",
        "00026": "00026:신의명", "007": "007:정상영", "009": "009:이경옥"
    }
    MANAGER_ORDER = ["001:이계성", "002:이계흥", "004:황일용", "00026:신의명", "007:정상영", "009:이경옥"]

    st.title("💳 채권(미수금) 현황 분석기")

    # 1. 구글 시트 메모 데이터 불러오기 🚀
    try:
        df_memo_gs = load_data_func("ar_memo")
        # 데이터가 비어있을 경우를 대비해 컬럼 강제 지정
        if df_memo_gs.empty:
            df_memo_gs = pd.DataFrame(columns=['거래처명', '메모'])
    except:
        st.error("구글 시트에서 'ar_memo' 탭을 찾을 수 없습니다. 시트 이름을 확인해주세요.")
        return

    uploaded_file = st.file_uploader("이카운트 [월별채권증감내역] 업로드", type=['csv', 'xlsx', 'xls'])

    if uploaded_file is None:
        st.info("💡 분석할 파일을 업로드하면 구글 시트 메모와 매칭하여 분석을 시작합니다.")
        return

    try:
        # 데이터 로드 및 정제 (생략된 로직은 이전과 동일)
        if uploaded_file.name.endswith('.csv'):
            try: df_raw = pd.read_csv(uploaded_file, encoding='utf-8')
            except: df_raw = pd.read_csv(uploaded_file, encoding='cp949')
        else:
            df_raw = pd.read_excel(uploaded_file)

        header_idx = df_raw[df_raw.apply(lambda r: r.astype(str).str.contains('거래처명').any(), axis=1)].index[0]
        df_raw.columns = df_raw.iloc[header_idx]
        df = df_raw.iloc[header_idx+1:].reset_index(drop=True)

        manager_col = next((c for c in df.columns if '담당자' in str(c)), None)
        df['거래처명'] = df['거래처명'].ffill()
        if manager_col:
            df[manager_col] = df[manager_col].ffill().astype(str).str.strip().apply(lambda x: MANAGER_MAP.get(x, f"{x}:미등록"))
        
        df = df.dropna(subset=['구분'])
        month_cols = [c for c in df.columns if '20' in str(c) and ('/' in str(c) or '-' in str(c))]

        id_vars = ['거래처명', '구분'] + ([manager_col] if manager_col else [])
        df_melt = df.melt(id_vars=id_vars, value_vars=month_cols, var_name='기준월', value_name='금액')
        df_melt['금액'] = pd.to_numeric(df_melt['금액'].astype(str).str.replace(',', ''), errors='coerce').fillna(0)
        
        pivot_idx = ['거래처명', '기준월'] + ([manager_col] if manager_col else [])
        df_pivot = df_melt.pivot_table(index=pivot_idx, columns='구분', values='금액', aggfunc='sum').reset_index()

        month_list = sorted(list(df_pivot['기준월'].unique()), reverse=True)
        m0, m1 = month_list[0], (month_list[1] if len(month_list) > 1 else None)
        
        # 스파크라인 데이터
        past_12 = sorted(month_list[:12])
        trend_series = df_pivot[df_pivot['기준월'].isin(past_12)].sort_values('기준월').groupby('거래처명')['잔액'].apply(list).reset_index(name='trend_data')

        # DSO 계산
        dso_results = []
        for trader, group in df_pivot.groupby('거래처명'):
            def get_dso(offset):
                target = month_list[offset : offset+12]
                sub = group[group['기준월'].isin(target)]
                s, b = sub['매출'].sum(), sub['잔액'].sum()
                return 9999 if s < 1 else int(round((b/s)*30))
            dso_results.append({'거래처명': trader, 'd0': get_dso(0), 'd1': get_dso(1), 'd2': get_dso(2)})
        
        final_df = df_pivot[df_pivot['기준월'] == m0].rename(columns={'매출':'당월 매출','수금':'당월 수금','잔액':'당월 잔액'})
        if m1:
            df_m1 = df_pivot[df_pivot['기준월'] == m1][['거래처명','매출','수금','잔액']].rename(columns={'매출':'전월 매출','수금':'전월 수금','잔액':'전월 잔액'})
            final_df = pd.merge(final_df, df_m1, on='거래처명', how='left')
        
        final_df = pd.merge(final_df, pd.DataFrame(dso_results), on='거래처명')
        final_df = pd.merge(final_df, trend_series, on='거래처명')

        # 🚀 구글 시트 메모 결합!
        final_df = pd.merge(final_df, df_memo_gs[['거래처명', '메모']], on='거래처명', how='left').fillna({'메모': ""})

        # 필터링 및 정렬 (이전과 동일)
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

        # 표 표시 데이터 가공
        def get_status(v):
            if v == 9999: return "🔴 F(장기)"
            if v > 365: return "🔴 ▲"
            if v > 90: return f"🔴 {v}일"
            if v > 45: return f"🟡 {v}일"
            return f"🟢 {v}일"

        res = final_df.copy()
        res['🚨 전전월'] = res['d2'].apply(get_status)
        res['🚨 전월'] = res['d1'].apply(get_status)
        res['🚨 당월'] = res['d0'].apply(get_status)
        
        # 에디터용 컬럼명 세팅
        disp_cols = {
            '거래처명': '거래처명',
            'trend_data': '📈 1년 잔액 추이',
            '전월 매출': '⏮️ 전월 매출', '전월 수금': '⏮️ 전월 수금', '전월 잔액': '⏮️ 전월 잔액',
            '당월 매출': '⬇️ 당월 매출', '당월 수금': '⬇️ 당월 수금', '당월 잔액': '⬇️ 당월 잔액',
            '🚨 전전월': '🚨 전전월', '🚨 전월': '🚨 전월', '🚨 당월': '🚨 당월',
            '메모': '📝 영업 의견/메모'
        }
        res_display = res[list(disp_cols.keys())].rename(columns=disp_cols)

        # 🚀 메모 수정 감지 및 구글 시트 저장 버튼
        edited_df = st.data_editor(
            res_display,
            use_container_width=True,
            hide_index=True,
            height=(len(res_display) + 1) * 38 + 100,
            column_config={
                "📈 1년 잔액 추이": st.column_config.LineChartColumn(width="medium"),
                "📝 영업 의견/메모": st.column_config.TextColumn(width="large", disabled=False),
                "⏮️ 전월 매출": st.column_config.NumberColumn(format="%d"), "⏮️ 전월 수금": st.column_config.NumberColumn(format="%d"), "⏮️ 전월 잔액": st.column_config.NumberColumn(format="%d"),
                "⬇️ 당월 매출": st.column_config.NumberColumn(format="%d"), "⬇️ 당월 수금": st.column_config.NumberColumn(format="%d"), "⬇️ 당월 잔액": st.column_config.NumberColumn(format="%d"),
            },
            disabled=[c for c in disp_cols.values() if "메모" not in c],
            key="ar_editor"
        )

        # 🚀 [핵심] 변경사항 저장 로직
        if st.button("💾 메모 저장하기"):
            # 수정한 내용만 추출
            new_memos = edited_df[['거래처명', '📝 영업 의견/메모']].copy()
            new_memos.columns = ['거래처명', '메모']
            
            # 구글 시트 직접 연결 (업데이트용)
            scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
            creds_dict = json.loads(st.secrets["gcp_service_account"])
            creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
            client = gspread.authorize(creds)
            doc = client.open("통합재고관리")
            sheet = doc.worksheet("ar_memo")
            
            # 시트 싹 비우고 새로 쓰기 (가장 확실한 방법)
            sheet.clear()
            sheet.update([new_memos.columns.values.tolist()] + new_memos.values.tolist())
            st.success("✅ 메모가 구글 시트에 안전하게 저장되었습니다!")
            st.cache_data.clear() # 캐시 비워서 다음 로드 시 반영되게 함

    except Exception as e:
        st.error(f"데이터 처리 중 오류 발생: {e}")
