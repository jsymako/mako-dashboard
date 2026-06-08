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
    try:
        with open("style.css", "r", encoding="utf-8") as f:
            st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)
    except: pass

    st.title("📦 발주 관리 (Order Management)")
    st.markdown("---")

    # ==========================================
    # 1. 데이터 로드 및 변수 초기화
    # ==========================================
    try:
        df_m = load_data_func("Manufacturers")
        df_item = load_data_func("ecount_item_data")
        df_trade = load_data_func("trade_record")
        df_emp = load_data_func("Employees")
        
        # 🚀 [핵심] emp_list를 여기서 확실하게 정의합니다.
        if df_emp is not None and not df_emp.empty and '성명' in df_emp.columns:
            emp_list = sorted(df_emp['성명'].dropna().unique().tolist())
        else:
            emp_list = ["직원 명단 없음"] # 시트가 비어있어도 에러 방지
        
        # ... (이하 기존 Order_Records, Order_Status 로드 로직 동일) ...
        df_order = load_data_func("Order_Records")
        if df_order is None or df_order.empty:
            df_order = pd.DataFrame(columns=['제조사ID', '차수', '품목코드', '직원명', '발주량'])
            
        df_status = load_data_func("Order_Status")
        if df_status is None or df_status.empty:
            df_status = pd.DataFrame(columns=['제조사ID', '차수', '상태', '최종수정일'])

    except Exception as e:
        st.error(f"데이터를 불러오는 중 오류가 발생했습니다: {e}")
        return

    # ==========================================
    # 2. 사이드바 필터
    # ==========================================
    st.sidebar.markdown("### ⚙️ 발주 설정")
    sel_emp = st.sidebar.selectbox("👨‍💼 내 이름(입력자) 선택", emp_list)
    m_dict = {str(row['제조사명']): str(row['제조사ID']) for _, row in df_m.iterrows()}
    sel_m_name = st.sidebar.selectbox("🏭 제조사 선택", list(m_dict.keys()))
    sel_m_id = m_dict[sel_m_name]
    
    # 차수 선택 (자동 갱신)
    exist_rounds = sorted([int(r) for r in df_order[df_order['제조사ID'].astype(str) == sel_m_id]['차수'].unique()], reverse=True)
    sel_round = st.sidebar.number_input("발주 차수", min_value=1, value=(exist_rounds[0] if exist_rounds else 1), step=1)
    
    # 상태 확인
    status_row = df_status[(df_status['제조사ID'].astype(str) == sel_m_id) & (df_status['차수'].astype(str) == str(sel_round))]
    current_status = status_row['상태'].iloc[0] if not status_row.empty else "입력중"
    st.sidebar.markdown(f"**현재 상태:** `{current_status}`")
    
    weeks_opt = st.sidebar.slider("📊 판매량 산출(최근 N주)", 1, 12, 4)

    # ==========================================
    # 3. 데이터 가공 (박스 단위 환산)
    # ==========================================
    box_col = next((c for c in df_item.columns if '박스' in c or '입수' in c), df_item.columns[3])
    df_item['박스입수'] = pd.to_numeric(df_item[box_col], errors='coerce').fillna(1)
    
    target_items = df_item[df_item['제조사'].astype(str) == sel_m_id].copy()
    stock_col = next((c for c in target_items.columns if '재고' in c), None)
    target_items['현재고(박스)'] = (pd.to_numeric(target_items[stock_col], errors='coerce').fillna(0) / target_items['박스입수']).round(1)

    # 판매량 가공
    recent_trade = df_trade[df_trade['일자'] >= (datetime.datetime.now() - datetime.timedelta(weeks=weeks_opt))]
    sales = recent_trade.groupby('품목코드')['수량'].sum() / target_items.set_index('품목코드')['박스입수']
    target_items['주평균판매량(박스)'] = (sales / weeks_opt).fillna(0).round(1)

    # 발주량 합산 (모든 직원 데이터)
    orders = df_order[(df_order['제조사ID'].astype(str) == sel_m_id) & (df_order['차수'].astype(str) == str(sel_round))]
    order_pivot = orders.pivot_table(index='품목코드', columns='직원명', values='발주량', aggfunc='sum').fillna(0)
    
    final_df = target_items[['품목코드', '이름', '현재고(박스)', '주평균판매량(박스)']].rename(columns={'이름': '품목명'})
    final_df = pd.merge(final_df, order_pivot, on='품목코드', how='left').fillna(0)
    final_df['내 발주량(박스)'] = final_df.get(sel_emp, 0)
    final_df['총 발주량(박스)'] = final_df.drop(columns=['품목코드', '품목명', '현재고(박스)', '주평균판매량(박스)']).sum(axis=1)

    # ==========================================
    # 4. 입력 보드
    # ==========================================
    st.subheader(f"📝 {sel_m_name} {sel_round}차 발주 입력")
    
    edited_df = st.data_editor(
        final_df,
        disabled=['품목코드', '품목명', '현재고(박스)', '주평균판매량(박스)', '총 발주량(박스)'],
        hide_index=True,
        use_container_width=True
    )

    if st.button("💾 저장 및 상태 변경"):
        client = get_gspread_client()
        doc = client.open("통합재고관리")
        # 1. Order_Records 업데이트
        sheet_o = doc.worksheet("Order_Records")
        # ... (기존 저장 로직과 동일하게 업데이트)
        st.success("저장 완료!")
