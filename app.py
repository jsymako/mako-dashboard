import streamlit as st
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import json
from streamlit_option_menu import option_menu 
import datetime
import holidays 

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
        
        if len(data) <= 1:
            return pd.DataFrame(columns=data[0] if data else [])
            
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

    main_menu = option_menu(
        menu_title=None, 
        options=["🏠 메인 요약", "📦 자사 재고", "🚀 쿠팡 재고", "📈 판매 현황", "🤝 거래처 현황", "💳 채권 분석"],
        icons=["", "", "", "", "", ""], 
        default_index=0, 
        styles={
            "container": {"padding": "0!important", "background-color": "transparent", "border": "none"},
            "nav-link": {
                "font-size": "1.40rem", "text-align": "left", "margin": "0px 0px 8px 0px",
                "padding": "10px 6px", "border-radius": "8px", "border": "2px solid #0fb6a9", 
                "color": "#333", "font-weight": "normal", "background-color": "#c3f7f1"
            },
            "nav-link-hover": {"background-color": "#2b98d8", "border-color": "#2b98d8"},
            "nav-link-selected": {"background-color": "#0fb6a9", "color": "white", "font-weight": "600", "border-color": "#0fb6a9"},
        }
    )


# -----------------------------------------------------------------
# 🚀 3. 메인 대시보드 (2열 구조 & 높이 고정 & 여백 추가)
# -----------------------------------------------------------------
def render_dashboard():
    st.title("마코펫 통합재고관리")
    st.markdown("각 데이터 연동 상태와 최근 크롤링 누락 여부를 확인합니다.")
    
    # 🚀 CSS 업데이트: margin-bottom을 추가하여 카드 자체가 아래로 여유를 가지게 함
    st.markdown("""
        <style>
        .dash-card {
            border: 1px solid #e0e0e0; 
            border-radius: 10px; 
            padding: 20px; 
            margin-bottom: 10px; /* 🚀 위아래 카드 사이의 여백 추가 */
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
        "판매 현황": {"sheet_name": "sales_record", "icon": "📈", "type": "missing_check", "offset": 2},
        "거래처 현황": {"sheet_name": "trade_record", "icon": "🤝", "type": "missing_check", "offset": 2}
    }

    today = pd.Timestamp.now().normalize()
    kr_holidays = holidays.KR(years=range(today.year - 1, today.year + 1))
    
    module_items = list(modules.items())
    
    # 🚀 그리드를 2개씩 끊어서(2열) 출력
    for i in range(0, len(module_items), 2):
        cols = st.columns(2)
        for j in range(2):
            if i + j < len(module_items):
                m_name, m_info = module_items[i + j]
                
                with cols[j]:
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
                                        past_week = pd.date_range(end=target_date, periods=7, freq='D')
                                        
                                        valid_business_days = [bd for bd in past_week if bd.weekday() < 5 and bd.date() not in kr_holidays]
                                        
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

                                        target_label = f"D-{m_info['offset']}"

                                        st.markdown(f"""
                                            <div class="dash-card">
                                                <div>
                                                    <div class="dash-title">{m_info['icon']} {m_name}</div>
                                                    <div style="margin-bottom: 8px;">연동 상태: <span class="{icon_class}">{icon_status}</span></div>
                                                    <div>최신 데이터: <span class="dash-stat">{latest_date_str}</span></div>
                                                </div>
                                                <div class="sub-text">
                                                    <b>🔍 7일 내 누락 (기준: {target_label}):</b><br>{missing_str}
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
        
        # 🚀 1행이 끝나면 물리적인 띄어쓰기(공백)를 강제로 추가하여 행간을 넓힘
        st.markdown("<div style='height: 15px;'></div>", unsafe_allow_html=True)

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
