import streamlit as st
import pandas as pd
import datetime
import json
import gspread
from oauth2client.service_account import ServiceAccountCredentials


# 🚀 구글 시트 연결 캐싱 (인증 최적화)
@st.cache_resource
def get_gspread_client():
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    creds_dict = json.loads(st.secrets["gcp_service_account"])
    creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
    return gspread.authorize(creds)

# 🚀 신규 차수 생성을 위한 팝업 다이얼로그 정의
@st.dialog("➕ 신규 발주 차수 생성")
def create_new_round_dialog(sel_m_id, sel_m_name, default_next_round, get_client_func):
    st.write(f"🏭 제조사: **{sel_m_name}**")
    new_r = st.number_input("생성할 신규 차수 번호 입력", min_value=1, value=int(default_next_round), step=1)
    st.markdown("<p style='color:#7f8c8d; font-size:0.9rem;'>※ 신규 생성 시 초기 상태는 자동으로 <b>'입력중'</b>으로 세팅됩니다.</p>", unsafe_allow_html=True)
    
    if st.form_submit_button if hasattr(st, "form_submit_button") else st.button("🚀 차수 생성 및 즉시 시작", use_container_width=True):
        with st.spinner("새로운 발주 차수를 개설하고 있습니다..."):
            try:
                client = get_client_func()
                doc = client.open("통합재고관리")
                try: sheet_s = doc.worksheet("Order_Status")
                except: sheet_s = doc.add_worksheet(title="Order_Status", rows="500", cols="5")
                
                # 기존 상태 로드 및 중복 검사 후 추가
                records = sheet_s.get_all_records()
                df_st = pd.DataFrame(records)
                
                if not df_st.empty and ((df_st['제조사ID'].astype(str) == str(sel_m_id)) & (df_st['차수'].astype(str) == str(new_r))).any():
                    st.error(f"❌ 이미 존재하는 차수입니다. ({new_r}차)")
                else:
                    today_str = datetime.datetime.now().strftime("%Y-%m-%d")
                    sheet_s.append_row([str(sel_m_id), str(new_r), "입력중", today_str])
                    st.session_state[f"cur_round_{sel_m_id}"] = int(new_r)
                    st.success("🎉 새로운 발주 차수가 생성되었습니다!")
                    st.cache_data.clear()
                    st.rerun()
            except Exception as e:
                st.error(f"생성 실패: {e}")

