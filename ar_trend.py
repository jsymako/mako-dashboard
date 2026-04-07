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

    # 🚀 [디자인] 헤더 고정 및 표 스타일 개선을 위한 CSS
    st.markdown("""
        <style>
        .stDataFrame [data-testid="stTable"] { font-size: 15px; }
        /* 헤더 고정 스타일 */
        thead tr th { position: sticky; top: 0; background-color: #f0f2f6; z-index: 1; }
        </style>
    """, unsafe_allow_html=True)

    st.title("💳 채권(미수금) 분석 관제탑")

    # 메모 데이터 로드
    try:
        df_memo_gs = load_data_func("ar_memo")
        if df_memo_gs.empty: df_memo_gs = pd.DataFrame(columns=['거래처명', '메모'])
    except:
        st.error("'ar_memo' 시트를 로드할 수 없습니다.")
        return

    uploaded_file = st.file_uploader("이카운트 엑셀 파일 업로드", type=['csv', 'xlsx', 'xls'])
    if not uploaded_file: return

    try:
        # 데이터 로드 로직 (이전과 동일)
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
        
        # 12개월 추이 (스파크라인)
        past_12 = sorted(month_list[:12])
        trend_series = df_pivot[df_pivot['기준월'].isin(past_12)].sort_values('기준월').groupby('거래처명')['잔액'].apply(list).reset_index(name='trend_data')

        # DSO 및 증감 분석 데이터 생성
        final_list = []
        for trader, group in df_pivot.groupby('거래처명'):
            # DSO (12개월 누적)
            def get_dso(m_list):
                sub = group[group['기준월'].isin(m_list)]
                s, b = sub['매출'].sum(), sub['잔액'].sum()
                return 9999 if s < 1 else int(round((b/s)*30))
            
            d0 = get_dso(month_list[0:12])
            d1 = get_dso(month_list[1:13]) if len(month_list) > 1 else 0
            
            # 전월/당월 데이터
            curr = group[group['기준월'] == m0].iloc[0]
            prev = group[group['기준월'] == m1].iloc[0] if m1 in group['기준월'].values else None
            
            def fmt_diff(c, p):
                diff = c - (p if p else 0)
                mark = "🔺" if diff > 0 else ("🔻" if diff < 0 else "-")
                return f"{int(c):,} ({mark} {abs(int(diff)):,})"

            final_list.append({
                '거래처명': trader,
                '담당자': curr[manager_col] if manager_col else "미지정",
                '📈 추이': trend_series[trend_series['거래처명']==trader]['trend_data'].iloc[0],
                '💰 매출 (전월대비)': fmt_diff(curr['매출'], prev['매출'] if prev is not None else 0),
                '📥 수금 (전월대비)': fmt_diff(curr['수금'], prev['수금'] if prev is not None else 0),
                '🚨 잔액 (현시점)': fmt_diff(curr['잔액'], prev['잔액'] if prev is not None else 0),
                'DSO_val': d0,
                'DSO_diff': d0 - d1 if d1 != 9999 and d0 != 9999 else 0
            })

        res_df = pd.DataFrame(final_list)

        # 사이드바 필터
        st.sidebar.markdown("### 🔍 필터 및 정렬")
        min_dso = st.sidebar.slider("DSO 필터", 0, 120, 45, step=15)
        sort_opt = st.sidebar.radio("정렬 기준", ["잔액 많은 순", "DSO 위험 순", "가나다 순"])
        
        # 필터 적용
        display_df = res_df[res_df['DSO_val'] >= min_dso].copy()
        
        # DSO 상태 텍스트화
        def get_dso_status(row):
            v, diff = row['DSO_val'], row['DSO_diff']
            base = "🔴 F(장기)" if v == 9999 else (f"🔴 {v}일" if v > 90 else (f"🟡 {v}일" if v > 45 else f"🟢 {v}일"))
            d_mark = f" (+{diff})" if diff > 0 else (f" ({diff})" if diff < 0 else "")
            return base + d_mark

        display_df['매출채권 회수현황 (DSO)'] = display_df.apply(get_dso_status, axis=1)
        
        # 메모 매칭
        display_df = pd.merge(display_df, df_memo_gs[['거래처명', '메모']], on='거래처명', how='left').fillna({'메모': ""})
        
        # 정렬
        if sort_opt == "잔액 많은 순":
            display_df['sort_val'] = display_df['🚨 잔액 (현시점)'].str.extract(r'(\d+)').astype(float)
            display_df = display_df.sort_values('sort_val', ascending=False)
        elif sort_opt == "DSO 위험 순":
            display_df = display_df.sort_values('DSO_val', ascending=False)
        else:
            display_df = display_df.sort_values('거래처명')

        # 🚀 [UI] 최종 표 출력
        st.subheader(f"📋 채권 상세 리포트 ({m0} 기준)")
        st.caption("💡 수치 옆 (🔺/🔻)는 전월 대비 증감액입니다. 메모를 수정한 후 하단 저장 버튼을 눌러주세요.")

        edited_df = st.data_editor(
            display_df[['거래처명', '담당자', '📈 추이', '💰 매출 (전월대비)', '📥 수금 (전월대비)', '🚨 잔액 (현시점)', '매출채권 회수현황 (DSO)', '메모']],
            use_container_width=True,
            hide_index=True,
            height=600, # 헤더 고정 효과를 위해 적절한 높이 설정
            column_config={
                "📈 추이": st.column_config.LineChartColumn(width="small"),
                "메모": st.column_config.TextColumn("📝 영업 의견/메모", width="large", disabled=False),
                "거래처명": st.column_config.Column(width="medium"),
                "매출채권 회수현황 (DSO)": st.column_config.Column(width="medium")
            },
            disabled=['거래처명', '담당자', '📈 추이', '💰 매출 (전월대비)', '📥 수금 (전월대비)', '🚨 잔액 (현시점)', '매출채권 회수현황 (DSO)']
        )

        # 저장 로직
        if st.button("💾 메모 내용 구글 시트에 저장하기"):
            scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
            creds_dict = json.loads(st.secrets["gcp_service_account"])
            creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
            client = gspread.authorize(creds)
            doc = client.open("통합재고관리")
            sheet = doc.worksheet("ar_memo")
            
            save_data = edited_df[['거래처명', '메모']].values.tolist()
            sheet.clear()
            sheet.update([['거래처명', '메모']] + save_data)
            st.success("✅ 메모가 성공적으로 저장되었습니다!")
            st.cache_data.clear()

    except Exception as e:
        st.error(f"오류 발생: {e}")
