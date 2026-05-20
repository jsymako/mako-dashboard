import streamlit as st
import pandas as pd
import numpy as np
import datetime
from dateutil.relativedelta import relativedelta
import os

def run(load_data_func):
    st.title("자사 재고 현황")
    
    # 🚀 짝꿍 CSS 파일 불러오기
    try:
        with open("style.css", "r", encoding="utf-8") as f:
            st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)
    except FileNotFoundError:
        pass

    

    try:
        # 1. 데이터 로드
        df_own = load_data_func("ecount_stock")
        df_sales = load_data_func("sales_record")
        df_item = load_data_func("ecount_item_data")
        
        # 업데이트 시간 추출
        update_time = df_own['업데이트 시간'].iloc[0] if '업데이트 시간' in df_own.columns and not df_own.empty else '정보 없음'

        # 2. 데이터 전처리
        df_own['현재재고'] = pd.to_numeric(df_own['현재재고'], errors='coerce').fillna(0).clip(lower=0)
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
        
        # 🚀 [수정] 순서 및 단어 변경: 부족, 품절, 과다, 적정
        status_list = ["전체보기", "부족", "품절", "과다", "적정"]
        selected_status = st.sidebar.selectbox("상태 필터", status_list, key="own_status_filter")

        months_to_look_back = st.sidebar.slider("판매 산출 기준 (개월)", 1, 12, 3, key="own_month_slider_v2")

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

        # 🚀 [수정] 상태 판별 함수: 2글자로 간소화 및 잔재 제거
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
            for br in sorted(df_merged['브랜드'].unique()):
                br_df = df_merged[df_merged['브랜드'] == br]
                
                html_content = f'<div class="brand-section"><div class="brand-title">🏢 {br} ({len(br_df)}개 품목)</div><div class="grid-container">'
                
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
                    
                    # '적정'일 때는 타이틀 배경을 투명하게 유지합니다.
                    if row['재고상태'] == "적정":
                        title_style = ""
                    else:
                        # 🚀 display: inline-block;을 제거하여 좌우로 꽉 차는 시원한 헤더로 복구했습니다.
                        title_style = f"background-color: {status_color}; color: {text_color};"
                    
                    # 🚀 [수정] 1. 예상소진주의 숫자와 단위를 HTML 태그로 완벽 분리
                    if row['예상소진주'] >= 96:
                        combined_html = '<span class="info-num">2</span><span class="info-unit">년이상</span>'
                    else:
                        weeks = row['예상소진주']
                        months = round(weeks / 4, 1)
                        
                        str_weeks = f"{int(round(weeks))}" if weeks >= 10 else f"{weeks}"
                        str_months = f"{int(round(months))}" if months >= 10 else f"{months}"
                        
                        combined_html = f'<span class="info-num">{str_weeks}</span><span class="info-unit">주</span> <span style="color:#ddd; font-size:1.5rem;">·</span> <span class="info-num">{str_months}</span><span class="info-unit">달</span>'
                    
                    # 현재고 분리
                    stock_text = row['환산재고']
                    stock_parts = stock_text.split(' ')
                    stock_num = stock_parts[0]
                    stock_unit = stock_parts[1] if len(stock_parts) > 1 else ""

                    # 🚀 [수정] 2. 주평균도 현재고처럼 숫자와 단위를 쪼갬
                    avg_text = row['환산주평균']
                    avg_parts = avg_text.split(' ')
                    avg_num = avg_parts[0]
                    avg_unit = avg_parts[1] if len(avg_parts) > 1 else ""

                    # 🚀 [수정] 3. HTML 구조에 info-num과 info-unit 클래스 적용
                    card_html = f"""
                    <div class="item-card" style="{border_style}">
                        <div class="card-header">
                            <div class="item-title" style="{title_style}">{row['품목명']}</div>
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
