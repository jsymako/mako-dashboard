import streamlit as st
import pandas as pd
import datetime
from dateutil.relativedelta import relativedelta
import altair as alt

def run(load_data_func):
    st.title("쿠팡 재고 현황")
    
    try:
        with open("style.css", "r", encoding="utf-8") as f:
            st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)
    except FileNotFoundError:
        pass

    try:
        # 1. 데이터 로드 및 마스터 결합
        df_raw = load_data_func("coupang_stock")
        df_cp_master = load_data_func("coupang_item_data") 
        
        # 🚀 [신규 추가] 구글 시트에 추가된 컬럼이 없을 경우를 대비한 안전 장치
        if '이카운트품목코드' not in df_cp_master.columns: df_cp_master['이카운트품목코드'] = ''
        if '쿠팡판매단위' not in df_cp_master.columns: df_cp_master['쿠팡판매단위'] = 1

        df_cp_master = df_cp_master[['옵션ID', '안전재고량', '최대판매가', '최소판매가', '이카운트품목코드', '쿠팡판매단위']].copy()
        df_cp_master['옵션ID'] = df_cp_master['옵션ID'].astype(str).str.strip()
        df_cp_master['이카운트품목코드'] = df_cp_master['이카운트품목코드'].astype(str).str.strip()
        # 단위를 숫자로 변환 (입력이 안 되어있으면 기본값 1로 세팅하여 나누기 오류 방지)
        df_cp_master['쿠팡판매단위'] = pd.to_numeric(df_cp_master['쿠팡판매단위'], errors='coerce').fillna(1)
        
        # 🚀 [핵심 로직] 자사 출고 데이터를 이카운트 품목코드로 매칭 & 단위 환산
        try:
            df_trade = load_data_func("trade_record")
            df_trade.columns = ['일자', '거래처명', '품목코드', '품목명', '수량', '공급가액']
            df_trade['일자'] = pd.to_datetime(df_trade['일자'], errors='coerce')
            df_trade['수량'] = pd.to_numeric(df_trade['수량'].astype(str).str.replace(',', ''), errors='coerce').fillna(0)
            df_trade['품목코드'] = df_trade['품목코드'].astype(str).str.strip()
            
            # 쿠팡으로 나간 물량만 1차 추출
            df_trade_cp = df_trade[df_trade['거래처명'].astype(str).str.contains('쿠팡', na=False)].copy()
            
            # 💡 [정확한 매칭] 이카운트 품목코드를 기준으로 옵션ID와 쿠팡판매단위를 조인
            df_trade_cp = pd.merge(
                df_trade_cp, 
                df_cp_master[['이카운트품목코드', '옵션ID', '쿠팡판매단위']], 
                left_on='품목코드', 
                right_on='이카운트품목코드', 
                how='inner' # 매칭되는 것만 남김
            )
            
            # 💡 [단위 환산] 이카운트 출고 수량을 쿠팡 재고단위로 변환 (예: 5개 출고 / 단위5 = 쿠팡 1개 입고)
            df_trade_cp['환산수량'] = df_trade_cp['수량'] / df_trade_cp['쿠팡판매단위']
            
        except Exception as e:
            st.warning(f"출고 데이터 맵핑 오류 (이카운트품목코드를 확인하세요): {e}")
            df_trade_cp = pd.DataFrame(columns=['일자', '옵션ID', '환산수량'])
        
        df_raw.columns = ['일자', '옵션ID', '브랜드', '품목명', '쿠팡품목명', '재고', '판매가']
        df_raw['일자'] = pd.to_datetime(df_raw['일자'], errors='coerce')
        df_raw['재고'] = pd.to_numeric(df_raw['재고'].astype(str).str.replace(',', ''), errors='coerce').fillna(0)
        df_raw['판매가'] = pd.to_numeric(df_raw['판매가'].astype(str).str.replace(',', ''), errors='coerce').fillna(0)
        df_raw['옵션ID'] = df_raw['옵션ID'].astype(str).str.strip()
        df_raw = df_raw.dropna(subset=['일자'])
        
        for col in ['안전재고량', '최대판매가', '최소판매가']:
            df_cp_master[col] = pd.to_numeric(df_cp_master[col], errors='coerce').fillna(0)
            
        df = pd.merge(df_raw, df_cp_master[['옵션ID', '안전재고량', '최대판매가', '최소판매가']], on='옵션ID', how='left')
        df[['안전재고량', '최대판매가', '최소판매가']] = df[['안전재고량', '최대판매가', '최소판매가']].fillna(0)

        # 2. 사이드바 필터 설정
        brand_list = ["전체보기"] + sorted(list(df['브랜드'].dropna().unique()))
        selected_brand = st.sidebar.selectbox("브랜드 선택", brand_list)

        prod_df = df if selected_brand == "전체보기" else df[df['브랜드'] == selected_brand]
        product_list = ["전체보기"] + sorted(list(prod_df['품목명'].dropna().unique()))
        selected_product = st.sidebar.selectbox("품목 선택", product_list)

        view_target = st.sidebar.radio("조회 항목", ["재고량 추이", "판매가 변동", "판매량 조회", "모두 보기"], index=3)
        
        today = datetime.date.today()
        if "coupang_start_date" not in st.session_state: 
            st.session_state.coupang_start_date = today - relativedelta(months=1)
        
        start_date = st.sidebar.date_input("시작 일", key="coupang_start_date", format="YYYY/MM/DD")
        end_date = st.sidebar.date_input("종료 일", value=today, format="YYYY/MM/DD")
        
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
        c1.metric("운영 품목", f"{item_count} 종")
        c2.metric("현재 총 재고", f"{int(total_stock):,} 개")
        c3.metric("평균 판매가", f"{int(avg_price):,} 원")
        st.markdown("---")

        # ==========================================
        # 4. 메인 시각화 세팅
        # ==========================================
        common_axis = alt.Axis(labelFontSize=14, titleFontSize=16, labelAngle=0)
        
        x_min = display_df['일자'].min()
        x_max = display_df['일자'].max()
        padding_days = max(3, int((x_max - x_min).days * 0.25))
        x_max_padded = x_max + datetime.timedelta(days=padding_days)
        
        axis_options = {'format': '%m/%d', 'labelFontSize': 14}
        diff_days = (x_max_padded - x_min).days
        
        if 0 < diff_days <= 14:
            axis_options['tickCount'] = diff_days
            
        common_x = alt.X(
            '일자:T', 
            title='', 
            axis=alt.Axis(**axis_options), 
            scale=alt.Scale(domain=[x_min, x_max_padded])
        )

        label_idx = display_df.groupby('품목명')['일자'].idxmax()
        label_df = display_df.loc[label_idx]

        title_prefix = selected_product if selected_product != '전체보기' else (selected_brand if selected_brand != '전체보기' else '전체')

        # === 📈 4-1. 재고량 추이 ===
        if view_target in ["재고량 추이", "모두 보기"]:
            st.subheader(f"{title_prefix} 재고량 변동 흐름")
            stock_line = alt.Chart(display_df).mark_line(point=True).encode(
                x=common_x,
                y=alt.Y('재고:Q', title='재고 수량 (개)', axis=common_axis),
                color=alt.Color('품목명:N', legend=None),
                tooltip=['일자:T', '브랜드', '품목명', '재고']
            )
            stock_label = alt.Chart(label_df).mark_text(align='left', dx=8, fontSize=14, fontWeight='bold').encode(
                x=common_x, y='재고:Q', text='품목명:N', color='품목명:N'
            )
            st.altair_chart((stock_line + stock_label).properties(height=450), use_container_width=True)
            st.markdown("<br>", unsafe_allow_html=True)

        # === 💰 4-2. 판매가 변동 ===
        if view_target in ["판매가 변동", "모두 보기"]:
            st.subheader(f"{title_prefix} 판매가 변동 흐름")
            price_line = alt.Chart(display_df).mark_line(point=True).encode(
                x=common_x,
                y=alt.Y('판매가:Q', title='판매가 (원)', axis=common_axis, scale=alt.Scale(zero=False)),
                color=alt.Color('품목명:N', legend=None),
                tooltip=['일자:T', '브랜드', '품목명', '판매가']
            )
            price_label = alt.Chart(label_df).mark_text(align='left', dx=8, fontSize=14, fontWeight='bold').encode(
                x=common_x, y='판매가:Q', text='품목명:N', color='품목명:N'
            )
            st.altair_chart((price_line + price_label).properties(height=450), use_container_width=True)
            st.markdown("<br>", unsafe_allow_html=True)

        # === 📦 4-3. 판매량(실소진) 추정 차트 (🚀 정확한 옵션ID 기반 산출) ===
        if view_target in ["판매량 조회", "모두 보기"]:
            st.subheader(f"{title_prefix} 주간 실소진량 (판매량) 추이")
            
            calc_df = filtered_df.copy()
            calc_df['일자_dt'] = pd.to_datetime(calc_df['일자'])
            calc_df['주차_일요일'] = calc_df['일자_dt'] + pd.to_timedelta(6 - calc_df['일자_dt'].dt.dayofweek, unit='d')
            calc_df['주차_일요일'] = calc_df['주차_일요일'].dt.date

            # 기말재고 (고유한 옵션ID 기준으로 정확히 추적)
            weekly_stock = calc_df.sort_values('일자_dt').groupby(['옵션ID', '품목명', '주차_일요일']).tail(1)[['옵션ID', '품목명', '주차_일요일', '재고']]
            weekly_stock.rename(columns={'재고': '기말재고'}, inplace=True)

            # 기초재고
            weekly_stock = weekly_stock.sort_values(['옵션ID', '주차_일요일'])
            weekly_stock['기초재고'] = weekly_stock.groupby('옵션ID')['기말재고'].shift(1)

            # 쿠팡 단위로 환산된 출고 데이터 매핑
            if not df_trade_cp.empty:
                df_trade_cp['일자_dt'] = pd.to_datetime(df_trade_cp['일자'])
                df_trade_cp['주차_일요일'] = df_trade_cp['일자_dt'] + pd.to_timedelta(6 - df_trade_cp['일자_dt'].dt.dayofweek, unit='d')
                df_trade_cp['주차_일요일'] = df_trade_cp['주차_일요일'].dt.date
                
                valid_options = calc_df['옵션ID'].unique()
                t_df = df_trade_cp[df_trade_cp['옵션ID'].isin(valid_options)]
                
                # 💡 [핵심] '환산수량'을 더해줍니다
                weekly_inbound = t_df.groupby(['옵션ID', '주차_일요일'])['환산수량'].sum().reset_index()
                weekly_inbound.rename(columns={'환산수량': '주간입고량'}, inplace=True)
            else:
                weekly_inbound = pd.DataFrame(columns=['옵션ID', '주차_일요일', '주간입고량'])

            # 실소진 산출 공식
            weekly_sales = pd.merge(weekly_stock, weekly_inbound, on=['옵션ID', '주차_일요일'], how='left').fillna({'주간입고량': 0})
            weekly_sales = weekly_sales.dropna(subset=['기초재고']).copy() 
            
            weekly_sales['추정판매량'] = weekly_sales['기초재고'] + weekly_sales['주간입고량'] - weekly_sales['기말재고']
            weekly_sales['추정판매량'] = weekly_sales['추정판매량'].clip(lower=0)
            
            # 차트 표시를 위해 '품목명' 단위로 합산
            weekly_sales_grouped = weekly_sales.groupby(['품목명', '주차_일요일'])[['기초재고', '주간입고량', '기말재고', '추정판매량']].sum().reset_index()
            
            def make_week_label(d):
                start_d = d - datetime.timedelta(days=6)
                return f"{start_d.strftime('%m/%d')}~{d.strftime('%m/%d')}"
                
            weekly_sales_grouped['주차_라벨'] = pd.to_datetime(weekly_sales_grouped['주차_일요일']).dt.date.apply(make_week_label)
            
            mask_sales = (weekly_sales_grouped['주차_일요일'] >= start_date) & (weekly_sales_grouped['주차_일요일'] <= end_date + datetime.timedelta(days=6))
            display_sales_df = weekly_sales_grouped[mask_sales].copy()

            if display_sales_df.empty:
                st.info("💡 판매량을 산출하려면 최소 2주 이상의 연속된 데이터가 필요합니다. (조회 기간을 넓혀주세요)")
            else:
                sales_bar = alt.Chart(display_sales_df).mark_bar(size=35, cornerRadiusEnd=4).encode(
                    x=alt.X('주차_라벨:N', sort=list(display_sales_df['주차_라벨'].unique()), title='해당 주차 (월~일)', axis=alt.Axis(labelAngle=0, labelFontSize=12)),
                    y=alt.Y('추정판매량:Q', title='주간 소진량 (개)'),
                    color=alt.Color('품목명:N', legend=alt.Legend(title="품목명") if selected_product == "전체보기" else None),
                    tooltip=[
                        alt.Tooltip('주차_라벨:N', title='기간'),
                        alt.Tooltip('품목명:N', title='품목'),
                        alt.Tooltip('기초재고:Q', format=',.0f', title='시작 재고'),
                        alt.Tooltip('주간입고량:Q', format=',.1f', title='당주 입고(쿠팡단위)'),
                        alt.Tooltip('기말재고:Q', format=',.0f', title='남은 재고'),
                        alt.Tooltip('추정판매량:Q', format=',.0f', title='★추정 판매량')
                    ]
                ).properties(height=400)
                
                if selected_product != "전체보기":
                    sales_text = sales_bar.mark_text(align='center', baseline='bottom', dy=-5, fontSize=14, fontWeight='bold', color='#444').encode(
                        text=alt.Text('추정판매량:Q', format=',.0f')
                    )
                    st.altair_chart((sales_bar + sales_text), use_container_width=True)
                else:
                    st.altair_chart(sales_bar, use_container_width=True)

        # ==========================================
        # 5. 일자별 상세 모니터링 표
        # ==========================================
        st.markdown("---")
        st.subheader("일자별 모니터링 상세표")
        st.markdown("※ 🚨재고부족(빨강) | 🔺가격초과(녹색) | 🔻가격미달(파랑) | 🚨+🔺🔻복합(보라)")

        def format_stock_status(row):
            try:
                val = int(float(row['재고']))
                safe_val = int(float(row['안전재고량']))
            except:
                val, safe_val = 0, 0
                
            if val <= 0: return "품절 🚨"
            if safe_val > 0 and val < safe_val: return f"{val:,} 🚨"
            return f"{val:,}"

        def format_price_status(row):
            try:
                val = int(float(row['판매가']))
                max_val = int(float(row['최대판매가']))
                min_val = int(float(row['최소판매가']))
            except:
                val, max_val, min_val = 0, 0, 0
                
            if max_val > 0 and val > max_val: return f"{val:,} 🔺"
            elif min_val > 0 and val < min_val: return f"{val:,} 🔻"
            return f"{val:,}"

        show_df = display_df[['일자', '브랜드', '품목명', '재고', '안전재고량', '판매가', '최소판매가', '최대판매가']].copy()
        show_df['재고 현황'] = show_df.apply(format_stock_status, axis=1)
        show_df['판매가 현황'] = show_df.apply(format_price_status, axis=1)
        show_df['일자'] = show_df['일자'].dt.strftime('%m/%d')

        if view_target == "재고량 추이" or view_target == "판매량 조회":
            show_df['표시값'] = show_df['재고 현황']
        elif view_target == "판매가 변동":
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

        if view_target == "모두 보기":
            target_width = 140
        else:
            target_width = 90
            
        my_column_config = {}
        for col in date_cols:
            my_column_config[col] = st.column_config.Column(width=target_width)

        def color_danger_cells(val):
            if not isinstance(val, str): return ""
            has_stock_danger = "🚨" in val
            has_high_price = "🔺" in val
            has_low_price = "🔻" in val
            
            if has_stock_danger and (has_high_price or has_low_price): return "color: #9c27b0; font-weight: bold;" 
            if has_low_price: return "color: #007bff; font-weight: bold;"
            if has_high_price: return "color: #28a745; font-weight: bold;"
            if has_stock_danger: return "color: #ff4b4b; font-weight: bold;"
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
