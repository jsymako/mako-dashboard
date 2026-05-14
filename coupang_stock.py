import streamlit as st
import pandas as pd
import datetime
from dateutil.relativedelta import relativedelta
import altair as alt

def run(load_data_func):
    st.title("🚀 쿠팡 재고 판매가 현황")
    
    try:
        with open("coupang_stock.css", "r", encoding="utf-8") as f:
            st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)
    except FileNotFoundError:
        pass

    
    
    try:
        # 1. 데이터 로드 및 마스터 결합
        df_raw = load_data_func("coupang_stock")
        df_cp_master = load_data_func("coupang_item_data") 
        
        df_raw.columns = ['일자', '옵션ID', '브랜드', '품목명', '쿠팡품목명', '재고', '판매가']
        df_raw['일자'] = pd.to_datetime(df_raw['일자'], errors='coerce')
        df_raw['재고'] = pd.to_numeric(df_raw['재고'].astype(str).str.replace(',', ''), errors='coerce').fillna(0)
        df_raw['판매가'] = pd.to_numeric(df_raw['판매가'].astype(str).str.replace(',', ''), errors='coerce').fillna(0)
        df_raw['옵션ID'] = df_raw['옵션ID'].astype(str).str.strip()
        df_raw = df_raw.dropna(subset=['일자'])
        
        df_cp_master = df_cp_master[['옵션ID', '안전재고량', '최대판매가', '최소판매가']].copy()
        df_cp_master['옵션ID'] = df_cp_master['옵션ID'].astype(str).str.strip()
        
        for col in ['안전재고량', '최대판매가', '최소판매가']:
            df_cp_master[col] = pd.to_numeric(df_cp_master[col].astype(str).str.replace(',', ''), errors='coerce').fillna(0)
            
        df = pd.merge(df_raw, df_cp_master, on='옵션ID', how='left')
        df[['안전재고량', '최대판매가', '최소판매가']] = df[['안전재고량', '최대판매가', '최소판매가']].fillna(0)

        # 2. 사이드바 필터 설정
        brand_list = ["전체보기"] + sorted(list(df['브랜드'].dropna().unique()))
        selected_brand = st.sidebar.selectbox("브랜드 선택", brand_list)

        # 🚀 [추가] 브랜드에 종속되는 품목 선택 기능
        prod_df = df if selected_brand == "전체보기" else df[df['브랜드'] == selected_brand]
        product_list = ["전체보기"] + sorted(list(prod_df['품목명'].dropna().unique()))
        selected_product = st.sidebar.selectbox("품목 선택", product_list)



        view_target = st.sidebar.radio("조회 항목", ["📦 재고량 추이", "💰 판매가 변동", "📊 모두 보기"], index=2)
        
        today = datetime.date.today()
        if "coupang_start_date" not in st.session_state: 
            # 🚀 [수정] 기본값을 14일 전에서 1개월 전으로 변경
            st.session_state.coupang_start_date = today - relativedelta(months=1)
        
        start_date = st.sidebar.date_input("시작 일", key="coupang_start_date", format="YYYY/MM/DD")
        end_date = st.sidebar.date_input("종료 일", value=today, format="YYYY/MM/DD")
        
        # 🚀 [추가] 품목 선택 필터 적용
        filtered_df = df.copy()
        if selected_brand != "전체보기":
            filtered_df = filtered_df[filtered_df['브랜드'] == selected_brand]
        if selected_product != "전체보기":
            filtered_df = filtered_df[filtered_df['품목명'] == selected_product]
            
        mask = (filtered_df['일자'].dt.date >= start_date) & (filtered_df['일자'].dt.date <= end_date)
        display_df = filtered_df.loc[mask].copy()

        if display_df.empty:
            st.warning("선택하신 조건에 데이터가 없습니다.")
            return

        # 3. 상단 요약 KPI
        latest_date = display_df['일자'].max()
        latest_df = display_df[display_df['일자'] == latest_date]
        
        total_stock = latest_df['재고'].sum()
        avg_price = latest_df['판매가'].mean() if not latest_df.empty else 0
        item_count = len(latest_df['품목명'].unique())
        
        c1, c2, c3 = st.columns(3)
        c1.metric("🛒 운영 품목", f"{item_count} 종")
        c2.metric("📦 현재 총 재고", f"{int(total_stock):,} 개")
        c3.metric("💸 평균 판매가", f"{int(avg_price):,} 원")
        st.markdown("---")

        # ==========================================
        # 4. 메인 시각화 (🚀 직접 라벨링 방식 적용)
        # ==========================================
        common_axis = alt.Axis(labelFontSize=14, titleFontSize=16, labelAngle=0)
        
        x_min = display_df['일자'].min()
        x_max = display_df['일자'].max()
        padding_days = max(3, int((x_max - x_min).days * 0.25))
        x_max_padded = x_max + datetime.timedelta(days=padding_days)
        
        # ==========================================
        # 4. 메인 시각화 (🚀 직접 라벨링 방식 적용)
        # ==========================================
        common_axis = alt.Axis(labelFontSize=14, titleFontSize=16, labelAngle=0)
        
        x_min = display_df['일자'].min()
        x_max = display_df['일자'].max()
        padding_days = max(3, int((x_max - x_min).days * 0.25))
        x_max_padded = x_max + datetime.timedelta(days=padding_days)
        
        # 🚀 [수정] X축 눈금(Tick) 옵션을 동적으로 생성합니다.
        axis_options = {'format': '%m/%d', 'labelFontSize': 14}
        diff_days = (x_max_padded - x_min).days
        
        # 날짜 간격이 14일 이하로 짧을 때만 tickCount 옵션을 추가 (하루에 하나씩!)
        if 0 < diff_days <= 14:
            axis_options['tickCount'] = diff_days
            
        common_x = alt.X(
            '일자:T', 
            title='', 
            axis=alt.Axis(**axis_options), # 🌟 None 에러 없이 딕셔너리 풀기로 안전하게 적용
            scale=alt.Scale(domain=[x_min, x_max_padded])
        )

        label_idx = display_df.groupby('품목명')['일자'].idxmax()
        label_df = display_df.loc[label_idx]

        # 차트 제목에 품목명도 함께 표시되도록 디테일 추가
        title_prefix = selected_product if selected_product != '전체보기' else (selected_brand if selected_brand != '전체보기' else '전체')

        if view_target in ["📦 재고량 추이", "📊 모두 보기"]:
            st.subheader(f"📦 {title_prefix} 재고량 변동 흐름")
            
            stock_line = alt.Chart(display_df).mark_line(point=True).encode(
                x=common_x,
                y=alt.Y('재고:Q', title='재고 수량 (개)', axis=common_axis),
                color=alt.Color('품목명:N', legend=None),
                tooltip=['일자:T', '브랜드', '품목명', '재고']
            )
            
            stock_label = alt.Chart(label_df).mark_text(align='left', dx=8, fontSize=14, fontWeight='bold').encode(
                x=common_x,
                y='재고:Q',
                text='품목명:N',
                color='품목명:N'
            )
            
            st.altair_chart((stock_line + stock_label).properties(height=450), use_container_width=True)

        st.markdown("<br>", unsafe_allow_html=True)

        if view_target in ["💰 판매가 변동", "📊 모두 보기"]:
            st.subheader(f"💰 {title_prefix} 판매가 변동 흐름")
            
            price_line = alt.Chart(display_df).mark_line(point=True).encode(
                x=common_x,
                y=alt.Y('판매가:Q', title='판매가 (원)', axis=common_axis, scale=alt.Scale(zero=False)),
                color=alt.Color('품목명:N', legend=None),
                tooltip=['일자:T', '브랜드', '품목명', '판매가']
            )
            
            price_label = alt.Chart(label_df).mark_text(align='left', dx=8, fontSize=14, fontWeight='bold').encode(
                x=common_x,
                y='판매가:Q',
                text='품목명:N',
                color='품목명:N'
            )
            
            st.altair_chart((price_line + price_label).properties(height=450), use_container_width=True)

        # 5. 일자별 상세 모니터링 표
        # 5. 일자별 상세 모니터링 표
        st.markdown("---")
        st.subheader("🚨 일자별 안전재고 및 가격 모니터링")
        st.markdown("※ 범례: 🚨재고부족(빨강) | 🔺가격초과(녹색) | 🔻가격미달(파랑) | 🚨+🔺🔻복합(보라)")

        # 🚀 1. 재고/판매가 데이터 안전 변환 및 아이콘 무조건 부착
        def format_stock_status(row):
            try:
                val = int(float(row['재고']))
                safe_val = int(float(row['안전재고량']))
            except:
                val, safe_val = 0, 0
                
            if val <= 0:
                return "품절 🚨"
            if safe_val > 0 and val < safe_val: 
                return f"{val:,} 🚨"
            return f"{val:,}"

        def format_price_status(row):
            try:
                val = int(float(row['판매가']))
                max_val = int(float(row['최대판매가']))
                min_val = int(float(row['최소판매가']))
            except:
                val, max_val, min_val = 0, 0, 0
                
            if max_val > 0 and val > max_val: 
                return f"{val:,} 🔺"
            elif min_val > 0 and val < min_val: 
                return f"{val:,} 🔻"
            return f"{val:,}"

        show_df = display_df[['일자', '브랜드', '품목명', '재고', '안전재고량', '판매가', '최소판매가', '최대판매가']].copy()
        
        show_df['재고 현황'] = show_df.apply(format_stock_status, axis=1)
        show_df['판매가 현황'] = show_df.apply(format_price_status, axis=1)
        show_df['일자'] = show_df['일자'].dt.strftime('%m/%d')

        # 🚀 2. 조회 항목별 데이터 매핑
        if view_target == "📦 재고량 추이":
            show_df['표시값'] = show_df['재고 현황']
        elif view_target == "💰 판매가 변동":
            show_df['표시값'] = show_df['판매가 현황']
        else:
            show_df['표시값'] = show_df['재고 현황'] + " | " + show_df['판매가 현황']

        show_df['안전재고'] = show_df['안전재고량'].apply(lambda x: f"{int(float(x)):,}" if pd.notna(x) else "0")
        show_df['최소판매가'] = show_df['최소판매가'].apply(lambda x: f"{int(float(x)):,}" if pd.notna(x) else "0")
        show_df['최대판매가'] = show_df['최대판매가'].apply(lambda x: f"{int(float(x)):,}" if pd.notna(x) else "0")

        pivot_df = show_df.pivot_table(
            index=['브랜드', '품목명', '안전재고', '최소판매가', '최대판매가'],
            columns='일자',
            values='표시값',
            aggfunc=lambda x: ' '.join(x)
        ).reset_index()

        date_cols = sorted([col for col in pivot_df.columns if col not in ['브랜드', '품목명', '안전재고', '최소판매가', '최대판매가']], reverse=True)
        final_cols = ['브랜드', '품목명', '안전재고', '최소판매가', '최대판매가'] + date_cols
        pivot_df = pivot_df[final_cols].fillna("-")

        if view_target == "📊 모두 보기":
            target_width = 140  # '재고 | 판매가'가 다 보이도록 넉넉하게 설정
        else:
            target_width = 90   # 단일 항목일 때는 90으로 콤팩트하게 유지
            
        my_column_config = {}
        for col in date_cols:
            my_column_config[col] = st.column_config.Column(width=target_width)

        # 🚀 3. 대표님이 요청하신 직관적인 색상 룰 적용
        def color_danger_cells(val):
            if not isinstance(val, str):
                return ""
                
            has_stock_danger = "🚨" in val
            has_high_price = "🔺" in val
            has_low_price = "🔻" in val
            
            # ① 복합 문제 (재고부족 + 가격이상) -> 보라색
            if has_stock_danger and (has_high_price or has_low_price):
                return "color: #9c27b0; font-weight: bold;" 
                
            # ② 단일 문제: 가격 미달 -> 파란색
            if has_low_price:
                return "color: #007bff; font-weight: bold;"
                
            # ③ 단일 문제: 가격 초과 -> 녹색
            if has_high_price:
                return "color: #28a745; font-weight: bold;"
                
            # ④ 단일 문제: 재고 부족 -> 빨간색
            if has_stock_danger:
                return "color: #ff4b4b; font-weight: bold;"
                
            return ""

        st.dataframe(
            pivot_df.style.map(color_danger_cells), 
            width="stretch", 
            height=750, 
            hide_index=True,
            column_config=my_column_config
        )

    except Exception as e:
        st.error(f"오류 발생: {e}")
