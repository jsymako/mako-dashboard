import streamlit as st
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import json
from streamlit_option_menu import option_menu 
import datetime
import holidays # 🚀 공휴일 체크용 라이브러리 추가

# 🚀 메뉴별 파일 임포트
import own_stock
import coupang_stock
import sales_trend
import trade_trend
import ar_trend

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
        df = pd.DataFrame(data[1:], columns=data[0])
        return df
    except Exception as e:
        return None 

# -----------------------------------------------------------------
# 🚀 1. 사이드바 CSS (열기/닫기 글자 박멸)
# -----------------------------------------------------------------
st.markdown("""
    <style>
    [data-testid="collapsedControl"] {
        color: transparent !important;
        background: transparent !important;
    }
    [data-testid="collapsedControl"] * { display: none !important; }
    [data-testid="collapsedControl"]::after {
        content: "❯" !important;
        font-size: 24px !important;
        font-weight: 900 !important;
        color: #333333 !important;
        display: block !important;
        margin-left: 10px !important;
    }
    </style>
""", unsafe_allow_html=True)

# -----------------------------------------------------------------
# 🚀 2. 사이드바 구성 (메뉴바)
# -----------------------------------------------------------------
with st.sidebar:
    st.title("통합관리")
    main_menu = option_menu(
        menu_title=None, 
        options=["🏠 메인 요약", "📦 자사 재고", "🚀 쿠팡 재고", "📈 판매 현황", "🤝 거래처 현황", "💳 채권 분석"],
        icons=["", "", "", "", "", ""], 
        default_index=0, 
        styles={
            "container": {"padding": "0!important", "background-color": "transparent", "border": "none"},
            "nav-link": {
                "font-size": "1.25rem", "text-align": "left", "margin": "0px 0px 8px 0px",
                "padding": "12px 15px", "border-radius": "8px", "border": "2px solid #ddd", 
                "color": "#333", "font-weight": "bold"
            },
            "nav-link-hover": {"background-color": "#fdf2f2", "border-color": "#d9534f"},
            "nav-link-selected": {"background-color": "#d9534f", "color": "white", "font-weight": "900", "border-color": "#d9534f"},
        }
    )

st.sidebar.markdown("---")

