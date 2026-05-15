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
import sales_perf

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
    [data-testid="stSidebar"] {
        min-width: 230px !important;
        max-width: 230px !important;
        background-color: #1E212B !important;  /* 🚀 아주 세련된 다크 네이비/그레이 색상 */
    }
    [data-testid="collapsedControl"] * { display: none !important; }
    [data-testid="collapsedControl"]::after {
        content: "❯" !important;
        font-size: 22px !important;
        font-weight: 900 !important;
        color: #FFFFFF !important;
        display: block !important;
        margin-left: 10px !important;
    }

    /* 🚀 추가: 사이드바 너비 강제 축소 (숫자를 바꿔가며 최적의 비율을 찾아보세요!) */
    [data-testid="stSidebar"] {
        min-width: 200px !important;
        max-width: 200px !important;
    }
    </style>
""", unsafe_allow_html=True)

# -----------------------------------------------------------------
# 🚀 2. 사이드바 구성 (메뉴바)
# -----------------------------------------------------------------
with st.sidebar:

    main_menu = option_menu(
        menu_title=None, 
        options=["대시보드", "자사 재고", "쿠팡 재고", "판매 현황", "영업 실적", "채권 분석"],
        # 🚀 [추가] 촌스러운 이모지 대신 얇고 깔끔한 부트스트랩 아이콘 삽입!
        # (이미지에 있는 격자 모양 아이콘이 바로 'grid' 입니다)
        icons=["grid", "box", "box-seam", "graph-up", "briefcase", "credit-card"], 
        default_index=0, 
        styles={
            "container": {
                "padding": "0!important", 
                "background-color": "transparent"
            },
            "icon": {
                "color": "#A0AEC0",               # 선택 안 된 아이콘은 은은한 회색
                "font-size": "1.1rem"
            },
            "nav-link": {
                "font-size": "1.05rem",
                "text-align": "left", 
                "margin": "0px 0px 4px 0px",
                "padding": "10px 15px",
                "border-radius": "0.5rem",        # 이미지처럼 모서리가 둥근 박스
                "color": "#A0AEC0",               # 글자색도 은은한 회색
                "font-weight": "400",
                "border": "none"
            },
            "nav-link-hover": {
                "background-color": "rgba(255, 255, 255, 0.05)", # 마우스 올리면 살짝 밝아짐
                "color": "#FFFFFF"
            },
            "nav-link-selected": {
                "background-color": "#374151",    # 🚀 이미지와 똑같은 짙은 둥근 회색 배경
                "color": "#FFFFFF",               # 글자와 아이콘이 순백색으로 빛남
                "font-weight": "600",             # 선택된 메뉴 글자만 볼드 처리
                "border": "none"
            },
        }
    )

    st.sidebar.markdown("---")

# -----------------------------------------------------------------
# 🚀 3. 메인 대시보드 (2열 구조 & 높이 고정 & 여백 추가)
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
                            
                            # 🚀 여기서부터 들여쓰기 짝맞춤 (if와 elif 라인이 완벽하게 일치해야 합니다)
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

                            elif m_info["type"] == "missing_check":  # 🚀 [교정됨] if와 같은 세로 선상으로 우측 4칸 이동!
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
# 🚀 4. 메뉴 선택에 따른 화면 전환
# -----------------------------------------------------------------
if main_menu == "대시보드" or main_menu is None:
    render_dashboard()
elif main_menu == "자사 재고":
    own_stock.run(load_sheet_data) 
elif main_menu == "쿠팡 재고":
    coupang_stock.run(load_sheet_data)
elif main_menu == "판매 현황":
    trade_trend.run(load_sheet_data)
elif main_menu == "채권 분석":
    ar_trend.run(load_sheet_data)
elif main_menu == "영업 실적":
    sales_perf.run(load_sheet_data)
