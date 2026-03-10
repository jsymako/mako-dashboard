import streamlit as st
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import json
import os

# 1. 페이지 기본 설정
st.set_page_config(page_title="통합재고관리", page_icon="📊", layout="wide")

# 🚀 [해결 포인트 1] CSS 주입 함수를 최상단으로 올리고, 공백을 강제로 제거합니다.
def local_css(file_name):
    if os.path.exists(file_name):
        with open(file_name, "r", encoding="utf-8") as f:
            # strip()을 써서 앞뒤 불필요한 공백을 완전히 제거한 뒤 주입합니다.
            css_content = f.read().strip()
            st.markdown(f"<style>{css_content}</style>", unsafe_allow_html=True)
    else:
        st.sidebar.error(f"⚠️ {file_name} 파일을 찾을 수 없습니다.")

# 2. 구글 시트 데이터 불러오기 함수
@st.cache_data(ttl=600)
def load_sheet_data(worksheet_name):
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    creds_dict = json.loads(st.secrets["gcp_service_account"])
    creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
    client = gspread.authorize(creds)
    doc = client.open("통합재고관리")
    sheet = doc.worksheet(worksheet_name)
    data = sheet.get_all_values()
    df = pd.DataFrame(data[1:], columns=data[0])
    return df

# 사이드바 설정
st.sidebar.title("📊 통합재고관리")
main_menu = st.sidebar.radio("▶ 메뉴 이동", ["📦 자사 재고 현황", "🚀 쿠팡 재고 현황", "📈 판매 현황"])
st.sidebar.markdown("---")

