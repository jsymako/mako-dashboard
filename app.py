import streamlit as st
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import json
from streamlit_option_menu import option_menu 
import datetime
import holidays 

import own_stock
import coupang_stock
import sales_trend
import trade_trend
import ar_trend
import sales_perf
import inbound_manager
import work_report
import order_management

st.set_page_config(page_title="통합재고관리", page_icon="🏠", layout="wide")

# 🚀 공통 데이터 로드 함수
@st.cache_data(ttl=600)
def load_sheet_data(worksheet_name):
    try:
        scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
        creds_dict = json.loads(st.secrets["gcp_service_account"])
        creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
        client = gspread.authorize(creds)
        doc = client.open("통합재고관리")
        sheet = doc.worksheet(worksheet_name)
        data = sheet.get_all_values()
        
        if len(data) <= 1:
            return pd.DataFrame(columns=data[0] if data else [])
            
        df = pd.DataFrame(data[1:], columns=data[0])
        return df
    except Exception as e:
        return None 

# -----------------------------------------------------------------
# 🚀 1. 사이드바만 강제로 다크 모드로 만드는 CSS
# -----------------------------------------------------------------
st.markdown("""
    <style>
    /* 메인 화면은 하얗게 두고, 사이드바 껍데기만 다크 네이비로 강제 지정 */
    [data-testid="stSidebar"] {
        background-color: #1E212B !important;
        min-width: 200px !important;
        max-width: 200px !important;
    }
    
    /* 스트림릿 내부의 숨겨진 하얀색 레이어도 다크 네이비로 덮어쓰기 */
    [data-testid="stSidebar"] > div:first-child {
        background-color: #1E212B !important;
        min-width: 200px !important;
        max-width: 200px !important;
        padding-top: 30px !important; 
        padding-bottom: 0px !important; /* 🚀 껍데기 하단 여백 제거 */
    }
    
    /* 🚀 [범인 검거] 캡처해주신 160x60 사이즈의 투명한 사이드바 헤더 영역 완전히 박살내기 */
    [data-testid="stSidebarHeader"] {
        padding: 0px !important;
        height: 0px !important;
        min-height: 0px !important;
        margin: 0px !important;
        display: none !important; /* 공간만 차지하던 유령 헤더 아예 삭제 */
    }
    
    /* 🚀 사이드바 안쪽 내용물(메뉴) 상/하단 여백 완전 제거 */
    [data-testid="stSidebarUserContent"] {
        padding-top: 0px !important;
        padding-bottom: 0px !important; /* 🚀 [핵심] 캡처에 나온 하단 보라색 여백을 박멸합니다! */
    }
    
    /* 빈 마크다운(style) 찌꺼기들이 차지하는 16px 마진 제거 */
    [data-testid="stSidebar"] div.element-container:has(style),
    [data-testid="stSidebar"] div.element-container:has(script) {
        display: none !important;
        height: 0px !important;
        margin: 0px !important;
    }

    /* 열기/닫기 화살표 색상을 흰색으로 */
    [data-testid="collapsedControl"] * { display: none !important; }
    [data-testid="collapsedControl"]::after {
        content: "❯" !important;
        font-size: 22px !important;
        font-weight: 900 !important;
        color: #FFFFFF !important;
        display: block !important;
        margin-left: 10px !important;
    }
    [data-testid="stSidebarNav"] {
        display: none !important;
    }
    
    /* 혹시 모를 iframe 하얀색 모서리 잔재 제거 */
    iframe {
        background-color: transparent !important;
    }

    /* 🚀 [추가] 사이드바 내부 세로 블록(stVerticalBlock)의 강제 하단 여백 및 간격 완벽 제거 */
    [data-testid="stSidebar"] [data-testid="stVerticalBlock"] {
        padding-bottom: 0px !important;
        gap: 0px !important;
    }
    [data-testid="stSidebar"] [data-testid="stVerticalBlock"] > div {
        padding-bottom: 0px !important;
        margin-bottom: 0px !important;
    }
    </style>
""", unsafe_allow_html=True)

