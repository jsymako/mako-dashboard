import streamlit as st
import pandas as pd
import datetime
import json
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from utils import custom_fullscreen_spinner

# 🚀 구글 시트 연결 캐싱
@st.cache_resource
def get_gspread_client():
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    creds_dict = json.loads(st.secrets["gcp_service_account"])
    creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
    return gspread.authorize(creds)

# 🚀 신규 차수 생성을 위한 팝업 다이얼로그
@st.dialog("➕ 신규 발주 생성")
def create_new_round_dialog(sel_m_id, sel_m_name, default_next_round, get_client_func):
    st.write(f"제조사: **{sel_m_name}**")
    
    with st.form("new_round_form", clear_on_submit=True):
        new_r = st.number_input("생성할 신규 차수 번호를 입력하세요", min_value=1, value=int(default_next_round), step=1)
        sel_feet = st.selectbox("컨테이너 크기 (피트)", ["40피트", "20피트"])
        
        st.markdown("<p style='color:#7f8c8d; font-size:0.9rem;'>※ 생성 시 초기 상태는 '입력중'으로 지정되며, 생성된 차수만 메인 화면에서 조회 가능합니다.</p>", unsafe_allow_html=True)
        submit_btn = st.form_submit_button("신규 발주 차수 생성", use_container_width=True)
        
        if submit_btn:
            with st.spinner("새로운 발주 차수를 저장 중..."):
                try:
                    client = get_client_func()
                    doc = client.open("통합재고관리")
                    try: 
                        sheet_s = doc.worksheet("Order_Status")
                    except: 
                        sheet_s = doc.add_worksheet(title="Order_Status", rows="500", cols="5")
                        sheet_s.append_row(['제조사ID', '차수', '상태', '피트', '최종수정일'])
                    
                    records = sheet_s.get_all_records()
                    df_st = pd.DataFrame(records)
                    
                    is_duplicate = False
                    if not df_st.empty and '제조사ID' in df_st.columns and '차수' in df_st.columns:
                        is_duplicate = ((df_st['제조사ID'].astype(str) == str(sel_m_id)) & (df_st['차수'].astype(str) == str(new_r))).any()
                    
                    if is_duplicate:
                        st.error(f"❌ 이미 존재하는 차수입니다. ({new_r}차)")
                    else:
                        if not sheet_s.row_values(1):
                            sheet_s.append_row(['제조사ID', '차수', '상태', '피트', '최종수정일'])
                            
                        today_str = datetime.datetime.now().strftime("%Y-%m-%d")
                        sheet_s.append_row([str(sel_m_id), str(new_r), "입력중", str(sel_feet), today_str])
                        st.session_state[f"selected_round_{sel_m_id}"] = int(new_r)
                        st.success("🎉 새로운 발주 차수가 정상 생성되었습니다!")
                        st.cache_data.clear()
                        st.rerun()
                except Exception as e:
                    st.error(f"차수 생성 중 오류 발생: {e}")

