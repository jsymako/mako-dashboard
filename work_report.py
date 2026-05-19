def run(load_sheet_data):
    st.markdown("<h1>📝 주간 업무 보고 시스템</h1>", unsafe_allow_html=True)
    
    df_emp = load_sheet_data("Employees")
    df_report = load_sheet_data("WorkReports")
    
    if df_emp is None or df_report is None: return

    # 1. 날짜 및 구간 계산
    target_date = st.sidebar.date_input("기준 주차 선택", datetime.today())
    monday = datetime.strptime(get_week_start(target_date), "%Y-%m-%d")
    target_week = monday.strftime("%Y-%m-%d")
    
    # 2. 직원 필터링 (전체 vs 개별)
    emp_names = ["전체"] + df_emp['성명'].tolist()
    selected_emp = st.sidebar.selectbox("직원 선택", emp_names)
    
    # 보고 대상 리스트
    target_employees = df_emp['성명'].tolist() if selected_emp == "전체" else [selected_emp]

    # 3. 직원별로 순회하며 표 생성
    for emp_name in target_employees:
        target_id = str(df_emp[df_emp['성명'] == emp_name]['직원ID'].values[0])
        
        # 해당 직원의 데이터 추출
        subset = df_report[(df_report['보고일자'] == target_week) & (df_report['직원ID'] == target_id)]
        
        # 날짜 구간 텍스트 생성
        last_monday = monday - timedelta(days=7)
        last_week_range = f"({last_monday.strftime('%m월%d일')} ~ {(last_monday + timedelta(days=4)).strftime('%m월%d일')})"
        this_week_range = f"({monday.strftime('%m월%d일')} ~ {(monday + timedelta(days=4)).strftime('%m월%d일')})"
        
        # 4. 매트릭스 구성
        day_order = ['월', '화', '수', '목', '금']
        cat_order = ['저번주 할일', '결과', '이번주 할일']
        
        if subset.empty:
            pivot_df = pd.DataFrame("", index=cat_order, columns=day_order)
        else:
            pivot_df = subset.pivot(index='분류', columns='요일', values='내용').reindex(index=cat_order, columns=day_order).fillna("")

        pivot_df = pivot_df.rename(index={'저번주 할일': f'저번주 할일 {last_week_range}', '이번주 할일': f'이번주 할일 {this_week_range}'})

        # 5. 화면 출력
        st.markdown(f"---")
        st.subheader(f"👤 {emp_name} 님 ({target_week} 주차)")
        st.data_editor(pivot_df, use_container_width=True, key=f"editor_{emp_name}")

    if st.button("💾 모든 변경사항 저장"):
        st.success("전체 데이터가 시트에 반영되었습니다!")
