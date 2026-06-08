import streamlit as st
import pandas as pd
import datetime
import json
import gspread
from oauth2client.service_account import ServiceAccountCredentials

# 🚀 구글 시트 연결 캐싱 (속도 최적화)
@st.cache_resource
def get_gspread_client():
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    creds_dict = json.loads(st.secrets["gcp_service_account"])
    creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
    return gspread.authorize(creds)

def run(load_data_func):
    st.title("📦 발주 관리 (Order Management)")

    try:
        with open("style.css", "r", encoding="utf-8") as f:
            st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)
    except FileNotFoundError:
        pass

    # ==========================================
    # 1. 필수 데이터 로드
    # ==========================================
    try:
        df_m = load_data_func("Manufacturers")
        df_item = load_data_func("ecount_item_data")
        df_trade = load_data_func("trade_record")
        df_emp = load_data_func("Employees")
        
        # 신규 발주 기록 시트 (없으면 빈 데이터프레임 생성)
        try:
            df_order = load_data_func("Order_Records")
            if df_order is None or df_order.empty:
                df_order = pd.DataFrame(columns=['제조사ID', '차수', '품목코드', '직원명', '발주량'])
        except:
            df_order = pd.DataFrame(columns=['제조사ID', '차수', '품목코드', '직원명', '발주량'])
            
    except Exception as e:
        st.error(f"데이터를 불러오는 중 오류가 발생했습니다: {e}")
        return

    # 데이터 정제
    df_trade.columns = ['일자', '거래처명', '품목코드', '품목명', '수량', '공급가액', '담당자']
    df_trade['일자'] = pd.to_datetime(df_trade['일자'], errors='coerce')
    df_trade['수량'] = pd.to_numeric(df_trade['수량'].astype(str).str.replace(',', ''), errors='coerce').fillna(0)
    
    # '재고' 열 찾기 (이름이 다를 수 있으므로 방어 로직)
    stock_col = next((col for col in df_item.columns if '재고' in col), None)
    
    # 직원 목록 동적 로드
    emp_list = []
    if df_emp is not None and not df_emp.empty and '성명' in df_emp.columns:
        emp_list = sorted(df_emp['성명'].dropna().unique().tolist())

    # ==========================================
    # 2. 사이드바 설정 (필터 및 옵션)
    # ==========================================
    st.sidebar.markdown("### ⚙️ 발주 설정")
    
    # ① 입력할 직원 선택
    sel_emp = st.sidebar.selectbox("👨‍💼 내 이름(입력자) 선택", emp_list)
    
    # ② 제조사 선택
    m_dict = {str(row['제조사명']): str(row['제조사ID']) for _, row in df_m.iterrows()}
    sel_m_name = st.sidebar.selectbox("🏭 제조사 선택", list(m_dict.keys()))
    sel_m_id = m_dict[sel_m_name]
    
    # ③ 차수 선택 (기존 차수 목록 + 신규 입력 가능)
    exist_rounds = df_order[df_order['제조사ID'] == sel_m_id]['차수'].unique().tolist()
    exist_rounds = sorted([int(r) for r in exist_rounds if str(r).isdigit()], reverse=True)
    
    round_mode = st.sidebar.radio("발주 차수", ["기존 발주 조회/수정", "새로운 차수 생성"])
    if round_mode == "새로운 차수 생성":
        sel_round = st.sidebar.number_input("신규 차수 입력", min_value=1, value=(max(exist_rounds)+1 if exist_rounds else 1), step=1)
    else:
        if not exist_rounds:
            st.sidebar.warning("기존 발주 내역이 없습니다. 신규 차수를 생성해주세요.")
            sel_round = 1
        else:
            sel_round = st.sidebar.selectbox("기존 차수 선택", exist_rounds)
            
    # ④ 판매량 분석 기준 주차 선택
    weeks_opt = st.sidebar.slider("📊 평균 판매량 산출 기준 (최근 N주)", min_value=1, max_value=12, value=4, step=1)

    # ==========================================
    # 3. 데이터 가공 (해당 제조사 품목 & 판매량 & 재고)
    # ==========================================
    # 해당 제조사 품목만 필터링
    if '제조사' not in df_item.columns:
        st.error("🚨 ecount_item_data 탭에 '제조사' 열이 존재하지 않습니다.")
        return
        
    target_items = df_item[df_item['제조사'].astype(str) == sel_m_id].copy()
    if target_items.empty:
        st.warning(f"'{sel_m_name}' 제조사에 매핑된 품목이 없습니다. 마스터 데이터를 확인해주세요.")
        return

    # 재고 매핑
    target_items['현재고'] = pd.to_numeric(target_items[stock_col], errors='coerce').fillna(0) if stock_col else 0
    target_items = target_items[['품목코드', '이름', '현재고']].rename(columns={'이름': '품목명'})

    # 판매량 매핑 (최근 N주)
    today = datetime.datetime.today()
    start_date = today - datetime.timedelta(weeks=weeks_opt)
    
    recent_trade = df_trade[df_trade['일자'] >= start_date]
    sales_sum = recent_trade.groupby('품목코드')['수량'].sum().reset_index()
    sales_sum['주평균판매량'] = (sales_sum['수량'] / weeks_opt).round(1)
    
    # 베이스 데이터 병합
    base_df = pd.merge(target_items, sales_sum[['품목코드', '주평균판매량']], on='품목코드', how='left').fillna({'주평균판매량': 0})

    # ==========================================
    # 4. 기존 발주 데이터 결합 (타 직원 입력분 포함)
    # ==========================================
    df_order['발주량'] = pd.to_numeric(df_order['발주량'], errors='coerce').fillna(0)
    current_orders = df_order[(df_order['제조사ID'] == sel_m_id) & (df_order['차수'].astype(str) == str(sel_round))]

    # 엑셀처럼 보기 위해 피벗 (품목코드 기준, 직원명 컬럼화)
    if not current_orders.empty:
        pivot_orders = current_orders.pivot_table(index='품목코드', columns='직원명', values='발주량', aggfunc='sum').reset_index().fillna(0)
    else:
        pivot_orders = pd.DataFrame(columns=['품목코드'])

    # 베이스 데이터에 피벗된 직원별 입력량 결합
    final_df = pd.merge(base_df, pivot_orders, on='품목코드', how='left').fillna(0)

    # 타 직원들 명단 추출 (나 제외)
    other_emps = [col for col in pivot_orders.columns if col != '품목코드' and col != sel_emp]
    
    # '내 발주량' 변수 확보
    if sel_emp in final_df.columns:
        final_df['내 발주량 (수정)'] = final_df[sel_emp]
    else:
        final_df['내 발주량 (수정)'] = 0.0

    # 총 발주량 계산
    final_df['총 발주량 (합계)'] = final_df[other_emps].sum(axis=1) + final_df['내 발주량 (수정)']

    # 컬럼 순서 정렬 가독성 있게 배치
    display_cols = ['품목코드', '품목명', '현재고', '주평균판매량'] + other_emps + ['내 발주량 (수정)', '총 발주량 (합계)']
    final_df = final_df[display_cols]

    # ==========================================
    # 5. UI 출력 및 데이터 에디터 (수정 가능 표)
    # ==========================================
    st.subheader(f"📝 {sel_m_name} - {sel_round}차 발주 입력 보드")
    st.markdown(f"**진행자:** {sel_emp} &nbsp;&nbsp;|&nbsp;&nbsp; **판매량 기준:** 최근 {weeks_opt}주")
    
    # 데이터 에디터 설정 ('내 발주량' 열만 수정 가능하도록 제한!)
    disabled_cols = [col for col in display_cols if col != '내 발주량 (수정)']
    
    edited_df = st.data_editor(
        final_df,
        disabled=disabled_cols,
        hide_index=True,
        use_container_width=True,
        column_config={
            "내 발주량 (수정)": st.column_config.NumberColumn("내 발주량 (수정✏️)", required=True, min_value=0, step=1, width="medium"),
            "총 발주량 (합계)": st.column_config.NumberColumn("총 발주량 (합계)", width="medium"),
            "주평균판매량": st.column_config.NumberColumn(f"주평균판매량({weeks_opt}주)", format="%.1f"),
            "현재고": st.column_config.NumberColumn("현재고", format="%d")
        },
        height=600
    )

    # ==========================================
    # 6. 저장 로직 (구글 시트 업데이트)
    # ==========================================
    st.markdown("<br>", unsafe_allow_html=True)
    if st.button("💾 내 발주량 저장 (구글 시트에 동기화)", use_container_width=True):
        with st.spinner("구글 시트에 데이터를 기록하고 있습니다..."):
            try:
                client = get_gspread_client()
                doc = client.open("통합재고관리")
                try: sheet = doc.worksheet("Order_Records")
                except: sheet = doc.add_worksheet(title="Order_Records", rows="1000", cols="5")

                # 전체 시트 데이터 로드
                all_records = sheet.get_all_records()
                df_all = pd.DataFrame(all_records)
                
                if not df_all.empty:
                    # 이번에 저장하는 조건(제조사, 차수, 직원명)과 겹치는 기존 기록은 삭제 (덮어쓰기를 위함)
                    mask = ~((df_all['제조사ID'].astype(str) == str(sel_m_id)) & 
                             (df_all['차수'].astype(str) == str(sel_round)) & 
                             (df_all['직원명'].astype(str) == str(sel_emp)))
                    df_all = df_all[mask]
                
                # 에디터에서 방금 수정한 '내 발주량'이 0보다 큰 데이터만 추출
                new_orders = edited_df[edited_df['내 발주량 (수정)'] > 0][['품목코드', '내 발주량 (수정)']].copy()
                new_orders['제조사ID'] = sel_m_id
                new_orders['차수'] = sel_round
                new_orders['직원명'] = sel_emp
                new_orders.rename(columns={'내 발주량 (수정)': '발주량'}, inplace=True)
                new_orders = new_orders[['제조사ID', '차수', '품목코드', '직원명', '발주량']] # 컬럼 순서 맞춤
                
                # 기존 데이터 아래에 새로운 데이터 병합
                df_to_save = pd.concat([df_all, new_orders], ignore_index=True)
                
                # 구글 시트에 일괄 덮어쓰기 (가장 빠르고 안전한 방식)
                sheet.clear()
                if df_to_save.empty:
                    sheet.append_row(['제조사ID', '차수', '품목코드', '직원명', '발주량'])
                else:
                    sheet.update([df_to_save.columns.values.tolist()] + df_to_save.astype(str).values.tolist())

                st.cache_data.clear()
                st.success(f"🎉 성공적으로 저장되었습니다! ({len(new_orders)}개 품목 입력 완료)")
                st.rerun()

            except Exception as e:
                st.error(f"저장 중 오류 발생: {e}")