# -----------------------------------------------------------------
# 🚀 2. ECharts 감성의 메뉴바 (option_menu 복구)
# -----------------------------------------------------------------
with st.sidebar:
    main_menu = option_menu(
        menu_title=None, 
        options=["대시 보드", "자사 재고", "판매 현황", "입고 현황", "쿠팡 현황", "업무 보고", "영업 실적", "채권 분석","발주 입력"],
        icons=[
            "grid",             # 대시 보드 (바둑판 모양)
            "boxes",            # 자사 재고 (쌓여있는 상자)
            "graph-up-arrow",   # 판매 현황 (상승하는 그래프)
            "truck",            # 입고 현황 (배송 트럭)
            "box-seam",         # 쿠팡 재고 (테이핑 된 택배 상자)
            "pencil-square",    # 업무 보고 (펜과 종이)
            "award",            # 영업 실적 (트로피/뱃지)
            "cash-stack",        # 채권 분석 (쌓여있는 돈/현금)
            "cart"
        ],
        default_index=0, 
        styles={
            "container": {
                "padding": "0!important", 
                "background-color": "#1E212B",
                "border-radius": "0px !important",  # 🚀 [추가] 전체 껍데기의 둥근 모서리를 직각으로 펴서 하얀 틈새를 완벽 차단합니다!
                "border": "none"                    # 🚀 [추가] 혹시 모를 외곽선도 제거
            },
            "icon": {
                "color": "#FFFFFF",               
                "font-size": "1.1rem"               # 🚀 1. [수정] 아이콘 크기 (기본 1.1rem -> 더 키우려면 1.2rem, 1.3rem)
            },
            "nav-link": {
                "font-size": "1.05rem",            # 🚀 2. [수정] 글자 크기 (기본 1.05rem -> 더 키우려면 1.1rem, 1.2rem)
                "text-align": "left", 
                "margin": "0px 0px 4px 0px",        # 🚀 3. [수정] 버튼과 버튼 사이의 간격 (4px을 8px로 늘리면 메뉴 사이가 벌어집니다)
                "padding": "3px 15px",            # 🚀 4. [수정] 버튼 자체의 크기 (위아래 10px, 양옆 15px 여백. 15px 20px로 늘리면 버튼이 훨씬 커집니다)
                "border-radius": "0.5rem",          # (개별 메뉴 버튼의 둥근 모서리는 그대로 유지)
                "color": "#FFFFFF",               
                "font-weight": "400",
                "border": "none",
                "--hover-color": "#485068"        
            },
            "nav-link-selected": {
                "background-color": "#485068",    
                "color": "#FFFFFF",               
                "font-weight": "500",             
                "border": "none"
            },
        }
    )

    st.sidebar.markdown('<hr style="border-top: 0px solid rgba(255, 255, 255, 0.5); margin: 10px 0px">', unsafe_allow_html=True)
    