def run(load_data_func):
    # 🚀 공통 CSS 로더 고정 반영
    try:
        with open("style.css", "r", encoding="utf-8") as f:
            st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)
    except FileNotFoundError:
        pass

    st.title("📦 발주 관리 시스템")
    st.markdown("---")

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
        if df_order is None or df_order.empty:
            df_order = pd.DataFrame(columns=['제조사ID', '차수', '품목코드', '직원명', '발주량'])
            
        df_status = load_data_func("Order_Status")
        if df_status is None or df_status.empty:
            df_status = pd.DataFrame(columns=['제조사ID', '차수', '상태', '최종수정일'])
    except Exception as e:
        st.error(f"구글 마스터 데이터 동기화 실패: {e}")
        return

    # 기본 파싱 정제
    df_trade.columns = ['일자', '거래처명', '품목코드', '품목명', '수량', '공급가액', '담당자']
    df_trade['일자'] = pd.to_datetime(df_trade['일자'], errors='coerce')
    df_trade['수량'] = pd.to_numeric(df_trade['수량'].astype(str).str.replace(',', ''), errors='coerce').fillna(0)
    df_order['발주량'] = pd.to_numeric(df_order['발주량'], errors='coerce').fillna(0)
    
    stock_map = df_stock.set_index('품목코드')['현재재고'].astype(str).str.replace(',', '')
    stock_map = pd.to_numeric(stock_map, errors='coerce').fillna(0).to_dict()

    emp_list = sorted(df_emp['성명'].dropna().unique().tolist()) if df_emp is not None and '성명' in df_emp.columns else ["미지정"]

    # ==========================================
    # 2. 사이드바 (제조사 및 담당자만 고정 배치)
    # ==========================================
    st.sidebar.markdown("### 🏭 소속 및 제조사")
    sel_emp = st.sidebar.selectbox("👨‍💼 내 이름(입력자) 선택", emp_list)
    m_dict = {str(row['제조사명']): str(row['제조사ID']) for _, row in df_m.iterrows()}
    sel_m_name = st.sidebar.selectbox("제조사 필터", list(m_dict.keys()))
    sel_m_id = m_dict[sel_m_name]

    # ==========================================
    # 3. 메인 화면 제어 컨트롤러 (차수 탐색 및 생성)
    # ==========================================
    # 해당 제조사의 기존 차수 목록 추출
    all_rounds = df_status[df_status['제조사ID'].astype(str) == str(sel_m_id)]['차수'].astype(str).tolist()
    all_rounds = sorted(list(set([int(r) for r in all_rounds if r.isdigit()])))
    
    # 세션 상태 주입을 통한 차수 기억 연동
    state_key = f"cur_round_{sel_m_id}"
    if state_key not in st.session_state:
        st.session_state[state_key] = all_rounds[-1] if all_rounds else 1
        
    # 차수 이동 및 매칭용 서브 UI 레이아웃
    ctrl_box = st.container(border=True)
    with ctrl_box:
        cc1, cc2, cc3, cc4, cc5 = st.columns([1, 2, 1, 2, 2])
        
        # 차수 다운 버튼 <
        if cc1.button("◀ 이전 차수", use_container_width=True):
            if all_rounds and st.session_state[state_key] in all_rounds:
                cur_idx = all_rounds.index(st.session_state[state_key])
                if cur_idx > 0: st.session_state[state_key] = all_rounds[cur_idx - 1]
            else:
                if st.session_state[state_key] > 1: st.session_state[state_key] -= 1
            st.rerun()
            
        # 현재 차수 정보 폰트 스케일업 표출
        with cc2:
            st.markdown(f"<h3 style='text-align:center; margin:0; padding-top:2px;'>🎯 {st.session_state[state_key]}차 발주</h3>", unsafe_allow_html=True)
            
        # 차수 업 버튼 >
        if cc3.button("다음 차수 ▶", use_container_width=True):
            if all_rounds and st.session_state[state_key] in all_rounds:
                cur_idx = all_rounds.index(st.session_state[state_key])
                if cur_idx < len(all_rounds) - 1: st.session_state[state_key] = all_rounds[cur_idx + 1]
            else:
                st.session_state[state_key] += 1
            st.rerun()

        # 실시간 상태 체크 및 변경 스위치
        round_val = st.session_state[state_key]
        status_filter = (df_status['제조사ID'].astype(str) == str(sel_m_id)) & (df_status['차수'].astype(str) == str(round_val))
        db_status = df_status[status_filter]['상태'].iloc[0] if not df_status[status_filter].empty else "입력중"
        
        with cc4:
            status_opts = ["입력중", "완료"]
            sel_status = st.selectbox("🚦 차수 상태 관리", status_opts, index=status_opts.index(db_status))
            
        # 신규 차수 팝업 트리거
        with cc5:
            st.markdown("<div style='padding-top:4px;'></div>", unsafe_allow_html=True)
            next_suggest = (all_rounds[-1] + 1) if all_rounds else 1
            if st.button("➕ 신규 차수 생성", color="primary", use_container_width=True):
                create_new_round_dialog(sel_m_id, sel_m_name, next_suggest, get_gspread_client)

    # 분석 주차 및 입고 대기 참고 차수 설정 바
    param_box = st.columns([4, 6])
    with param_box[0]:
        weeks_opt = st.slider("📊 판매량 산출 기준 (최근 N주)", min_value=1, max_value=12, value=4)
    with param_box[1]:
        ref_rounds = st.multiselect("🚚 입고정산/참고용 과거 차수 선택 (합산 표출)", [r for r in all_rounds if r != round_val], placeholder="비교 및 이월 잔량 차수 선택")

    # ==========================================
    # 4. 박스 단위 완전 연산 및 명칭 결합
    # ==========================================
    target_items = df_item[df_item['제조사'].astype(str) == str(sel_m_id)].copy()
    if target_items.empty:
        st.warning(f"💡 현재 '{sel_m_name}' 제조사로 등록된 마스터 품목이 없습니다.")
        return

    target_items['박스단위'] = pd.to_numeric(target_items['박스당개수'], errors='coerce').fillna(1)
    
    # 🚀 [품목이름 결합 수정] 브랜드 + 품목이름 복합구조 적용
    target_items['품목명'] = "[" + target_items['브랜드'].fillna('미분류').astype(str) + "] " + target_items['이름'].astype(str)
    
    target_items['현재고(낱개)'] = target_items['품목코드'].map(stock_map).fillna(0).astype(float)
    target_items['현재고(박스)'] = (target_items['현재고(낱개)'] / target_items['박스단위']).round(1)

    # 주평균 판매량 (박스 변환)
    recent_limit = datetime.datetime.now() - datetime.timedelta(weeks=weeks_opt)
    df_trade_recent = df_trade[df_trade['일자'] >= recent_limit]
    sales_units = df_trade_recent.groupby('품목코드')['수량'].sum().reindex(target_items['품목코드'], fill_value=0)
    target_items['주평균판매량(박스)'] = ((sales_units / target_items.set_index('품목코드')['박스단위']) / weeks_opt).fillna(0).round(1)

    # 🚀 [참고용 과거 차수 데이터 연동 수식] Multi-Select 대응 구조
    if ref_rounds:
        df_ref_filtered = df_order[(df_order['제조사ID'].astype(str) == str(sel_m_id)) & (df_order['차수'].isin(ref_rounds))]
        ref_series = df_ref_filtered.groupby('품목코드')['발주량'].sum().reindex(target_items['품목코드'], fill_value=0)
        target_items['참고 차수 발주량(박스)'] = ref_series.values
    else:
        target_items['참고 차수 발주량(박스)'] = 0.0

    # ==========================================
    # 5. 다중 사용자 피벗 테이블 연산 
    # ==========================================
    curr_orders = df_order[(df_order['제조사ID'].astype(str) == str(sel_m_id)) & (df_order['차수'].astype(str) == str(round_val))]
    order_pivot = curr_orders.pivot_table(index='품목코드', columns='직원명', values='발주량', aggfunc='sum').fillna(0)
    
    base_columns = target_items[['품목코드', '품목명', '현재고(박스)', '주평균판매량(박스)', '참고 차수 발주량(박스)']]
    final_df = pd.merge(base_columns, order_pivot, on='품목코드', how='left').fillna(0)
    
    # 내 입력 및 타 직원 열 위상 분리 정렬
    if sel_emp not in final_df.columns:
        final_df['내 발주량(박스)'] = 0.0
    else:
        final_df['내 발주량(박스)'] = final_df[sel_emp]
        
    other_staffs = [c for c in order_pivot.columns if c != sel_emp]
    final_df['총 발주량(박스)'] = final_df[other_staffs].sum(axis=1) + final_df['내 발주량(박스)']

    # 컬럼 가독성 정렬 순서 정의
    display_layout = ['품목코드', '품목명', '현재고(박스)', '주평균판매량(박스)', '참고 차수 발주량(박스)'] + other_staffs + ['내 발주량(박스)', '총 발주량(박스)']
    final_df = final_df[display_layout]

    # ==========================================
    # 6. 🚀 표 스크롤 완전 제거 패치 및 렌더링
    # ==========================================
    # 💡 행 개수에 맞춰 높이를 동적으로 연산하여 내부 스크롤바 발생 원천 차단
    calculated_height = (len(final_df) + 1) * 36 + 45
    
    editable_config = st.data_editor(
        final_df,
        disabled=[c for c in display_layout if c != '내 발주량(박스)'],
        hide_index=True,
        use_container_width=True,
        height=int(calculated_height),
        column_config={
            "내 발주량(박스)": st.column_config.NumberColumn("내 발주량(박스✏️)", min_value=0.0, step=0.1, format="%.1f"),
            "총 발주량(박스)": st.column_config.NumberColumn("총 발주량(박스)", format="%.1f"),
            "현재고(박스)": st.column_config.NumberColumn("현재고(박스)", format="%.1f"),
            "주평균판매량(박스)": st.column_config.NumberColumn("주평균판매량", format="%.1f"),
            "참고 차수 발주량(박스)": st.column_config.NumberColumn("🛒 선택차수 입고대기분", format="%.1f")
        }
    )

    # ==========================================
    # 7. 통합 저장 분기 처리 엔진
    # ==========================================
    st.markdown("<br>", unsafe_allow_html=True)
    if st.button("💾 데이터 및 진행 상태 통합 저장", use_container_width=True, type="primary"):
        with st.spinner("구글 시트에 실시간 업로드 및 동기화 중..."):
            try:
                client = get_gspread_client()
                doc = client.open("통합재고관리")
                
                # ① 상태(Order_Status) 업데이트
                sheet_s = doc.worksheet("Order_Status")
                records_s = sheet_s.get_all_records()
                df_st_save = pd.DataFrame(records_s)
                
                # 기존 데이터 내 동일 조건 검색 후 정리
                if not df_st_save.empty:
                    df_st_save = df_st_save[~((df_st_save['제조사ID'].astype(str) == str(sel_m_id)) & (df_st_save['차수'].astype(str) == str(round_val)))]
                today_str = datetime.datetime.now().strftime("%Y-%m-%d")
                new_status_row = pd.DataFrame([{"제조사ID": str(sel_m_id), "차수": str(round_val), "상태": str(sel_status), "최종수정일": today_str}])
                df_st_save = pd.concat([df_st_save, new_status_row], ignore_index=True)
                
                sheet_s.clear()
                sheet_s.update([df_st_save.columns.values.tolist()] + df_st_save.astype(str).values.tolist())

                # ② 발주 수량(Order_Records) 업데이트
                sheet_o = doc.worksheet("Order_Records")
                records_o = sheet_o.get_all_records()
                df_ord_save = pd.DataFrame(records_o)
                
                if not df_ord_save.empty:
                    # 내 데이터만 타깃하여 덮어쓰기 정제
                    df_ord_save = df_ord_save[~((df_ord_save['제조사ID'].astype(str) == str(sel_m_id)) & 
                                               (df_ord_save['차수'].astype(str) == str(round_val)) & 
                                               (df_ord_save['직원명'].astype(str) == str(sel_emp)))]
                
                # 에디터 시트에서 수정한 값 추출
                changed_rows = editable_config[editable_config['내 발주량(박스)'] > 0][['품목코드', '내 발주량(박스)']].copy()
                changed_rows['제조사ID'] = str(sel_m_id)
                changed_rows['차수'] = str(round_val)
                changed_rows['직원명'] = str(sel_emp)
                changed_rows.rename(columns={'내 발주량(박스)': '발주량'}, inplace=True)
                changed_rows = changed_rows[['제조사ID', '차수', '품목코드', '직원명', '발주량']]
                
                df_final_ord = pd.concat([df_ord_save, changed_rows], ignore_index=True)
                
                sheet_o.clear()
                if df_final_ord.empty:
                    sheet_o.append_row(['제조사ID', '차수', '품목코드', '직원명', '발주량'])
                else:
                    sheet_o.update([df_final_ord.columns.values.tolist()] + df_final_ord.astype(str).values.tolist())

                st.cache_data.clear()
                st.success(f"🎉 {round_val}차 발주 수량 및 진행상태 [{sel_status}] 저장이 성공적으로 완료되었습니다!")
                st.rerun()
            except Exception as e:
                st.error(f"구글 시트 연동 중 물리적 에러 발생: {e}")
