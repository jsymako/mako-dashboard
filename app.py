import streamlit as st
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import json

# 1. 페이지 기본 설정 (가장 먼저 와야 함)
st.set_page_config(page_title="마코 통합 대시보드", page_icon="📊", layout="wide")

# 2. 구글 시트 데이터 불러오기 함수 (시트 이름만 넣으면 다 가져오도록 모듈화!)
@st.cache_data(ttl=600) # 10분마다 새로고침
def load_sheet_data(worksheet_name):
    scope = [
        "https://spreadsheets.google.com/feeds",
        "https://www.googleapis.com/auth/drive"
    ]
    # Secrets에서 인증 정보 가져오기
    creds_dict = json.loads(st.secrets["gcp_service_account"])
    creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
    client = gspread.authorize(creds)
    
    # 통합재고관리 문서에서 원하는 탭(worksheet_name) 열기
    doc = client.open("통합재고관리")
    sheet = doc.worksheet(worksheet_name)
    
    data = sheet.get_all_values()
    df = pd.DataFrame(data[1:], columns=data[0])
    return df

# ==========================================
# 3. 사이드바 (왼쪽 네비게이션 메뉴)
# ==========================================
st.sidebar.title("📊 통합 대시보드")
st.sidebar.caption("원하시는 메뉴를 선택하세요.")

# 라디오 버튼으로 큰 카테고리 3개 분리
main_menu = st.sidebar.radio(
    "▶ 메뉴 이동",
    ["📦 자사 재고 현황", "🚀 쿠팡 재고 현황", "📈 판매 현황"]
)

st.sidebar.markdown("---")

# ==========================================
# 4. 메뉴별 화면 구성
# ==========================================

# ------------------------------------------
# [메뉴 1] 자사 재고 현황 (이카운트)
# ------------------------------------------
if main_menu == "📦 자사 재고 현황":
    st.title("📦 자사 재고 현황 및 소진 예측 (주 단위)")
    
    try:
        # 1. 시트 데이터 모두 불러오기
        df_own = load_sheet_data("ecount_stock")
        df_sales = load_sheet_data("sales_record")
        df_item = load_sheet_data("ecount_item_data") # 💡 기준값 및 박스입수 시트
        
        # 숫자형/날짜형 데이터 전처리
        df_own['현재재고'] = pd.to_numeric(df_own['현재재고'], errors='coerce').fillna(0)
        df_sales['수량'] = df_sales['수량'].astype(str).str.replace(',', '')
        df_sales['수량'] = pd.to_numeric(df_sales['수량'], errors='coerce').fillna(0)
        df_sales['일자'] = pd.to_datetime(df_sales['일자'], errors='coerce', yearfirst=True)

        # 🚀 [추가됨] ecount_item_data의 D열(4번째 열, 인덱스 3)을 '박스입수'로 추출
        box_col_name = df_item.columns[3] 
        df_item_box = df_item[['품목코드', box_col_name]].copy()
        df_item_box.rename(columns={box_col_name: '박스입수'}, inplace=True)
        # 빈칸이거나 문자가 있으면 기본값 1(낱개)로 처리
        df_item_box['박스입수'] = pd.to_numeric(df_item_box['박스입수'], errors='coerce').fillna(1)

        # ecount_item_data의 E열(5번째 열, 인덱스 4)을 '과다기준주'로 추출
        excess_col_name = df_item.columns[4]
        df_item_limit = df_item[['품목코드', excess_col_name]].copy()
        df_item_limit.rename(columns={excess_col_name: '과다기준주'}, inplace=True)
        df_item_limit['과다기준주'] = pd.to_numeric(df_item_limit['과다기준주'], errors='coerce')

        # 2. 사이드바 필터: 브랜드 & 상태 & 분석 기간
        brand_list = ["전체보기"] + sorted(list(df_own['브랜드'].unique()))
        selected_brand = st.sidebar.selectbox("🔍 브랜드 필터", brand_list)
        
        status_list = ["전체보기", "품절", "재고 부족", "과다 재고", "적정"]
        selected_status = st.sidebar.selectbox("⚠️ 상태 필터", status_list)
        
        months_to_look_back = st.sidebar.slider("📅 판매 평균 산출 기준 (개월)", min_value=1, max_value=12, value=1)
        
        # 3. 판매량 기반 평균 계산 로직 (당월 제외, 전월 기준)
        from dateutil.relativedelta import relativedelta
        import datetime
        
        today = datetime.datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        end_date = today.replace(day=1) - datetime.timedelta(days=1)
        start_date = (end_date - relativedelta(months=months_to_look_back - 1)).replace(day=1)
        
        # 선택 기간 내 데이터 필터링
        recent_sales = df_sales[(df_sales['일자'] >= pd.Timestamp(start_date)) & (df_sales['일자'] <= pd.Timestamp(end_date))]
        
        # 품목코드별 총 판매량 계산
        total_sales_by_item = recent_sales.groupby('품목코드')['수량'].sum().reset_index()
        total_sales_by_item.rename(columns={'수량': '기간내_총판매량'}, inplace=True)
        
        # 월평균을 4로 나누어 '주 평균 판매량' 산출
        total_sales_by_item['월평균판매량'] = total_sales_by_item['기간내_총판매량'] / months_to_look_back
        total_sales_by_item['주평균판매량'] = (total_sales_by_item['월평균판매량'] / 4).round(1)
        
        # 4. 데이터 4개 병합 (자사재고 + 주평균판매량 + 과다기준주 + 박스입수)
        df_merged = pd.merge(df_own, total_sales_by_item[['품목코드', '주평균판매량']], on='품목코드', how='left')
        df_merged['주평균판매량'] = df_merged['주평균판매량'].fillna(0)
        
        df_merged = pd.merge(df_merged, df_item_limit, on='품목코드', how='left')
        df_merged = pd.merge(df_merged, df_item_box, on='품목코드', how='left')
        
        # 5. 로직 계산 (소진주, 상태 판별)
        import numpy as np
        df_merged['예상소진주'] = np.where(df_merged['주평균판매량'] > 0, 
                                       df_merged['현재재고'] / df_merged['주평균판매량'], 
                                       999.0)
        df_merged['예상소진주'] = df_merged['예상소진주'].round(1)
        
        # E열 데이터 기반 상태 판별 로직
        def check_status(row):
            if row['현재재고'] <= 0: return "🔴 품절"
            elif row['예상소진주'] < 4.0: return "🟠 재고 부족 (4주 미만)"
            else:
                limit = row['과다기준주'] if pd.notna(row['과다기준주']) and row['과다기준주'] > 0 else 24.0
                if row['예상소진주'] > limit:
                    return f"🔵 과다 재고 ({int(limit)}주 초과)"
                else:
                    return "🟢 적정"
            
        df_merged['재고상태'] = df_merged.apply(check_status, axis=1)

        # 🚀 [핵심] 박스 환산 표시 로직
        def format_stock_display(row):
            qty = row['현재재고']
            box_unit = row['박스입수']
            
            # 박스입수가 1개이거나 없으면 낱개로 표시
            if box_unit <= 1:
                return f"{int(qty):,} 개"
            else:
                boxes = qty / box_unit
                # 10박스 미만은 소수점 1자리까지 표시
                if boxes < 10:
                    return f"{boxes:.1f} 박스"
                # 10박스 이상은 깔끔하게 정수로 표시
                else:
                    return f"{int(boxes):,} 박스"

        df_merged['환산재고'] = df_merged.apply(format_stock_display, axis=1)

        # 6. 화면 출력
        if selected_brand != "전체보기":
            df_merged = df_merged[df_merged['브랜드'] == selected_brand]
            
        if selected_status != "전체보기":
            df_merged = df_merged[df_merged['재고상태'].str.contains(selected_status, na=False)]
            
        # 메인 화면 컬럼 순서 업데이트 ('현재재고' 대신 '환산재고' 출력)
        final_display_df = df_merged[['브랜드', '품목명', '환산재고', '주평균판매량', '예상소진주', '재고상태']]
        
        date_range_str = f"{start_date.year}년 {start_date.month}월 ~ {end_date.year}년 {end_date.month}월"
        st.subheader(f"📋 [{selected_brand}] 재고 상태 종합표 (필터: {selected_status})")
        st.caption(f"💡 산출 기준: {date_range_str} ({months_to_look_back}개월 판매량을 4주 단위로 환산했습니다.)")
        
        st.dataframe(final_display_df, use_container_width=True)
        
    except Exception as e:
        st.error(f"데이터 분석 중 오류가 발생했습니다: {e}")