# ------------------------------------------
# [메뉴 1] 자사 재고 현황
# ------------------------------------------
if main_menu == "📦 자사 재고 현황":
    st.title("📦 자사 재고 현황 및 소진 예측 (주 단위)")
    
    # 🚀 [해결 포인트 2] 데이터 로직 시작 전에 디자인을 먼저 입힙니다.
    local_css("style.css")

    try:
        df_own = load_sheet_data("ecount_stock")
        df_sales = load_sheet_data("sales_record")
        df_item = load_sheet_data("ecount_item_data")
        
        update_time = df_own['업데이트 시간'].iloc[0] if '업데이트 시간' in df_own.columns and not df_own.empty else '정보 없음'

        # 데이터 전처리
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

        # 필터 설정
        brand_list = ["전체보기"] + sorted(list(df_own['브랜드'].unique()))
        selected_brand = st.sidebar.selectbox("🔍 브랜드 필터", brand_list)
        status_list = ["전체보기", "품절", "재고 부족", "과다 재고", "적정"]
        selected_status = st.sidebar.selectbox("⚠️ 상태 필터", status_list)
        months_to_look_back = st.sidebar.slider("📅 판매 평균 산출 기준 (개월)", 1, 12, 1)

        # 판매량 계산 로직
        from dateutil.relativedelta import relativedelta
        import datetime
        today = datetime.datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        end_date = today.replace(day=1) - datetime.timedelta(days=1)
        start_date = (end_date - relativedelta(months=months_to_look_back - 1)).replace(day=1)
        recent_sales = df_sales[(df_sales['일자'] >= pd.Timestamp(start_date)) & (df_sales['일자'] <= pd.Timestamp(end_date))]
        total_sales_by_item = recent_sales.groupby('품목코드')['수량'].sum().reset_index()
        total_sales_by_item.rename(columns={'수량': '기간내_총판매량'}, inplace=True)
        total_sales_by_item['주평균판매량'] = ((total_sales_by_item['기간내_총판매량'] / months_to_look_back) / 4).round(1)

        # 데이터 병합 및 최종 계산
        df_merged = pd.merge(df_own, total_sales_by_item[['품목코드', '주평균판매량']], on='품목코드', how='left').fillna(0)
        df_merged = pd.merge(df_merged, df_item_limit, on='품목코드', how='left')
        df_merged = pd.merge(df_merged, df_item_box, on='품목코드', how='left')
        
        import numpy as np
        df_merged['예상소진주'] = np.where(df_merged['주평균판매량'] > 0, (df_merged['현재재고'] / df_merged['주평균판매량']).round(1), 999.0)

        def check_status(row):
            if row['현재재고'] <= 0: return "🔴 품절"
            if row['예상소진주'] < 4.0: return "🟠 재고 부족 (4주 미만)"
            limit = row['과다기준주'] if pd.notna(row['과다기준주']) and row['과다기준주'] > 0 else 24.0
            return f"🔵 과다 재고 ({int(limit)}주 초과)" if row['예상소진주'] > limit else "🟢 적정"
        
        df_merged['재고상태'] = df_merged.apply(check_status, axis=1)

        def format_stock_display(qty, box_unit):
            if box_unit <= 1: return f"{int(qty):,} 개" if qty == int(qty) else f"{qty:.1f} 개"
            boxes = qty / box_unit
            return f"{boxes:.1f} 박스" if boxes < 10 else f"{int(boxes):,} 박스"

        df_merged['환산재고'] = df_merged.apply(lambda r: format_stock_display(r['현재재고'], r['박스입수']), axis=1)
        df_merged['환산주평균'] = df_merged.apply(lambda r: format_stock_display(r['주평균판매량'], r['박스입수']), axis=1)

        # 필터 적용
        if selected_brand != "전체보기": df_merged = df_merged[df_merged['브랜드'] == selected_brand]
        if selected_status != "전체보기": df_merged = df_merged[df_merged['재고상태'].str.contains(selected_status, na=False)]

        # 정보 표시
        date_range_str = f"{start_date.year}년 {start_date.month}월 ~ {end_date.year}년 {end_date.month}월"
        st.info(f"**🕒 데이터 업데이트 :** {update_time}  \n**💡 산출 기준 :** {date_range_str} ({months_to_look_back}개월 판매량을 4주 단위로 환산)")
        
        # 카드 레이아웃 출력
        if df_merged.empty:
            st.warning("조건에 맞는 품목이 없습니다.")
        else:
            for br in sorted(df_merged['브랜드'].unique()):
                br_df = df_merged[df_merged['브랜드'] == br]
                html_content = f'<div class="brand-section"><div class="brand-title">🏢 {br} ({len(br_df)}개 품목)</div><div class="grid-container">'
                for _, row in br_df.iterrows():
                    s_class = "badge-good"
                    if "품절" in row['재고상태']: s_class = "badge-out"
                    elif "부족" in row['재고상태']: s_class = "badge-short"
                    elif "과다" in row['재고상태']: s_class = "badge-over"
                    w_val = "자료 없음" if row['예상소진주'] >= 999 else f"{row['예상소진주']} 주"
                    html_content += f'<div class="item-card"><div class="item-title">{row["품목명"]}</div><div class="info-row"><span class="info-label">현재 재고</span><span class="info-val">{row["환산재고"]}</span></div><div class="info-row"><span class="info-label">주평균 판매</span><span class="info-val">{row["환산주평균"]}</span></div><div class="info-row"><span class="info-label">예상 소진</span><span class="info-val">{w_val}</span></div><div class="badge {s_class}">{row["재고상태"]}</div></div>'
                html_content += '</div></div>'
                st.markdown(html_content, unsafe_allow_html=True)
                
    except Exception as e:
        st.error(f"데이터 분석 중 오류가 발생했습니다: {e}")

# 메뉴 2, 3은 기존과 동일하게 유지...
elif main_menu == "🚀 쿠팡 재고 현황":
    st.title("🚀 쿠팡 재고 현황")
    st.info("💡 준비 중입니다.")
elif main_menu == "📈 판매 현황":
    st.title("📈 판매 현황")
    st.info("💡 준비 중입니다.")