# -----------------------------------------------------------------
# 🚀 3. 메인 대시보드 (공휴일 완벽 패스 & 채권 예외 처리)
# -----------------------------------------------------------------
def render_dashboard():
    st.title("🏠 통합재고관리 관제센터")
    st.markdown("각 모듈의 **최신 업데이트 날짜**와 크롤링 **누락일(영업일 기준)**을 점검하세요.")
    
    st.markdown("""
        <style>
        .dash-card {
            border: 1px solid #e0e0e0; border-radius: 10px; padding: 20px; 
            background: #fff; box-shadow: 2px 2px 10px rgba(0,0,0,0.05); height: 100%;
        }
        .dash-title { font-size: 1.25rem; font-weight: 800; color: #111; margin-bottom: 12px; border-bottom: 2px solid #eee; padding-bottom: 10px; }
        .dash-stat { font-size: 1.4rem; font-weight: 900; color: #0275d8; }
        .status-ok { color: #5cb85c; font-weight: bold; font-size: 0.95rem; }
        .status-err { color: #d9534f; font-weight: bold; font-size: 0.95rem; }
        .status-warn { color: #f0ad4e; font-weight: bold; font-size: 0.95rem; }
        .sub-text { font-size: 0.9rem; margin-top: 15px; background: #f8f9fa; padding: 12px; border-radius: 6px; }
        </style>
    """, unsafe_allow_html=True)

    modules = {
        "자사 재고": {"sheet_name": "ecount_stock", "icon": "📦", "check_date": True},
        "쿠팡 재고": {"sheet_name": "coupang_stock", "icon": "🚀", "check_date": True},
        "판매 현황": {"sheet_name": "sales_record", "icon": "📈", "check_date": True},
        "거래처 현황": {"sheet_name": "trade_record", "icon": "🤝", "check_date": True},
        "채권 분석": {"sheet_name": "ar_memo", "icon": "💳", "check_date": False} # 🚀 채권분석은 날짜 체크 완전 제외!
    }

    # 🚀 최근 7일(달력 기준) 생성 후, 주말 및 공휴일 발라내기
    today = pd.Timestamp.now().normalize()
    past_week = pd.date_range(end=today, periods=7, freq='D')
    kr_holidays = holidays.KR(years=range(today.year - 1, today.year + 1))
    
    # 월~금(weekday < 5)이면서 한국 공휴일이 아닌 날만 '진짜 영업일'로 추출
    valid_business_days = [bd for bd in past_week if bd.weekday() < 5 and bd.date() not in kr_holidays]

    cols = st.columns(3)
    for idx, (m_name, m_info) in enumerate(modules.items()):
        col = cols[idx % 3]
        
        with col:
            df = load_sheet_data(m_info["sheet_name"])
            
            if df is not None and not df.empty:
                # 🚀 날짜 체크가 필요한 모듈 (자사, 쿠팡, 판매, 거래처)
                if m_info["check_date"]:
                    date_col = next((c for c in df.columns if any(kw in str(c) for kw in ['일자', '날짜', '등록일', '기준일', '수집일'])), None)
                    
                    if date_col:
                        parsed_dates = pd.to_datetime(df[date_col].astype(str).str.strip(), errors='coerce').dropna()
                        
                        if not parsed_dates.empty:
                            latest_date = parsed_dates.max()
                            latest_date_str = latest_date.strftime('%Y-%m-%d')
                            unique_dates_set = set(parsed_dates.dt.strftime('%Y-%m-%d'))
                            
                            # 진짜 영업일 중 누락된 날짜만 찾기
                            missing_days = []
                            for bd in valid_business_days:
                                bd_str = bd.strftime('%Y-%m-%d')
                                if bd_str not in unique_dates_set:
                                    missing_days.append(bd.strftime('%m/%d(%a)'))
                            
                            if missing_days:
                                missing_str = f"<span style='color:#d9534f; font-weight:bold;'>{', '.join(missing_days)}</span>"
                                icon_status = "⚠️ 누락 확인"
                                icon_class = "status-warn"
                            else:
                                missing_str = "<span style='color:#5cb85c; font-weight:bold;'>누락 없음 (완벽)</span>"
                                icon_status = "🟢 정상 수신중"
                                icon_class = "status-ok"

                            st.markdown(f"""
                                <div class="dash-card">
                                    <div class="dash-title">{m_info['icon']} {m_name}</div>
                                    <div style="margin-bottom: 8px;">연동 상태: <span class="{icon_class}">{icon_status}</span></div>
                                    <div>최신 데이터: <span class="dash-stat">{latest_date_str}</span></div>
                                    <div class="sub-text">
                                        <b>🔍 7일 내 누락(휴일 제외):</b><br>{missing_str}
                                    </div>
                                </div>
                            """, unsafe_allow_html=True)
                        else:
                            st.markdown(f"""
                                <div class="dash-card">
                                    <div class="dash-title">{m_info['icon']} {m_name}</div>
                                    <div>연동 상태: <span class="status-warn">⚠️ 날짜 파싱 오류</span></div>
                                </div>
                            """, unsafe_allow_html=True)
                
                # 🚀 날짜 체크가 필요 없는 모듈 (채권 분석)
                else:
                    st.markdown(f"""
                        <div class="dash-card">
                            <div class="dash-title">{m_info['icon']} {m_name}</div>
                            <div>연동 상태: <span class="status-ok">🟢 정상 수신중</span></div>
                            <div class="sub-text" style="color: #666; font-style: italic;">
                                날짜 누락 검사 대상이 아닙니다. (메모 등 수동 관리)
                            </div>
                        </div>
                    """, unsafe_allow_html=True)
            
            # 시트 연결 실패 시
            else:
                st.markdown(f"""
                    <div class="dash-card">
                        <div class="dash-title">{m_info['icon']} {m_name}</div>
                        <div>연동 상태: <span class="status-err">🔴 점검 필요</span></div>
                        <div class="sub-text">시트명 불일치 또는 데이터가 없습니다.</div>
                    </div>
                """, unsafe_allow_html=True)

# -----------------------------------------------------------------
# 🚀 4. 메뉴 선택에 따른 화면 전환
# -----------------------------------------------------------------
if main_menu == "🏠 메인 요약" or main_menu is None:
    render_dashboard()
elif main_menu == "📦 자사 재고":
    own_stock.run(load_sheet_data) 
elif main_menu == "🚀 쿠팡 재고":
    coupang_stock.run(load_sheet_data)
elif main_menu == "📈 판매 현황":
    sales_trend.run(load_sheet_data)
elif main_menu == "🤝 거래처 현황":
    trade_trend.run(load_sheet_data)
elif main_menu == "💳 채권 분석":
    ar_trend.run(load_sheet_data)