def run(load_data_func):
    try:
        with open("style.css", "r", encoding="utf-8") as f:
            st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)
    except FileNotFoundError:
        pass

    st.title("📦 발주 관리")

    # ==========================================
    # 1. 데이터 마스터 로드 및 안전 장치
    # ==========================================
    try:
        df_m = load_data_func("Manufacturers")
        df_item = load_data_func("ecount_item_data")
        df_trade = load_data_func("trade_record")
        df_emp = load_data_func("Employees")
        df_stock = load_data_func("ecount_stock")
        df_order = load_data_func("Order_Records")
        df_status = load_data_func("Order_Status")
        
        expected_order_cols = ['제조사ID', '차수', '품목코드', '직원명', '발주량']
        if df_order is None or df_order.empty:
            df_order = pd.DataFrame(columns=expected_order_cols)
        else:
            for col in expected_order_cols:
                if col not in df_order.columns: df_order[col] = ""
            
        expected_status_cols = ['제조사ID', '차수', '상태', '피트', '최종수정일']
        if df_status is None or df_status.empty:
            df_status = pd.DataFrame(columns=expected_status_cols)
        else:
            for col in expected_status_cols:
                if col not in df_status.columns: df_status[col] = ""
                    
    except Exception as e:
        st.error(f"구글 시트 데이터 마스터 동기화 실패: {e}")
        return

    df_trade.columns = ['일자', '거래처명', '품목코드', '품목명', '수량', '공급가액', '담당자']
    df_trade['일자'] = pd.to_datetime(df_trade['일자'], errors='coerce')
    df_trade['수량'] = pd.to_numeric(df_trade['수량'].astype(str).str.replace(',', ''), errors='coerce').fillna(0).astype(int)
    df_order['발주량'] = pd.to_numeric(df_order['발주량'], errors='coerce').fillna(0).astype(int)
    
    try:
        df_stock.columns = df_stock.columns.astype(str).str.strip()
        stock_map = df_stock.set_index('품목코드')['현재재고'].astype(str).str.replace(',', '')
        stock_map = pd.to_numeric(stock_map, errors='coerce').fillna(0).to_dict()
    except:
        stock_map = {}

    if df_emp is not None and '성명' in df_emp.columns and '발주입력' in df_emp.columns:
        allowed_input_emps = sorted(df_emp[df_emp['발주입력'].astype(str).str.strip().str.upper() == 'Y']['성명'].dropna().unique().tolist())
        if not allowed_input_emps:
            allowed_input_emps = ["권한자 없음"]
    else:
        allowed_input_emps = ["권한자 없음"]

    # ==========================================
    # 2. 사이드바 (제조사 및 신규생성)
    # ==========================================
    m_dict = {str(row['제조사명']): str(row['제조사ID']) for _, row in df_m.iterrows()}
    sel_m_name = st.sidebar.selectbox("제조사 필터", list(m_dict.keys()))
    sel_m_id = m_dict[sel_m_name]

    st.sidebar.markdown("---")

    all_rounds = df_status[df_status['제조사ID'].astype(str) == str(sel_m_id)]['차수'].astype(str).tolist()
    all_rounds = sorted(list(set([int(r) for r in all_rounds if r.isdigit()])))
    next_suggest = (all_rounds[-1] + 1) if all_rounds else 1
    
    if st.sidebar.button("➕ 신규 발주 생성", type="primary", use_container_width=True):
        create_new_round_dialog(sel_m_id, sel_m_name, next_suggest, get_gspread_client)

    # ==========================================
    # 3. 메인 제어반
    # ==========================================
    if not all_rounds:
        st.info(f"💡 현재 '{sel_m_name}' 제조사에 생성된 발주 차수가 없습니다. [신규 발주 생성]을 진행해 주세요.")
        return

    round_key = f"selected_round_{sel_m_id}"
    if round_key not in st.session_state or st.session_state[round_key] not in all_rounds:
        st.session_state[round_key] = all_rounds[-1] 

    main_ctrl = st.container(border=True)
    with main_ctrl:
        c2, c3, c4, c1, c5, c6 = st.columns([3, 2, 2, 2, 3, 2])
        
        with c1:
            sel_emp = st.selectbox("👨‍💼 내 이름(입력자) 선택", allowed_input_emps)
        
        def format_round_display(r):
            row = df_status[(df_status['제조사ID'].astype(str) == str(sel_m_id)) & (df_status['차수'].astype(str) == str(r))]
            if not row.empty:
                st_val = row['상태'].iloc[0]
                ft_val = row['피트'].iloc[0] if '피트' in row.columns and pd.notna(row['피트'].iloc[0]) and str(row['피트'].iloc[0]).strip() != "" else ""
                ft_str = f" {ft_val}" if ft_val else ""
                return f"📦 {r}차{ft_str} ({st_val})"
            return f"📦 {r}차"

        with c2:
            selected_round_val = st.selectbox(
                "🎯 조회/수정 차수 선택", 
                all_rounds, 
                index=all_rounds.index(st.session_state[round_key]),
                format_func=format_round_display
            )
            st.session_state[round_key] = selected_round_val
            
            status_filter = (df_status['제조사ID'].astype(str) == str(sel_m_id)) & (df_status['차수'].astype(str) == str(selected_round_val))
            db_status = df_status[status_filter]['상태'].iloc[0] if not df_status[status_filter].empty else "입력중"
            db_feet = df_status[status_filter]['피트'].iloc[0] if '피트' in df_status.columns and not df_status[status_filter].empty else ""
        
        with c3:
            status_opts = ["입력중", "완료"]
            sel_status = st.selectbox("🚦 상태 변경", status_opts, index=status_opts.index(db_status) if db_status in status_opts else 0)
            
        with c4:
            st.markdown("<div style='margin-top: 28px;'></div>", unsafe_allow_html=True)
            if st.button("🗑️ 현재 차수 삭제", type="secondary", use_container_width=True):
                with st.spinner("삭제 중..."):
                    try:
                        client = get_gspread_client()
                        doc = client.open("통합재고관리")
                        s_sheet = doc.worksheet("Order_Status")
                        s_df = pd.DataFrame(s_sheet.get_all_records())
                        if not s_df.empty:
                            s_df = s_df[~((s_df['제조사ID'].astype(str) == str(sel_m_id)) & (s_df['차수'].astype(str) == str(selected_round_val)))]
                            s_sheet.clear()
                            s_sheet.update([s_df.columns.values.tolist()] + s_df.astype(str).values.tolist() if not s_df.empty else [['제조사ID', '차수', '상태', '피트', '최종수정일']])

                        o_sheet = doc.worksheet("Order_Records")
                        o_df = pd.DataFrame(o_sheet.get_all_records())
                        if not o_df.empty:
                            o_df = o_df[~((o_df['제조사ID'].astype(str) == str(sel_m_id)) & (o_df['차수'].astype(str) == str(selected_round_val)))]
                            o_sheet.clear()
                            o_sheet.update([o_df.columns.values.tolist()] + o_df.astype(str).values.tolist() if not o_df.empty else [['제조사ID', '차수', '품목코드', '직원명', '발주량']])

                        if round_key in st.session_state: del st.session_state[round_key]
                        st.cache_data.clear()
                        st.rerun()
                    except Exception as e:
                        st.error(f"삭제 오류: {e}")
                        
        with c5:
            ref_rounds = st.multiselect("🚚 입고 대기 차수 추가", [r for r in all_rounds if r != selected_round_val], placeholder="비교할 과거 차수 다중 선택 가능")
        with c6:
            months_opt = st.slider("📊 평균판매량 산출 (최근 N개월)", min_value=1, max_value=12, value=3)

    # ==========================================
    # 4. SCM 수식 연산 및 CBM 로드 
    # ==========================================
    target_items = df_item[df_item['제조사'].astype(str) == str(sel_m_id)].copy()
    if target_items.empty:
        st.warning(f"💡 현재 '{sel_m_name}' 제조사로 등록된 마스터 품목이 없습니다.")
        return

    # 🚀 파이썬의 최대 정밀도 연산 유지 (소수점 15자리 이상)
    target_items['CBM'] = pd.to_numeric(target_items.get('CBM', 0), errors='coerce').fillna(0.0)
    target_items['박스단위'] = pd.to_numeric(target_items['박스당개수'], errors='coerce').fillna(1).astype(int)
    target_items['품목명'] = "[" + target_items['브랜드'].fillna('미분류').astype(str) + "] " + target_items['이름'].astype(str)
    
    target_items['현재고(낱개)'] = target_items['품목코드'].map(stock_map).fillna(0).astype(int)
    target_items['현재고'] = (target_items['현재고(낱개)'] / target_items['박스단위']).fillna(0).astype(int)

    days_to_subtract = months_opt * 30
    weeks_in_period = days_to_subtract / 7.0
    recent_limit = datetime.datetime.now() - datetime.timedelta(days=days_to_subtract)
    
    df_trade_recent = df_trade[df_trade['일자'] >= recent_limit].copy()
    df_trade_recent_emp = df_trade_recent[df_trade_recent['담당자'] == str(sel_emp)]
    
    total_sales_units = df_trade_recent.groupby('품목코드')['수량'].sum()
    emp_sales_units = df_trade_recent_emp.groupby('품목코드')['수량'].sum()
    
    target_items['전체평균(낱개)'] = target_items['품목코드'].map(total_sales_units).fillna(0)
    target_items['입력자평균(낱개)'] = target_items['품목코드'].map(emp_sales_units).fillna(0)
    
    target_items['전체평균'] = ((target_items['전체평균(낱개)'] / target_items['박스단위']) / weeks_in_period).round(0).astype(int)
    target_items['입력자평균'] = ((target_items['입력자평균(낱개)'] / target_items['박스단위']) / weeks_in_period).round(0).astype(int)

    if ref_rounds:
        df_ref_filtered = df_order[(df_order['제조사ID'].astype(str) == str(sel_m_id)) & (df_order['차수'].astype(int).isin([int(r) for r in ref_rounds]))]
        ref_series = df_ref_filtered.groupby('품목코드')['발주량'].sum()
        target_items['입고대기분'] = target_items['품목코드'].map(ref_series).fillna(0).astype(int)
    else:
        target_items['입고대기분'] = 0

    target_items['가용예상재고'] = (target_items['현재고'] + target_items['입고대기분']).fillna(0).astype(int)

    # ==========================================
    # 5. 피벗 연산 및 데이터 결합
    # ==========================================
    curr_orders = df_order[(df_order['제조사ID'].astype(str) == str(sel_m_id)) & (df_order['차수'].astype(str) == str(selected_round_val))]
    
    pivot_cols = allowed_input_emps + ['수정량']
    if not curr_orders.empty:
        order_pivot = curr_orders.pivot_table(index='품목코드', columns='직원명', values='발주량', aggfunc='sum').fillna(0)
    else:
        order_pivot = pd.DataFrame(0, index=target_items['품목코드'], columns=pivot_cols)
        
    for c in pivot_cols:
        if c not in order_pivot.columns: order_pivot[c] = 0
    order_pivot = order_pivot[pivot_cols].fillna(0).astype(int)
    
    base_columns = target_items[['품목코드', '품목명', 'CBM', '현재고', '입고대기분', '가용예상재고', '전체평균', '입력자평균']]
    final_df = pd.merge(base_columns, order_pivot.reset_index(), on='품목코드', how='left').fillna(0)
    
    emp_cols = allowed_input_emps
    
    final_df['수정량 입력✏️'] = final_df['수정량'].fillna(0).astype(int)
    final_df['입력 총량'] = final_df[emp_cols].sum(axis=1).fillna(0).astype(int)
    final_df['최종발주량'] = (final_df['입력 총량'] + final_df['수정량 입력✏️']).fillna(0).astype(int)

    # 합계 CBM 연산
    final_df['합계 CBM'] = (final_df['최종발주량'] * final_df['CBM']).fillna(0).astype(float)
    total_cbm = final_df['합계 CBM'].sum()

    display_layout = ['품목코드', '품목명', 'CBM', '현재고', '입고대기분', '가용예상재고', '전체평균', '입력자평균'] + emp_cols + ['입력 총량', '수정량 입력✏️', '최종발주량', '합계 CBM']
    final_df = final_df[display_layout]

    # ==========================================
    # 6. 총 CBM 표시 및 표 렌더링 (단층 구조 원복)
    # ==========================================
    # 🚀 표시 단위 소수점 8자리로 증가 (최대 정밀도 반영)
    st.markdown(f"""
        <div style="background-color: #2E86C1; padding: 12px; border-radius: 8px; text-align: center; color: white; margin-bottom: 10px; display: flex; justify-content: center; align-items: center