# ------------------------------------------
# [메뉴 2] 쿠팡 재고 현황 (광고센터 크롤링)
# ------------------------------------------
elif main_menu == "🚀 쿠팡 재고 현황":
    st.title("🚀 쿠팡 재고 현황")
    st.info("💡 향후 이곳에 쿠팡 품절 임박 상품, 과다 재고 알림 등의 로직이 추가될 예정입니다.")
    
    try:
        df_coupang = load_sheet_data("coupang_stock")
        
        last_update = df_coupang['기록시간'].iloc[0] if not df_coupang.empty and '기록시간' in df_coupang.columns else '정보 없음'
        st.caption(f"최근 데이터 동기화: {last_update}")
        
        st.subheader("📋 쿠팡 원본 데이터 확인")
        st.dataframe(df_coupang, use_container_width=True)
        
    except Exception as e:
        st.error(f"쿠팡 데이터를 불러오지 못했습니다: {e}")

# ------------------------------------------
# [메뉴 3] 판매 현황 (이카운트 매출)
# ------------------------------------------
elif main_menu == "📈 판매 현황":
    st.title("📈 제품별 판매 현황 및 트렌드")
    st.info("💡 향후 이곳에 기간(1~12개월) 선택 필터와, 판매량 기반 재고 소진 예상일 분석이 추가될 예정입니다.")
    
    try:
        df_sales = load_sheet_data("sales_record")
        
        st.subheader("📋 누적 판매 데이터 확인")
        # 데이터가 너무 많을 수 있으므로 최근 100개만 미리보기
        st.dataframe(df_sales.tail(100), use_container_width=True)
        
    except Exception as e:
        st.error(f"판매 데이터를 불러오지 못했습니다: {e}")