# -----------------------------------------------------------------
# 🚀 3. 메인 대시보드 화면 (1줄에 3개 나란히 배치)
# -----------------------------------------------------------------
def render_dashboard():
    st.title("마코펫 통합조회시스템")
    
    st.markdown("""
        <style>
        .dash-card {
            border: 1px solid #e0e0e0; 
            border-radius: 10px; 
            padding: 20px; 
            margin-bottom: 10px; 
            background: #fff; 
            box-shadow: 2px 2px 10px rgba(0,0,0,0.05); 
            height: 250px; 
            display: flex;
            flex-direction: column;
            justify-content: space-between;
        }
        .dash-title { font-size: 1.4rem; font-weight: 600; color: #111; margin-bottom: 5px; border-bottom: 2px solid #eee; padding-bottom: 10px; }
        .dash-stat { font-size: 1.4rem; font-weight: 600; color: #0275d8; }
        .status-ok { color: #5cb85c; font-weight: normal; font-size: 1.2rem; }
        .status-err { color: #d9534f; font-weight: bold; font-size: 1.2rem; }
        .status-warn { color: #f0ad4e; font-weight: bold; font-size: 1.2rem; }
        .sub-text { font-size: 1.1rem; margin-top: 5px; background: #f8f9fa; padding: 12px; border-radius: 6px; }
        </style>
    """, unsafe_allow_html=True)

    modules = {
        "자사 재고": {"sheet_name": "ecount_stock", "icon": "📦", "type": "latest_only"},
        "쿠팡 재고": {"sheet_name": "coupang_stock", "icon": "🚀", "type": "missing_check", "offset": 1},
        "판매 현황": {"sheet_name": "trade_record", "icon": "🤝", "type": "missing_check", "offset": 2}
    }

    today = pd.Timestamp.now().normalize()
    kr_holidays = holidays.KR(years=range(today.year - 1, today.year + 1))
    
    module_items = list(modules.items())
    
    # 🚀 [핵심 수정] 2줄씩 나누던 코드를 지우고, 화면을 3등분(3열)하여 한 줄로 나란히 배치합니다.
    cols = st.columns(3)
    
    for i, (m_name, m_info) in enumerate(module_items):
        with cols[i]:
            try: 
                df = load_sheet_data(m_info["sheet_name"])
                
                if df is not None and not df.empty:
                    date_col = next((c for c in df.columns if any(kw in str(c) for kw in ['일자', '날짜', '등록일', '기준일', '수집일', '시간', '일시', '업데이트'])), None)
                    
                    if m_info["type"] == "latest_only":
                        latest_str = "확인 불가"
                        if date_col:
                            parsed_dates = pd.to_datetime(df[date_col].astype(str).str.strip(), errors='coerce').dropna()
                            if not parsed_dates.empty:
                                latest_str = parsed_dates.max().strftime('%Y-%m-%d %H:%M')
                                
                        st.markdown(f"""
                            <div class="dash-card">
                                <div>
                                    <div class="dash-title">{m_info['icon']} {m_name}</div>
                                    <div style="margin-bottom: 8px;">연동 상태: <span class="status-ok">🟢 정상 수신중</span></div>
                                </div>
                                <div class="sub-text">
                                    <b>최신 데이터 갱신 일시:</b><br>
                                    <span style="font-size:1.1rem; color:#0275d8; font-weight:bold;">{latest_str}</span>
                                </div>
                            </div>
                        """, unsafe_allow_html=True)

                    elif m_info["type"] == "missing_check":
                        if date_col:
                            parsed_dates = pd.to_datetime(df[date_col].astype(str).str.strip(), errors='coerce').dropna()
                            
                            if not parsed_dates.empty:
                                latest_date_str = parsed_dates.max().strftime('%Y-%m-%d')
                                unique_dates_set = set(parsed_dates.dt.strftime('%Y-%m-%d'))
                                
                                target_date = today - pd.Timedelta(days=m_info["offset"])
                                past_month = pd.date_range(end=target_date, periods=30, freq='D')
                                
                                valid_business_days = [bd for bd in past_month if bd.weekday() < 5 and bd.date() not in kr_holidays]
                                
                                missing_days = []
                                for bd in valid_business_days:
                                    bd_str = bd.strftime('%Y-%m-%d')
                                    if bd_str not in unique_dates_set:
                                        missing_days.append(bd.strftime('%m/%d(%a)'))
                                
                                if missing_days:
                                    if len(missing_days) > 5:
                                        display_missing = ', '.join(missing_days[:5]) + f" ...외 {len(missing_days)-5}일"
                                    else:
                                        display_missing = ', '.join(missing_days)
                                        
                                    missing_str = f"<span style='color:#d9534f; font-weight:bold;'>{display_missing}</span>"
                                    icon_status = "⚠️ 누락 확인"
                                    icon_class = "status-warn"
                                else:
                                    missing_str = "<span style='color:#5cb85c; font-weight:bold;'>누락 없음</span>"
                                    icon_status = "🟢 정상 수신중"
                                    icon_class = "status-ok"

                                target_label = f"D-{m_info['offset']}"

                                st.markdown(f"""
                                    <div class="dash-card">
                                        <div>
                                            <div class="dash-title">{m_info['icon']} {m_name}</div>
                                            <div style="margin-bottom: 8px;">연동 상태: <span class="{icon_class}">{icon_status}</span></div>
                                            <div>최신 데이터: <span class="dash-stat">{latest_date_str}</span></div>
                                        </div>
                                        <div class="sub-text">
                                            <b>🔍 30일 내 누락 (기준: {target_label}):</b><br>{missing_str}
                                        </div>
                                    </div>
                                """, unsafe_allow_html=True)
                            else:
                                st.markdown(f"<div class='dash-card'><div><div class='dash-title'>{m_info['icon']} {m_name}</div><div>연동 상태: <span class='status-warn'>⚠️ 날짜 파싱 오류</span></div></div></div>", unsafe_allow_html=True)
                    else:
                        st.markdown(f"""
                            <div class="dash-card">
                                <div>
                                    <div class="dash-title">{m_info['icon']} {m_name}</div>
                                    <div>연동 상태: <span class="status-err">🔴 점검 필요</span></div>
                                </div>
                                <div class="sub-text">시트명 불일치 또는 데이터가 없습니다.</div>
                            </div>
                        """, unsafe_allow_html=True)
                        
            except Exception as e:
                st.markdown(f"""
                    <div class="dash-card">
                        <div>
                            <div class="dash-title">{m_info['icon']} {m_name}</div>
                            <div>연동 상태: <span class="status-err">🔴 분석 중단</span></div>
                        </div>
                        <div class="sub-text" style="color:red; font-size:0.8rem;">데이터 구조 오류가 발생했습니다.</div>
                    </div>
                """, unsafe_allow_html=True)
    
    st.markdown("<div style='height: 15px;'></div>", unsafe_allow_html=True)

# -----------------------------------------------------------------
# 🚀 4. 메뉴 선택에 따른 화면 전환 (다시 복구!)
# -----------------------------------------------------------------
if main_menu == "대시 보드" or main_menu is None:
    render_dashboard()
elif main_menu == "자사 재고":
    own_stock.run(load_sheet_data) 
elif main_menu == "쿠팡 현황":
    coupang_stock.run(load_sheet_data)
elif main_menu == "입고 현황":
    inbound_manager.run(load_sheet_data)
elif main_menu == "판매 현황":
    trade_trend.run(load_sheet_data)
elif main_menu == "업무 보고":
    work_report.run(load_sheet_data)
elif main_menu == "채권 분석":
    ar_trend.run(load_sheet_data)
elif main_menu == "영업 실적":
    sales_perf.run(load_sheet_data)
elif main_menu == "발주 입력":
    order_management.run(load_sheet_data)
