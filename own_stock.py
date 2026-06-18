import streamlit as st
import pandas as pd
import numpy as np
import datetime
from dateutil.relativedelta import relativedelta
import os
from utils import custom_fullscreen_spinner

def run(load_data_func):
    st.title("자사 재고 현황")
    
    # 🚀 짝꿍 CSS 파일 불러오기
    try:
        with open("style.css", "r", encoding="utf-8") as f:
            st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)
    except FileNotFoundError:
        pass

    try:
        with custom_fullscreen_spinner("재고 데이터 로딩 중..."):
            # 1. 데이터 로드
            df_own = load_data_func("ecount_stock")
            df_sales = load_data_func("sales_record")
            df_item = load_data_func("ecount_item_data")
            
            # 업데이트 시간 추출
            update_time = df_own['업데이트 시간'].iloc[0] if '업데이트 시간' in df_own.columns and not df_own.empty else '정보 없음'
    
            # 2. 데이터 전처리
            df_own['현재재고'] = pd.to_numeric(df_own['현재재고'], errors='coerce').fillna(0)
            df_sales['수량'] = df_sales['수량'].astype(str).str.replace(',', '')
            df_sales['수량'] = pd.to_numeric(df_sales['수량'], errors='coerce').fillna(0)
            df_sales['일자'] = pd.to_datetime(df_sales['일자'], errors='coerce', yearfirst=True)
    
            # 박스입수 및 과다기준주 추출
            box_col_name = df_item.columns[3] 
            df_item_box = df_item[['품목코드', box_col_name]].copy()
            df_item_box.rename(columns={box_col_name: '박스입수'}, inplace=True)
            df_item_box['박스입수'] = pd.to_numeric(df_item_box['박스입수'], errors='coerce').fillna(1)
    
            excess_col_name = df_item.columns[4]
            df_item_limit = df_item[['품목코드', excess_col_name]].copy()
            df_item_limit.rename(columns={excess_col_name: '과다기준주'}, inplace=True)
            df_item_limit['과다기준주'] = pd.to_numeric(df_item_limit['과다기준주'], errors='coerce')
    
            # 3. 사이드바 필터
            brand_list = ["전체보기"] + sorted(list(df_own['브랜드'].unique()))
            selected_brand = st.sidebar.selectbox("브랜드 필터", brand_list, key="own_brand_filter")
            
            status_list = ["전체보기", "부족", "품절", "과다", "적정"]
            selected_status = st.sidebar.selectbox("상태 필터", status_list, key="own_status_filter")
    
            months_to_look_back = st.sidebar.slider("판매 산출 기준 (개월)", 1, 12, 3, key="own_month_slider_v2")
            
            # 🚀 [추가] 한번에보기 체크박스 추가 (기본값: False)
            view_all_toggle = st.sidebar.checkbox("브랜드 구분 해제", value=False, key="own_view_all_toggle")
    
            # 4. 날짜 계산 및 판매량 합산
            today = datetime.datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
            end_date = today.replace(day=1) - datetime.timedelta(days=1)
            start_date = (end_date - relativedelta(months=months_to_look_back - 1)).replace(day=1)
            
            recent_sales = df_sales[(df_sales['일자'] >= pd.Timestamp(start_date)) & (df_sales['일자'] <= pd.Timestamp(end_date))]
            total_sales_by_item = recent_sales.groupby('품목코드')['수량'].sum().reset_index()
            total_sales_by_item.rename(columns={'수량': '기간내_총판매량'}, inplace=True)
            
            total_sales_by_item['주평균판매량'] = ((total_sales_by_item['기간내_총판매량'] / months_to_look_back) / 4).round(1).clip(lower=0)
            
            # 5. 데이터 병합 및 최종 환산
            df_merged = pd.merge(df_own, total_sales_by_item[['품목코드', '주평균판매량']], on='품목코드', how='left').fillna(0)
            df_merged = pd.merge(df_merged, df_item_limit, on='품목코드', how='left')
            df_merged = pd.merge(df_merged, df_item_box, on='품목코드', how='left')
            
            df_merged['현재재고'] = pd.to_numeric(df_merged['현재재고'], errors='coerce').fillna(0).clip(lower=0)
            df_merged['주평균판매량'] = pd.to_numeric(df_merged['주평균판매량'], errors='coerce').fillna(0).clip(lower=0)
    
            df_merged['예상소진주'] = np.where(df_merged['주평균판매량'] > 0, 
                                           (df_merged['현재재고'] / df_merged['주평균판매량']).round(1), 
                                           999.0)
            df_merged['예상소진주'] = pd.to_numeric(df_merged['예상소진주'], errors='coerce').fillna(0).clip(lower=0)
    
            def check_status(row):
                if row['현재재고'] <= 0: return "품절"
                if row['예상소진주'] < 2.0: return "부족"
                limit = row['과다기준주'] if pd.notna(row['과다기준주']) and row['과다기준주'] > 0 else 24.0
                return "과다" if row['예상소진주'] > limit else "적정"
                
            df_merged['재고상태'] = df_merged.apply(check_status, axis=1)
    
            def format_stock_display(qty, box_unit):
                if box_unit <= 1: 
                    return f"{int(qty):,} 개" if qty == int(qty) else f"{qty:.1f} 개"
                boxes = qty / box_unit
                return f"{boxes:.1f} 박스" if boxes < 10 else f"{int(boxes):,} 박스"
    
            df_merged['환산재고'] = df_merged.apply(lambda r: format_stock_display(r['현재재고'], r['박스입수']), axis=1)
            df_merged['환산주평균'] = df_merged.apply(lambda r: format_stock_display(r['주평균판매량'], r['박스입수']), axis=1)
    
            # 필터 적용
            if selected_brand != "전체보기":
                df_merged = df_merged[df_merged['브랜드'] == selected_brand]
            if selected_status != "전체보기":
                df_merged = df_merged[df_merged['재고상태'] == selected_status]
    
            # 6. 상단 정보 박스 출력
            date_range_str = f"{start_date.year}년 {start_date.month}월 ~ {end_date.year}년 {end_date.month}월"
            st.info(f"**업데이트 :** {update_time}  \n**산출기간 :** {date_range_str} ({months_to_look_back}개월 판매량 기준)")
            
            # 7. 카드 렌더링 루프
            if df_merged.empty:
                st.warning("조건에 맞는 품목이 없습니다.")
            else:
                # 🚀 [핵심 변경] '한번에보기' 여부에 따라 그룹핑 방식을 결정합니다.
                if view_all_toggle:
                    # 브랜드 무시하고 전체 데이터를 하나의 그룹("전체 품목")으로 묶음
                    groups = [("전체 품목", df_merged)]
                else:
                    # 기존처럼 브랜드를 기준으로 데이터를 쪼개어 그룹 생성
                    groups = [(br, df_merged[df_merged['브랜드'] == br]) for br in sorted(df_merged['브랜드'].unique())]
    
                # 결정된 그룹 단위로 반복 출력
                for group_name, br_df in groups:
                    
                    # 아이콘 동적 변경 (통합일 땐 📦, 브랜드별일 땐 🏢)
                    icon = "📦" if view_all_toggle else "🏢"
                    html_content = f'<div class="brand-section"><div class="brand-title">{icon} {group_name} ({len(br_df)}개 품목)</div><div class="grid-container">'
                    
                    for _, row in br_df.iterrows():
    
                        # 1. 상태별 색상 및 두께 일괄 정의 (전부 1px로 통일)
                        if row['재고상태'] == "품절":
                            status_color = "#fd1e1e" # 빨간색
                            border_thick = "1px"
                            text_color = "white"     # 짙은 배경엔 흰 글자
                        elif row['재고상태'] == "부족":
                            status_color = "#ffe321" # 노란색
                            border_thick = "1px"
                            text_color = "black"     # 밝은 배경엔 검은 글자
                        elif row['재고상태'] == "과다":
                            status_color = "#28a745" # 초록색
                            border_thick = "1px"
                            text_color = "white"     # 짙은 배경엔 흰 글자
                        else: # 적정
                            status_color = "#e0e0e0" # 옅은 회색
                            border_thick = "1px"
                            text_color = "inherit"   # 기본 글자색 유지
    
                        # 2. 테두리 및 타이틀 스타일 적용
                        border_style = f"border: {border_thick} solid {status_color};"
                        
                        if row['재고상태'] == "적정":
                            title_style = ""
                        else:
                            title_style = f"background-color: {status_color}; color: {text_color};"
                        
                        # 🚀 [추가] 한번에보기 일 경우 품목명 위에 '브랜드명'을 연하게 추가
                        if view_all_toggle:
                            # 0.8rem 크기로 연하게(opacity: 0.8) 브랜드명을 넣고 <br>로 줄바꿈
                            display_title = f"<span style='font-size: 1.2rem; font-weight: normal; opacity: 0.9;'>{row['브랜드']}</span><br>{row['품목명']}"
                        else:
                            display_title = row['품목명']
    
                        # 3. 예상소진주: 불필요한 .0 소수점 제거 로직 적용
                        if row['예상소진주'] >= 96:
                            combined_html = '<span class="info-num">2</span><span class="info-unit">년이상</span>'
                        else:
                            weeks = row['예상소진주']
                            months = round(weeks / 4, 1)
                            
                            if weeks >= 10:
                                str_weeks = f"{int(round(weeks))}"
                            else:
                                str_weeks = f"{int(weeks)}" if weeks == int(weeks) else f"{round(weeks, 1)}"
                                
                            if months >= 10:
                                str_months = f"{int(round(months))}"
                            else:
                                str_months = f"{int(months)}" if months == int(months) else f"{round(months, 1)}"
                            
                            combined_html = f'<span class="info-num">{str_weeks}</span><span class="info-unit">주</span> <span style="color:#ccc; font-size:0.9rem;">·</span> <span class="info-num">{str_months}</span><span class="info-unit">달</span>'
                        
                        # 4. 현재고: ".0" 꼬리표 강제 절삭
                        stock_text = str(row['환산재고'])
                        stock_parts = stock_text.split(' ')
                        stock_num = stock_parts[0]
                        if stock_num.endswith('.0'): 
                            stock_num = stock_num[:-2]
                        stock_unit = stock_parts[1] if len(stock_parts) > 1 else ""
    
                        # 5. 주평균: ".0" 꼬리표 강제 절삭
                        avg_text = str(row['환산주평균'])
                        avg_parts = avg_text.split(' ')
                        avg_num = avg_parts[0]
                        if avg_num.endswith('.0'): 
                            avg_num = avg_num[:-2]
                        avg_unit = avg_parts[1] if len(avg_parts) > 1 else ""
    
                        # 🚀 [적용] 완성된 display_title 변수를 아이템 타이틀 부분에 삽입
                        card_html = f"""
                        <div class="item-card" style="{border_style}">
                            <div class="card-header">
                                <div class="item-title" style="{title_style}">{display_title}</div>
                                <div class="stock-main">
                                    <span class="stock-label">현재고</span>
                                    <div>
                                        <span class="stock-val">{stock_num}</span>
                                        <span class="stock-unit">{stock_unit}</span>
                                    </div>
                                </div>
                            </div>
                            <div class="card-divider"></div>
                            <div class="card-body">
                                <div class="info-row">
                                    <span class="info-label">주평균</span>
                                    <div>
                                        <span class="info-num">{avg_num}</span><span class="info-unit">{avg_unit}</span>
                                    </div>
                                </div>
                                <div class="info-row">
                                    <span class="info-label">예상</span>
                                    <div>{combined_html}</div>
                                </div>
                            </div>
                        </div>
                        """
                        html_content += card_html.replace('\n', '').strip()
                    
                    html_content += '</div></div>' 
                    st.markdown(html_content, unsafe_allow_html=True)

    except Exception as e:
        st.error(f"데이터 분석 중 오류가 발생했습니다: {e}")
