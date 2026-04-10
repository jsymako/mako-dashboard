import streamlit as st
import pandas as pd
import datetime
from dateutil.relativedelta import relativedelta
import altair as alt
import holidays

def run(load_data_func):
    st.title("🤝 통합 거래처 및 판매 현황")
    
    try:
        with open("sales_trend.css", "r", encoding="utf-8") as f:
            st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)
    except FileNotFoundError:
        pass

    try:
        # ==========================================
        # 1. 데이터 로드 및 마스터 결합
        # ==========================================
        df_trade_raw = load_data_func("trade_record")
        df_item = load_data_func("ecount_item_data")
        
        df_trade_raw.columns = ['일자', '거래처명', '품목코드', '품목명', '수량', '공급가액']
        df_trade_raw['일자'] = pd.to_datetime(df_trade_raw['일자'], errors='coerce')
        df_trade_raw['수량'] = pd.to_numeric(df_trade_raw['수량'].astype(str).str.replace(',', ''), errors='coerce').fillna(0)
        df_trade_raw['공급가액'] = pd.to_numeric(df_trade_raw['공급가액'].astype(str).str.replace(',', ''), errors='coerce').fillna(0)
        df_trade_raw = df_trade_raw.dropna(subset=['일자'])
        
        box_col_name = df_item.columns[3] 
        df_item_master = df_item[['품목코드', '이름', '브랜드', box_col_name]].copy()
        df_item_master.rename(columns={'이름': '공식품목명', box_col_name: '박스입수'}, inplace=True)
        df_item_master['박스입수'] = pd.to_numeric(df_item_master['박스입수'], errors='coerce').fillna(1)
        
        df_trade = pd.merge(df_trade_raw, df_item_master, on='품목코드', how='left')
        
        df_trade['브랜드'] = df_trade['브랜드'].fillna('기타(미지정)')
        df_trade['공식품목명'] = df_trade['공식품목명'].fillna(df_trade['품목명'])
        df_trade['박스입수'] = df_trade['박스입수'].fillna(1)
        df_trade['환산수량'] = df_trade['수량'] / df_trade['박스입수']
        
        df_trade['월_dt'] = df_trade['일자'].dt.to_period('M').dt.to_timestamp()
        df_trade['월'] = df_trade['일자'].dt.strftime('%Y년 %m월')

        # ==========================================
        # 2. 사이드바 필터 (거래처 -> 브랜드 -> 품목 순차적 다중 선택)
        # ==========================================
        trader_list = sorted(list(df_trade['거래처명'].dropna().unique()))
        selected_traders = st.sidebar.multiselect(
            "거래처 선택", 
            options=trader_list,
            default=[],
            placeholder="비워두면 전사 판매 현황 조회"
        )
        
        temp_df = df_trade if not selected_traders else df_trade[df_trade['거래처명'].isin(selected_traders)]
        
        brand_list = sorted(list(temp_df['브랜드'].dropna().unique()))
        selected_brands = st.sidebar.multiselect(
            "브랜드 선택", 
            options=brand_list,
            default=[],
            placeholder="비워두면 전체 브랜드 조회"
        )

        temp_prod_df = temp_df if not selected_brands else temp_df[temp_df['브랜드'].isin(selected_brands)]
        prod_list = sorted(list(temp_prod_df['공식품목명'].dropna().unique()))
        selected_products = st.sidebar.multiselect(
            "품목 선택", 
            options=prod_list,
            default=[],
            placeholder="비워두면 전체 품목 조회"
        )

        view_mode = st.sidebar.radio("분석 모드", ["월별 현황", "일별 현황", "수요 예측"], index=0)

        # 공통 필터 적용
        filtered_df = df_trade.copy()
        if selected_traders:
            filtered_df = filtered_df[filtered_df['거래처명'].isin(selected_traders)]
        if selected_brands:
            filtered_df = filtered_df[filtered_df['브랜드'].isin(selected_brands)]
        if selected_products:
            filtered_df = filtered_df[filtered_df['공식품목명'].isin(selected_products)]

        group_field = '브랜드' if not selected_brands and not selected_products else '공식품목명'

        # ==========================================
        # 3. 모드별 날짜 세팅 및 필터링
        # ==========================================
        today = datetime.date.today()
        
        if view_mode == "일별 현황":
            if "trade_start_date" not in st.session_state: 
                st.session_state.trade_start_date = today - relativedelta(months=1)
            
            start_date = st.sidebar.date_input("시작 일", key="trade_start_date", format="YYYY/MM/DD")
            end_date = st.sidebar.date_input("종료 일", value=today, format="YYYY/MM/DD")
            
            mask = (filtered_df['일자'].dt.date >= start_date) & (filtered_df['일자'].dt.date <= end_date)
            display_df = filtered_df.loc[mask].copy()
            
            date_range_str = f"{start_date.strftime('%Y년 %m월 %d일')} ~ {end_date.strftime('%Y년 %m월 %d일')}"
            diff_val = (end_date - start_date).days + 1
            avg_label = "💸 일평균 거래액"

        elif view_mode == "월별 현황":
            month_list = sorted(list(df_trade['월'].unique()))
            if not month_list:
                st.warning("데이터가 없습니다.")
                return
                
            start_month = st.sidebar.selectbox("시작 월", month_list, index=max(0, len(month_list)-6))
            end_month = st.sidebar.selectbox("종료 월", month_list, index=len(month_list)-1)
            
            display_df = filtered_df[(filtered_df['월'] >= start_month) & (filtered_df['월'] <= end_month)]
            
            date_range_str = f"{start_month} ~ {end_month}"
            d1, d2 = pd.to_datetime(start_month, format='%Y년 %m월'), pd.to_datetime(end_month, format='%Y년 %m월')
            diff_val = (d2.year - d1.year) * 12 + (d2.month - d1.month) + 1
            avg_label = "💸 월평균 거래액"
            
        else: # 수요 예측 모드 
            display_df = filtered_df.copy()
            diff_val = 0
            date_range_str = ""

        if display_df.empty:
            st.warning("선택하신 조건에 데이터가 없습니다.")
            return

        # ==========================================
        # 4. KPI 상단 바
        # ==========================================
        total_amt = display_df['공급가액'].sum()
        total_qty = display_df['수량'].sum()
        total_amt_man = total_amt / 10000
        
        c1, c2, c3, c4 = st.columns(4)
        
        if view_mode == "수요 예측":
            c1.metric("📊 기준", "최근 12개월")
            c2.metric("💰 총 거래액", f"{int(total_amt_man):,}만 원", f"실제: {int(total_amt):,} 원", delta_color="off")
            
            disp_tag = "전체 항목"
            if selected_products: disp_tag = f"{len(selected_products)}개 품목"
            elif selected_brands: disp_tag = f"{len(selected_brands)}개 브랜드"
            elif selected_traders: disp_tag = f"{len(selected_traders)}개 거래처"
            
            c3.metric("🏷️ 기준 대상", disp_tag)
            c4.metric("📦 총 출고수량", f"{int(total_qty):,} 개")
        else:
            avg_amt = total_amt / diff_val if diff_val > 0 else 0
            avg_amt_man = avg_amt / 10000
            
            c1.metric("📅 분석 기간", f"{diff_val}{'일' if view_mode=='일별 현황' else '개월'}", date_range_str, delta_color="off")
            c2.metric("💰 총 거래액", f"{int(total_amt_man):,}만 원", f"실제: {int(total_amt):,} 원", delta_color="off")
            c3.metric(avg_label, f"{int(avg_amt_man):,}만 원", f"실제: {int(avg_amt):,} 원", delta_color="off")
            c4.metric("📦 총 출고수량", f"{int(total_qty):,} 개")
            
        st.markdown("---")

        # ==========================================
        # 5. 메인 시각화 분기 (현황 분석 vs 수요 예측)
        # ==========================================
        if view_mode in ["월별 현황", "일별 현황"]:
            common_axis = alt.Axis(labelFontSize=14, titleFontSize=16, labelAngle=0)
            grp = '월' if view_mode == "월별 현황" else '일자'
            
            trader_title = "전체 거래처" if not selected_traders else ", ".join(selected_traders)
            st.subheader(f"📉 {trader_title} 거래액 추이")
            
            color_encoding = alt.Color('거래처명:N', legend=alt.Legend(title="거래처")) if selected_traders else alt.value("#2E86C1")
            
            if selected_traders:
                trend = display_df.groupby([grp, '거래처명'])['공급가액'].sum().reset_index()
            else:
                trend = display_df.groupby([grp])['공급가액'].sum().reset_index()
                trend['거래처명'] = '전체'

            if view_mode == "일별 현황":
                x_min, x_max = display_df['일자'].min(), display_df['일자'].max()
                diff_days = (x_max - x_min).days
                axis_options = {'format': '%m/%d', 'labelFontSize': 14}
                if 0 < diff_days <= 14: axis_options['tickCount'] = diff_days
                common_x = alt.X('일자:T', title='', axis=alt.Axis(**axis_options))
                
                line_chart = alt.Chart(trend).mark_line(point=True).encode(
                    x=common_x, y=alt.Y('공급가액:Q', title='금액(원)'), color=color_encoding, tooltip=[grp, '거래처명', '공급가액']
                ).properties(height=350)
                st.altair_chart(line_chart, use_container_width=True)
            else:
                line_chart = alt.Chart(trend).mark_line(point=True).encode(
                    x=alt.X(f'{grp}:N', title='', axis=alt.Axis(labelAngle=0, labelFontSize=14)), 
                    y=alt.Y('공급가액:Q', title='금액(원)'), color=color_encoding, tooltip=[grp, '거래처명', '공급가액']
                ).properties(height=350)
                st.altair_chart(line_chart, use_container_width=True)

            # ------------------------------------------
            # 관점 전환 교차 랭킹 차트
            # ------------------------------------------
            st.markdown("---")
            
            rank_mode = st.radio("그래프 기준", ["품목", "거래처"], horizontal=True)
            
            if "품목" in rank_mode:
                rank_field = group_field 
                
                if selected_products: display_name = ", ".join(selected_products)
                elif selected_brands: display_name = ", ".join(selected_brands)
                else: display_name = "전체 브랜드"
                    
                st.subheader(f"📊 {trader_title} 내 [{display_name}] 매출 순위 (TOP 15)")
            else:
                rank_field = '거래처명'
                if selected_products: brand_title = f"선택 품목({len(selected_products)}개)"
                elif selected_brands: brand_title = ", ".join(selected_brands)
                else: brand_title = "전체 품목"
                    
                st.subheader(f"📊 [{brand_title}] 매출 견인 거래처 순위 (TOP 15)")
                
            sum_df = display_df.groupby([rank_field])[['공급가액', '환산수량']].sum().reset_index()
            sum_df = sum_df.sort_values(by='공급가액', ascending=False).head(15) 
            
            y_ax = alt.Axis(labelLimit=500, labelFontSize=14, title='', labelPadding=10)
            chart_h = max(300, len(sum_df) * 45)

            rank_chart = alt.Chart(sum_df).mark_bar(
                size=25,            
                cornerRadius=5,     
                color="#2E86C1",    
                opacity=0.9
            ).encode(
                x=alt.X('공급가액:Q', title='총 거래액 (원)'), 
                y=alt.Y(f'{rank_field}:N', sort='-x', axis=y_ax),
                tooltip=[rank_field, alt.Tooltip('공급가액', format=','), alt.Tooltip('환산수량', format=',.1f', title='수량(박스)')]
            )
            
            text_label = rank_chart.mark_text(
                align='left', dx=5, fontSize=13, fontWeight='bold', color='#555'
            ).encode(text=alt.Text('공급가액:Q', format=','))

            st.altair_chart((rank_chart + text_label).properties(height=chart_h), use_container_width=True)

        # ==========================================
        # 🚀 6. 향후 12개월 수요 예측
        # ==========================================
        elif view_mode == "수요 예측":
            st.subheader("향후 12개월 수요 (출고) 예측 분석")
            m_data = filtered_df.groupby('월_dt')['수량'].sum().reset_index().set_index('월_dt').asfreq('MS').fillna(0)
            
            if len(m_data) < 12:
                st.warning("예측 모델을 구동하려면 최소 12개월 이상의 과거 거래 데이터가 필요합니다.")
            else:
                # 🚀 [추가됨] 예측 알고리즘 안내 박스 (시각적 피드백)
                with st.expander("💡 수요 예측 알고리즘 안내 (클릭하여 펼치기)", expanded=False):
                    st.markdown("""
                        <div style="background-color: #fcf8ff; border-left: 4px solid #8E44AD; padding: 15px 20px; border-radius: 5px; margin-bottom: 25px;">
                            <h4 style="margin-top: 0; color: #2c3e50; font-size: 1.1rem; margin-bottom: 10px;">💡 수요 예측 알고리즘 안내</h4>
                            <ul style="margin-bottom: 0; color: #444; font-size: 1.0rem; line-height: 1.7; padding-left: 20px;">
                                <li><b>기초 체력 (60% 반영):</b> 과거 12개월 평균 판매량 <span style="color:#777; font-size:0.9rem;">(장기적인 판매 규모의 안정성)</span></li>
                                <li><b>최신 트렌드 (40% 반영):</b> 최근 3개월 평균 판매량 <span style="color:#777; font-size:0.9rem;">(가장 최근의 시장 상승/하락 추세)</span></li>
                                <li><b>계절성 지수:</b> 과거 판매 패턴 기준의 월별 고유 가중치 <span style="color:#777; font-size:0.9rem;">(예: 성수기/비수기 변동폭)</span></li>
                                <li style="list-style: none; margin-top: 10px; margin-left: -20px; color: #8E44AD; font-weight: bold; font-size: 1.05rem;">
                                    👉 예상 발주량 = (기초 체력 + 최신 트렌드) × 월별 계절성 지수
                                </li>
                            </ul>
                        </div>
                    """, unsafe_allow_html=True)

                if selected_products and len(selected_products) == 1:
                    b_unit = filtered_df['박스입수'].iloc[0] 
                else:
                    b_unit = filtered_df['박스입수'].mean()

                # 예측 알고리즘 로직 수행
                base_12m = m_data['수량'].tail(12).mean()
                base_3m = m_data['수량'].tail(3).mean()
                blended_avg = (base_12m * 0.6) + (base_3m * 0.4)

                seasonal_idx = filtered_df.groupby(filtered_df['일자'].dt.month)['수량'].sum() / (filtered_df.groupby(filtered_df['일자'].dt.month)['수량'].sum().mean())
                
                cur_start = datetime.datetime.now().replace(day=1)
                
                f_res = []
                for i in range(1, 13):
                    t_date = cur_start + relativedelta(months=i)
                    f_res.append({'월_dt': t_date, '예측수량': blended_avg * seasonal_idx.get(t_date.month, 1.0)})
                f_df = pd.DataFrame(f_res)

                # 그래프 오버랩 처리
                past_df = m_data.tail(12).reset_index().rename(columns={'수량':'값','월_dt':'날'})
                past_df['순서'] = range(1, 13)
                past_df['공통월_라벨'] = past_df['날'].dt.strftime('%m월')
                past_df['구분'] = '과거 실적 (작년 동기)'
                
                future_df = f_df.rename(columns={'예측수량':'값','월_dt':'날'})
                future_df['순서'] = range(1, 13)
                future_df['공통월_라벨'] = future_df['날'].dt.strftime('%m월')
                future_df['구분'] = '향후 예측 (내년 동기)'
                
                comb = pd.concat([past_df, future_df])
                comb['박스환산'] = comb['값'] / b_unit
                
                forecast_chart = alt.Chart(comb).mark_line(point=True, size=3).encode(
                    x=alt.X('공통월_라벨:N', sort=alt.EncodingSortField(field='순서', order='ascending'), title='비교 월 (Month)', axis=alt.Axis(labelAngle=0, labelFontSize=14)), 
                    y=alt.Y('박스환산:Q', title='수량 (박스)'),
                    color=alt.Color('구분:N', scale=alt.Scale(domain=['과거 실적 (작년 동기)', '향후 예측 (내년 동기)'], range=['#95A5A6', '#8E44AD'])),
                    strokeDash=alt.StrokeDash('구분:N', scale=alt.Scale(domain=['과거 실적 (작년 동기)', '향후 예측 (내년 동기)'], range=[[1,0], [5,5]]), legend=alt.Legend(title="비교 그룹", orient="top-left")),
                    tooltip=[
                        alt.Tooltip('구분:N', title='구분'),
                        alt.Tooltip('날:T', format='%Y년 %m월', title='실제 연/월'), 
                        alt.Tooltip('박스환산:Q', format=',.1f', title='수량 (박스)'), 
                        alt.Tooltip('값:Q', format=',.0f', title='수량 (낱개)')
                    ]
                ).properties(height=350)
                
                st.altair_chart(forecast_chart, use_container_width=True)

                st.markdown("### 📋 향후 12개월 예상 수요 (발주 추천량) 상세표")
                
                f_df['예상 박스'] = f_df['예측수량'] / b_unit
                disp_df = f_df.copy()
                disp_df['예측 월'] = disp_df['월_dt'].dt.strftime('%Y년 %m월')
                disp_df = disp_df[['예측 월', '예상 박스', '예측수량']]
                disp_df.rename(columns={'예측수량': '낱개 수량 (개)'}, inplace=True)

                html_table = disp_df.style.format({
                    '예상 박스': '{:,.1f} 박스',
                    '낱개 수량 (개)': '{:,.0f} 개'
                }).hide(axis="index") \
                  .set_table_attributes('style="width:100%; font-size:1.2rem; text-align:center; border-collapse:collapse; background-color:white; box-shadow: 0 2px 8px rgba(0,0,0,0.05);"') \
                  .set_table_styles([
                      {'selector': 'th', 'props': [('background-color', '#f4f6f8'), ('color', '#333'), ('padding', '14px'), ('border-bottom', '2px solid #ddd'), ('text-align', 'center'), ('font-size', '1.25rem')]},
                      {'selector': 'td', 'props': [('padding', '14px'), ('border-bottom', '1px solid #eee'), ('color', '#111'), ('font-size', '1.2rem'), ('text-align', 'center')]}
                  ]).to_html()
                
                st.markdown(html_table, unsafe_allow_html=True)
                st.markdown("<br>", unsafe_allow_html=True)
                
                total_f = f_df['예측수량'].sum()
                total_box_str = f"{total_f/b_unit:.1f} 박스" if b_unit > 1 else f"{int(total_f):,} 개"
                st.success(f"✅ 향후 12개월 총 예상 출고(필요)량: 약 **{total_box_str}** ({int(total_f):,} 개)")

    except Exception as e:
        st.error(f"오류 발생: {e}")
