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

# 🚀 신규 차수 생성을 위한 팝업 다이얼로그 (안전한 Form 구조 적용)
@st.dialog("➕ 신규 발주 차수 생성")
def create_new_round_dialog(sel_m_id, sel_m_name, default_next_round, get_client_func):
    st.write(f"🏭 대상 제조사: **{sel_m_name}**")
    
    with st.form("new_round_form", clear_on_submit=True):
        new_r = st.number_input("생성할 신규 차수 번호를 입력하세요", min_value=1, value=int(default_next_round), step=1)
        st.markdown("<p style='color:#7f8c8d; font-size:0.9rem;'>※ 생성 시 초기 상태는 '입력중'으로 지정되며, 생성된 차수만 메인 화면에서 조회 가능합니다.</p>", unsafe_allow_html=True)
        submit_btn = st.form_submit_button("🚀 차수 개설 및 생성하기", use_container_width=True)
        
        if submit_btn:
            with st.spinner("새로운 발주 차수를 구글 시트에 등록 중..."):
                try:
                    client = get_client_func()
                    doc = client.open("통합재고관리")
                    try: sheet_s = doc.worksheet("Order_Status")
                    except: sheet_s = doc.add_worksheet(title="Order_Status", rows="500", cols="5")
                    
                    records = sheet_s.get_all_records()
                    df_st = pd.DataFrame(records)
                    
                    if not df_st.empty and ((df_st['제조사ID'].astype(str) == str(sel_m_id)) & (df_st['차수'].astype(str) == str(new_r))).any():
                        st.error(f"❌ 이미 존재하는 차수입니다. ({new_r}차)")
                    else:
                        today_str = datetime.datetime.now().strftime("%Y-%m-%d")
                        sheet_s.append_row([str(sel_m_id), str(new_r), "입력중", today_str])
                        st.session_state[f"selected_round_{sel_m_id}"] = int(new_r)
                        st.success("🎉 새로운 발주 차수가 정상 생성되었습니다!")
                        st.cache_data.clear()
                        st.rerun()
                except Exception as e:
                    st.error(f"차수 생성 중 오류 발생: {e}")

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
        df_status = load_data_func("Order_Status")
        
        # 구조 방어선 구축
        expected_order_cols = ['제조사ID', '차수', '품목코드', '직원명', '발주량']
        if df_order is None or df_order.empty:
            df_order = pd.DataFrame(columns=expected_order_cols)
        else:
            for col in expected_order_cols:
                if col not in df_order.columns: df_order[col] = ""
            
        expected_status_cols = ['제조사ID', '차수', '상태', '최종수정일']
        if df_status is None or df_status.empty:
            df_status = pd.DataFrame(columns=expected_status_cols)
        else:
            for col in expected_status_cols:
                if col not in df_status.columns: df_status[col] = ""
                    
    except Exception as e:
        st.error(f"구글 시트 데이터 마스터 동기화 실패: {e}")
        return

    # 정산 전처리 숫자인식화
    df_trade.columns = ['일자', '거래처명', '품목코드', '품목명', '수량', '공급가액', '담당자']
    df_trade['일자'] = pd.to_datetime(df_trade['일자'], errors='coerce')
    df_trade['수량'] = pd.to_numeric(df_trade['수량'].astype(str).str.replace(',', ''), errors='coerce').fillna(0)
    df_order['발주량'] = pd.to_numeric(df_order['발주량'], errors='coerce').fillna(0)
    
    # 🚀 [재고 연동 패치] ecount_stock 정상 인덱싱 연동 완료
    try:
        df_stock.columns = df_stock.columns.astype(str).str.strip()
        stock_map = df_stock.set_index('품목코드')['현재재고'].astype(str).str.replace(',', '')
        stock_map = pd.to_numeric(stock_map, errors='coerce').fillna(0).to_dict()
    except Exception as e:
        stock_map = {}
        st.warning(f"⚠️ ecount_stock 매핑 엔진 경고: {e}")

    # 🚀 직원 명부 권한 필터링 ("발주입력" 열이 "Y"인 직원 추출)
    emp_list = sorted(df_emp['성명'].dropna().unique().tolist()) if df_emp is not None and '성명' in df_emp.columns else ["미지정"]
    
    if df_emp is not None and '발주입력' in df_emp.columns:
        allowed_input_emps = sorted(df_emp[df_emp['발주입력'].astype(str).str.upper() == 'Y']['성명'].dropna().unique().tolist())
    else:
        allowed_input_emps = emp_list.copy()

    # ==========================================
    # 2. 사이드바 (제조사 선택 / 담당자 지정 / 생성 다이얼로그)
    # ==========================================
    st.sidebar.markdown("### 🏭 수입 통제 센터")
    sel_emp = st.sidebar.selectbox("👨‍💼 내 이름(입력자) 선택", emp_list)
    
    # 내 이름이 발주 권한 목록(Y)에 없을 경우를 대비한 가동 강제 보장
    if sel_emp not in allowed_input_emps and sel_emp != "미지정":
        allowed_input_emps.append(sel_emp)
        
    m_dict = {str(row['제조사명']): str(row['제조사ID']) for _, row in df_m.iterrows()}
    sel_m_name = st.sidebar.selectbox("제조사 필터", list(m_dict.keys()))
    sel_m_id = m_dict[sel_m_name]

    st.sidebar.markdown("---")
    # 신규 생성 트리거 버튼 배치
    all_rounds = df_status[df_status['제조사ID'].astype(str) == str(sel_m_id)]['차수'].astype(str).tolist()
    all_rounds = sorted(list(set([int(r) for r in all_rounds if r.isdigit()])))
    next_suggest = (all_rounds[-1] + 1) if all_rounds else 1
    
    if st.sidebar.button("➕ 신규 발주 차수 생성", type="primary", use_container_width=True):
        create_new_round_dialog(sel_m_id, sel_m_name, next_suggest, get_gspread_client)

    # ==========================================
    # 3. 메인 제어반 상단 레이아웃 (드롭다운식 선택)
    # ==========================================
    if not all_rounds:
        st.info(f"💡 현재 '{sel_m_name}' 제조사에 생성된 발주 차수가 없습니다. 왼쪽 사이드바에서 [신규 발주 차수 생성]을 진행해 주세요.")
        return

    # 세션 기반 드롭다운 인덱스 연동 유지
    round_key = f"selected_round_{sel_m_id}"
    if round_key not in st.session_state or st.session_state[round_key] not in all_rounds:
        st.session_state[round_key] = all_rounds[-1] # 기본값은 가장 최신 차수

    main_ctrl = st.container(border=True)
    with main_ctrl:
        mc1, mc2, mc3 = st.columns([3, 3, 4])
        with mc1:
            # 🚀 [수정] 무조건 1차부터 보이던 로직 탈피 -> 생성된 차수만 드롭다운 표출
            selected_round_val = st.selectbox(
                "🎯 조회 및 수정할 차수 선택", 
                all_rounds, 
                index=all_rounds.index(st.session_state[round_key]),
                format_func=lambda x: f"📦 {x}차 발주 내역"
            )
            st.session_state[round_key] = selected_round_val
        
        # 실시간 상태 마스터 추적
        status_filter = (df_status['제조사ID'].astype(str) == str(sel_m_id)) & (df_status['차수'].astype(str) == str(selected_round_val))
        db_status = df_status[status_filter]['상태'].iloc[0] if not df_status[status_filter].empty else "입력중"
        
        with mc2:
            status_opts = ["입력중", "완료"]
            sel_status = st.selectbox("🚦 해당 차수 진행 상태 변경", status_opts, index=status_opts.index(db_status) if db_status in status_opts else 0)
            
        with mc3:
            weeks_opt = st.slider("📊 판매량 주차 스케일 (최근 N주)", min_value=1, max_value=12, value=4)

    # 보조 참고용 멀티셀렉터
    ref_rounds = st.multiselect("🚚 입고 정산용 참고 차수 선택 (대기량 합산용)", [r for r in all_rounds if r != selected_round_val], placeholder="비교할 과거 차수 다중 선택 가능")

    # ==========================================
    # 4. SCM 수식 연산 및 컬럼 하이브리드 결합
    # ==========================================
    target_items = df_item[df_item['제조사'].astype(str) == str(sel_m_id)].copy()
    target_items['박스단위'] = pd.to_numeric(target_items['박스당개수'], errors='coerce').fillna(1)
    
    # 🚀 [요구사항] 브랜드 + 품목명 복합 표출 처리
    target_items['품목명'] = "[" + target_items['브랜드'].fillna('미분류').astype(str) + "] " + target_items['이름'].astype(str)
    
    target_items['현재고(낱개)'] = target_items['품목코드'].map(stock_map).fillna(0).astype(float)
    target_items['현재고'] = (target_items['현재고(낱개)'] / target_items['박스단위']).round(1)

    # 주평균 판매량 (박스 변환 적용)
    recent_limit = datetime.datetime.now() - datetime.timedelta(weeks=weeks_opt)
    df_trade_recent = df_trade[df_trade['일자'] >= recent_limit]
    sales_units = df_trade_recent.groupby('품목코드')['수량'].sum().reindex(target_items['품목코드'], fill_value=0)
    target_items['주평균판매량'] = ((sales_units / target_items.set_index('품목코드')['박스단위']) / weeks_opt).fillna(0).round(1)

    # 선택차수 입고대기분 (Multi-Select 합산화)
    if ref_rounds:
        df_ref_filtered = df_order[(df_order['제조사ID'].astype(str) == str(sel_m_id)) & (df_order['차수'].astype(int).isin([int(r) for r in ref_rounds]))]
        ref_series = df_ref_filtered.groupby('품목코드')['발주량'].sum().reindex(target_items['품목코드'], fill_value=0)
        target_items['선택차수 입고대기분'] = ref_series.values
    else:
        target_items['선택차수 입고대기분'] = 0.0

    # 🚀 [요구사항] 가용예상재고 계산 공식 (현재고 + 입고대기분 - 주평균판매량)
    target_items['가용예상재고'] = (target_items['현재고'] + target_items['선택차수 입고대기분'] - target_items['주평균판매량']).round(1)

    # ==========================================
    # 5. 권한 기반 다중 사용자 피벗 매핑 연산
    # ==========================================
    curr_orders = df_order[(df_order['제조사ID'].astype(str) == str(sel_m_id)) & (df_order['차수'].astype(str) == str(selected_round_val))]
    
    # 🚀 일반 직원 입력량과 '수정량' 데이터를 구분하여 피벗 결합하기 위해 빈 컬럼 사전 구축
    pivot_cols = allowed_input_emps + ['수정량']
    if not curr_orders.empty:
        order_pivot = curr_orders.pivot_table(index='품목코드', columns='직원명', values='발주량', aggfunc='sum').fillna(0)
        # 필요한 권한 컬럼 재정렬 및 빈 공간 자동 0 처리
        for c in pivot_cols:
            if c not in order_pivot.columns: order_pivot[c] = 0.0
        order_pivot = order_pivot[pivot_cols]
    else:
        order_pivot = pd.DataFrame(0.0, index=target_items['품목코드'], columns=pivot_cols)
    
    base_columns = target_items[['품목코드', '품목명', '현재고', '주평균판매량', '선택차수 입고대기분', '가용예상재고']]
    final_df = pd.merge(base_columns, order_pivot.reset_index(), on='품목코드', how='left').fillna(0)
    
    # 🚀 권한 명단에 맞춰 열 이름 매핑 ('(박스)' 명칭화)
    emp_column_rename = {emp: f"{emp}(박스)" for emp in allowed_input_emps}
    final_df.rename(columns=emp_column_rename, inplace=True)
    
    renamed_emp_cols = [f"{emp}(박스)" for emp in allowed_input_emps]
    my_edit_col = f"{sel_emp}(박스)"
    
    # 🚀 [요구사항] 입력 총량 계산 (직원들의 총 입력량 더한 값)
    final_df['입력 총량'] = final_df[renamed_emp_cols].sum(axis=1).round(1)
    
    # 🚀 [요구사항] 수정량 입력 매핑
    final_df['수정량 입력✏️'] = final_df['수정량'].astype(float).round(1)
    
    # 🚀 [요구사항] 최종발주량 계산 공식 (입력 총량 - 수정량 입력)
    final_df['최종발주량'] = (final_df['입력 총량'] - final_df['수정량 입력✏️']).round(1)

    # 데이터 에디터 최종 열 시퀀스 설계
    display_layout = ['품목코드', '품목명', '현재고', '주평균판매량', '선택차수 입고대기분', '가용예상재고'] + renamed_emp_cols + ['입력 총량', '수정량 입력✏️', '최종발주량']
    final_df = final_df[display_layout]

    # ==========================================
    # 6. 표 스크롤 완전 차단 (동적 높이 패치)
    # ==========================================
    calculated_height = (len(final_df) + 1) * 36 + 45
    
    # 🚀 오직 로그인한 '내 입력 컬럼'과 '수정량 입력✏️' 열만 쓰기 권한 부여, 나머지는 잠금(disabled)
    allowed_edit_cols = [my_edit_col, '수정량 입력✏️']
    disabled_list = [c for c in display_layout if c not in allowed_edit_cols]
    
    editable_config = st.data_editor(
        final_df,
        disabled=disabled_list,
        hide_index=True,
        use_container_width=True,
        height=int(calculated_height),
        column_config={
            my_edit_col: st.column_config.NumberColumn(f"{sel_emp}(박스✏️)", min_value=0.0, step=0.1, format="%.1f"),
            "수정량 입력✏️": st.column_config.NumberColumn("수정량 입력✏️", step=0.1, format="%.1f"),
            "입력 총량": st.column_config.NumberColumn("입력 총량", format="%.1f"),
            "최종발주량": st.column_config.NumberColumn("최종발주량", format="%.1f"),
            "현재고": st.column_config.NumberColumn("현재고", format="%.1f"),
            "주평균판매량": st.column_config.NumberColumn("주평균판매량", format="%.1f"),
            "선택차수 입고대기분": st.column_config.NumberColumn("선택차수 입고대기분", format="%.1f"),
            "가용예상재고": st.column_config.NumberColumn("가용예상재고", format="%.1f")
        }
    )

    # ==========================================
    # 7. 통합 동기화 저장 엔진
    # ==========================================
    st.markdown("<br>", unsafe_allow_html=True)
    if st.button("💾 내 발주량 및 수정량/진행 상태 통합 저장", use_container_width=True, type="primary"):
        with st.spinner("구글 시트에 실시간 덮어쓰기 정산 중..."):
            try:
                client = get_gspread_client()
                doc = client.open("통합재고관리")
                
                # ① Order_Status 갱신
                sheet_s = doc.worksheet("Order_Status")
                records_s = sheet_s.get_all_records()
                df_st_save = pd.DataFrame(records_s)
                
                if not df_st_save.empty:
                    df_st_save = df_st_save[~((df_st_save['제조사ID'].astype(str) == str(sel_m_id)) & (df_st_save['차수'].astype(str) == str(selected_round_val)))]
                today_str = datetime.datetime.now().strftime("%Y-%m-%d")
                new_status_row = pd.DataFrame([{"제조사ID": str(sel_m_id), "차수": str(selected_round_val), "상태": str(sel_status), "최종수정일": today_str}])
                df_st_save = pd.concat([df_st_save, new_status_row], ignore_index=True)
                
                sheet_s.clear()
                sheet_s.update([df_st_save.columns.values.tolist()] + df_st_save.astype(str).values.tolist())

                # ② Order_Records (내 발주량 + 시스템 수정량 병합 저장)
                sheet_o = doc.worksheet("Order_Records")
                records_o = sheet_o.get_all_records()
                df_ord_save = pd.DataFrame(records_o)
                
                if not df_ord_save.empty:
                    # 내 이름으로 기록된 행과 '수정량' 명의로 기록된 기존 수치를 정조준하여 삭제
                    df_ord_save = df_ord_save[~((df_ord_save['제조사ID'].astype(str) == str(sel_m_id)) & 
                                               (df_ord_save['차수'].astype(str) == str(selected_round_val)) & 
                                               (df_ord_save['직원명'].isin([str(sel_emp), '수정량'])))]
                
                # 내 입력값 추출
                my_rows = editable_config[editable_config[my_edit_col] > 0][['품목코드', my_edit_col]].copy()
                my_rows['제조사ID'] = str(sel_m_id)
                my_rows['차수'] = str(selected_round_val)
                my_rows['직원명'] = str(sel_emp)
                my_rows.rename(columns={my_edit_col: '발주량'}, inplace=True)
                my_rows = my_rows[['제조사ID', '차수', '품목코드', '직원명', '발주량']]
                
                # 수정량 입력값 추출
                adjust_rows = editable_config[editable_config['수정량 입력✏️'] != 0][['품목코드', '수정량 입력✏️']].copy()
                adjust_rows['제조사ID'] = str(sel_m_id)
                adjust_rows['차수'] = str(selected_round_val)
                adjust_rows['직원명'] = '수정량' # 피벗 시 '수정량' 열로 들어오도록 이름을 매칭 고정
                adjust_rows.rename(columns={'수정량 입력✏️': '발주량'}, inplace=True)
                adjust_rows = adjust_rows[['제조사ID', '차수', '품목코드', '직원명', '발주량']]
                
                # 최종 취합 후 업로드
                df_final_ord = pd.concat([df_ord_save, my_rows, adjust_rows], ignore_index=True)
                
                sheet_o.clear()
                if df_final_ord.empty:
                    sheet_o.append_row(['제조사ID', '차수', '품목코드', '직원명', '발주량'])
                else:
                    sheet_o.update([df_final_ord.columns.values.tolist()] + df_final_ord.astype(str).values.tolist())

                st.cache_data.clear()
                st.success(f"🎉 {selected_round_val}차 SCM 발주 계획안 및 수정 수량이 [{sel_status}] 상태로 완벽하게 동기화되었습니다!")
                st.rerun()
            except Exception as e:
                st.error(f"구글 분산 원장 기록 중 치명적 동기화 에러 발생: {e}")
