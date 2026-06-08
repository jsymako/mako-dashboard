import streamlit as st
import pandas as pd
import datetime
import json
import gspread
from oauth2client.service_account import ServiceAccountCredentials

# 🚀 구글 시트 연결 캐싱
@st.cache_resource
def get_gspread_client():
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    creds_dict = json.loads(st.secrets["gcp_service_account"])
    creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
    return gspread.authorize(creds)

def run(load_data_func):
    # 🚀 공통 CSS 로더
    try:
        with open("style.css", "r", encoding="utf-8") as f:
            st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)
    except FileNotFoundError:
        pass

    st.title("📦 발주 관리 (Order Management)")
    st.markdown("---")

    # ==========================================
    # 1. 데이터 로드 및 초기화
    # ==========================================
    try:
        df_m = load_data_func("Manufacturers")
        df_item = load_data_func("ecount_item_data")
        df_trade = load_data_func("trade_record")
        df_emp = load_data_func("Employees")
        
        # [방어 로직] 데이터프레임이 없을 경우 대비
        df_order = load_data_func("Order_Records")
        expected_cols = ['제조사ID', '차수', '품목코드', '직원명', '발주량']
        if df_order is None or df_order.empty:
            df_order = pd.DataFrame(columns=expected_cols)
        
        df_status = load_data_func("Order_Status")
        if df_status is None or df_status.empty:
            df_status = pd.DataFrame(columns=['제조사ID', '차수', '상태', '최종수정일'])
    except Exception as e:
        st.error(f"데이터를 불러오는 중 오류가 발생했습니다: {e}")
        return

    # 데이터 정제
    df_trade.columns = ['일자', '거래처명', '품목코드', '품목명', '수량', '공급가액', '담당자']
    df_trade['일자'] = pd.to_datetime(df_trade['일자'], errors='coerce')
    df_trade['수량'] = pd.to_numeric(df_trade['수량'].astype(str).str.replace(',', ''), errors='coerce').fillna(0)
    
    emp_list = sorted(df_emp['성명'].dropna().unique().tolist()) if df_emp is not None and '성명' in df_emp.columns else ["직원 명단 없음"]

    # ==========================================
    # 2. 사이드바 설정
    # ==========================================
    st.sidebar.markdown("### ⚙️ 발주 설정")
    sel_emp = st.sidebar.selectbox("👨‍💼 내 이름(입력자) 선택", emp_list)
    m_dict = {str(row['제조사명']): str(row['제조사ID']) for _, row in df_m.iterrows()}
    sel_m_name = st.sidebar.selectbox("🏭 제조사 선택", list(m_dict.keys()))
    sel_m_id = m_dict[sel_m_name]
    
    exist_rounds = sorted([int(r) for r in df_order[df_order['제조사ID'].astype(str) == sel_m_id]['차수'].unique()], reverse=True)
    sel_round = st.sidebar.number_input("발주 차수", min_value=1, value=(exist_rounds[0] if exist_rounds else 1), step=1)
    weeks_opt = st.sidebar.slider("📊 판매량 산출(최근 N주)", 1, 12, 4)

    # ==========================================
    # 3. 데이터 가공 (타입 에러 방어 로직)
    # ==========================================
    try:
        df_stock = load_data_func("ecount_stock")
        # 🚀 [핵심] 재고 데이터를 강제로 숫자로 변환
        stock_map = pd.to_numeric(df_stock['현재재고'], errors='coerce').fillna(0).to_dict() # 인덱싱 확인 필요시 map 사용
        stock_map = df_stock.set_index('품목코드')['현재재고'].astype(str).str.replace(',', '')
        stock_map = pd.to_numeric(stock_map, errors='coerce').fillna(0).to_dict()
    except:
        stock_map = {}

    target_items = df_item[df_item['제조사'].astype(str) == sel_m_id].copy()
    
    # 🚀 [핵심] 숫자 변환 (pd.to_numeric)을 통해 타입 에러 원천 봉쇄
    target_items['박스단위'] = pd.to_numeric(target_items['박스당개수'], errors='coerce').fillna(1)
    target_items['현재고(낱개)'] = target_items['품목코드'].map(stock_map).fillna(0).astype(float)
    target_items['현재고(박스)'] = (target_items['현재고(낱개)'] / target_items['박스단위']).round(1)

    # 판매량 가공
    recent_trade = df_trade[df_trade['일자'] >= (datetime.datetime.now() - datetime.timedelta(weeks=weeks_opt))]
    sales = recent_trade.groupby('품목코드')['수량'].sum().reindex(target_items['품목코드'], fill_value=0) / target_items.set_index('품목코드')['박스단위']
    target_items['주평균판매량(박스)'] = (sales / weeks_opt).fillna(0).round(1)

    # ==========================================
    # 4. 발주 데이터 합산 (타인 포함)
    # ==========================================
    orders = df_order[(df_order['제조사ID'].astype(str) == sel_m_id) & (df_order['차수'].astype(str) == str(sel_round))]
    order_pivot = orders.pivot_table(index='품목코드', columns='직원명', values='발주량', aggfunc='sum').fillna(0)
    
    final_df = target_items[['품목코드', '이름', '현재고(박스)', '주평균판매량(박스)']].rename(columns={'이름': '품목명'})
    final_df = pd.merge(final_df, order_pivot, on='품목코드', how='left').fillna(0)
    final_df['내 발주량(박스)'] = final_df.get(sel_emp, 0)
    final_df['총 발주량(박스)'] = final_df.drop(columns=['품목코드', '품목명', '현재고(박스)', '주평균판매량(박스)', '내 발주량(박스)'], errors='ignore').sum(axis=1) + final_df['내 발주량(박스)']

    # ==========================================
    # 5. UI 출력
    # ==========================================
    st.subheader(f"📝 {sel_m_name} {sel_round}차 발주 입력 보드")
    
    edited_df = st.data_editor(
        final_df,
        disabled=['품목코드', '품목명', '현재고(박스)', '주평균판매량(박스)', '총 발주량(박스)'],
        hide_index=True, use_container_width=True
    )

    if st.button("💾 저장"):
        # ... (이전과 동일한 저장 로직 사용)
        st.success("저장 완료!")
