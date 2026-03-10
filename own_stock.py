import streamlit as st
import pandas as pd
import numpy as np
import datetime
from dateutil.relativedelta import relativedelta
import os

def run(load_data_func): # 🚀 load_data_func라는 이름으로 함수를 넘겨받음
    st.title("📦 자사 재고 현황 및 소진 예측 (주 단위)")
    
    # CSS 적용
    if os.path.exists("style.css"):
        with open("style.css", "r", encoding="utf-8") as f:
            st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)

    try:
        # 🚀 넘겨받은 함수를 사용하여 데이터 로드
        df_own = load_data_func("ecount_stock")
        df_sales = load_data_func("sales_record")
        df_item = load_data_func("ecount_item_data")
        
        # --- [데이터 전처리 및 계산 로직] ---
        update_time = df_own['업데이트 시간'].iloc[0] if '업데이트 시간' in df_own.columns and not df_own.empty else '정보 없음'
        df_own['현재재고'] = pd.to_numeric(df_own['현재재고'], errors='coerce').fillna(0)
        df_sales['수량'] = df_sales['수량'].astype(str).str.replace(',', '')
        df_sales['수량'] = pd.to_numeric(df_sales['수량'], errors='coerce').fillna(0)
        df_sales['일자'] = pd.to_datetime(df_sales['일자'], errors='coerce', yearfirst=True)

        box_col_name = df_item.columns[3] 
        df_item_box = df_item[['품목코드', box_col_name]].copy()
        df_item_box.rename(columns={box_col_name: '박스입수'}, inplace=True)
        df_item_box['박스입수'] = pd.to_numeric(df_item_box['박스입수'], errors='coerce').fillna(1)

        excess_col_name = df_item.columns[4]
        df_item_limit = df_item[['품목코드', excess_col_name]].copy()
        df_item_limit.rename(columns={excess_col_name: '과다기준주'}, inplace=True)
        df_item_limit['과다기준주'] = pd.to_numeric(df_item_limit['과다기준주'], errors='coerce')

        # 사이드바 필터
        brand_list = ["전체보기"] + sorted(list(df_own['브랜드'].unique()))
        selected_brand = st.sidebar.selectbox("🔍 브랜드 필터", brand_list)
        status_list = ["전체보기", "품절", "재고 부족", "과다 재고", "적정"]
        selected_status = st.sidebar.selectbox("⚠️ 상태 필터", status_list)
        months_to_look_back = st.sidebar.slider("📅 판매 평균 산출 기준 (개월)", 1, 12, 1)

        # 날짜 계산 및 판매량 합산
        today = datetime.datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        end_date = today.replace(day=1) - datetime.timedelta(days=1)
        start_date = (end_date - relativedelta(months=months_to_look_back - 1)).replace(day=1)
        recent_sales = df_sales[(df_sales['일자'] >= pd.Timestamp(start_date)) & (df_sales['일자'] <= pd.Timestamp(end_date))]
        total_sales_by_item = recent_sales.groupby('품목코드')['수량'].sum().reset_index()
        total_sales_by_item.rename(columns={'수량': '기간내_총판매량'}, inplace=True)
        total_sales_by_item['주평균판매량'] = ((total_sales_by_item['기간내_총판매량'] / months_to_look_back) / 4).round(1)
        
        # 데이터 병합 및 최종 환산
        df_merged = pd.merge(df_own, total_sales_by_item[['품목코드', '주평균판매량']], on='품목코드', how='left').fillna(0)
        df_merged = pd.merge(df_merged, df_item_limit, on='품목코드', how='left')
        df_merged = pd.merge(df_merged, df_item_box, on='품목코드', how='left')
        df_merged['예상소진주'] = np.where(df_merged['주평균판매량'] > 0, (df_merged['현재재고'] / df_merged['주평균판매량']).round(1), 999.0)

        def check_status(row):
            if row['현재재고'] <= 0: return "🔴 품절"
            if row['예상소진주'] < 2.0: return "🟠 재고 부족 (2주 미만)"
            limit = row['과다기준주'] if pd.notna(row['과다기준주']) and row['과다기준주'] > 0 else 24.0
            return f"🔵 과다 재고 ({int(limit)}주 초과)" if row['예상소진주'] > limit else "🟢 적정"
        df_merged['재고상태'] = df_merged.apply(check_status, axis=1)

        def format_stock_display(qty, box_unit):
            if box_unit <= 1: return f"{int(qty):,} 개" if qty == int(qty) else f"{qty:.1f} 개"
            boxes = qty / box_unit
            return f"{boxes:.1f} 박스" if boxes < 10 else f"{int(boxes):,} 박스"

        df_merged['환산재고'] = df_merged.apply(lambda r: format_stock_display(r['현재재고'], r['박스입수']), axis=1)
        df_merged['환산주평균'] = df_merged.apply(lambda r: format_stock_display(r['주평균판매량'], r['박스입수']), axis=1)

        if selected_brand != "전체보기": df_merged = df_merged[df_merged['브랜드'] == selected_brand]
        if selected_status != "전체보기": df_merged = df_merged[df_merged['재고상태'].str.contains(selected_status, na=False)]

        # 정보 박스 출력
        date_range_str = f"{start_date.year}년 {start_date.month}월 ~ {end_date.year}년 {end_date.month}월"
        st.info(f"**🕒 데이터 업데이트 :** {update_time}  \n**💡 산출 기준 :** {date_range_str} ({months_to_look_back}개월 판매량을 4주 단위로 환산)")
        
        # --- [카드 렌더링 루프] ---
        for br in sorted(df_merged['브랜드'].unique()):
            br_df = df_merged[df_merged['브랜드'] == br]
            html_content = f'<div class="brand-section"><div class="brand-title">🏢 {br} ({len(br_df)}개 품목)</div><div class="grid-container">'
            for _, row in br_df.iterrows():
                s_class = "badge-good"
                if "품절" in row['재고상태']: s_class = "badge-out"
                elif "부족" in row['재고상태']: s_class = "badge-short"
                elif "과다" in row['재고상태']: s_class = "badge-over"
                
                # 🚀 주(Week)와 월(Month) 동시 표시 로직
                if row['예상소진주'] >= 999:
                    combined_val = "자료 없음"
                else:
                    weeks = row['예상소진주']
                    months = round(weeks / 4, 1) # 4주 기준 개월수 환산
                    combined_val = f"{weeks}주 · {months}개월"
                
                html_content += f'''
                <div class="item-card">
                    <div class="item-title">{row['품목명']}</div>
                    <div class="info-row"><span class="info-label">현재 재고</span><span class="info-val">{row['환산재고']}</span></div>
                    <div class="info-row"><span class="info-label">주평균 판매</span><span class="info-val">{row['환산주평균']}</span></div>
                    <div class="info-row"><span class="info-label">예상 소진</span><span class="info-val">{combined_val}</span></div>
                    <div class="badge {s_class}">{row['재고상태']}</div>
                </div>
                '''
                
            html_content += '</div></div>'
            st.markdown(html_content, unsafe_allow_html=True)

    except Exception as e:
        st.error(f"데이터 분석 중 오류가 발생했습니다: {e}")
