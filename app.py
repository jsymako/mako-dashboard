import streamlit as st
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import json
from streamlit_option_menu import option_menu 
from datetime import datetime

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
        return None # 에러 발생 시 None 반환 (메인 화면에서 오류 감지용)

# -----------------------------------------------------------------
# 🚀 1. 사이드바 열기/닫기 글자 "완전 박멸" CSS
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
# 🚀 2. 사이드바 구성 (메인 요약 메뉴 추가!)
# -----------------------------------------------------------------
with st.sidebar:
    # st.image("mako_logo.png", use_container_width=True) 
    st.title("통합관리")

    # 🚀 옵션 메뉴에 "🏠 메인 요약"을 1번에 추가!
    main_menu = option_menu(
        menu_title=None, 
        options=["🏠 메인 요약", "📦 자사 재고", "🚀 쿠팡 재고", "📈 판매 현황", "🤝 거래처 현황", "💳 채권 분석"],
        icons=["", "", "", "", "", ""], 
        default_index=0, # 접속 시 무조건 0번(메인 요약)이 뜹니다.
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
# 🚀 3. 메인 대시보드 렌더링 전용 함수
# -----------------------------------------------------------------
def render_dashboard():
    st.title("🏠 통합재고관리 관제센터")
    st.markdown("각 모듈의 **데이터 연동 상태**와 **전체 규모**를 한눈에 확인하세요.")
    
    # 대시보드용 카드 CSS
    st.markdown("""
        <style>
        .dash-card {
            border: 1px solid #e0e0e0; border-radius: 10px; padding: 20px; 
            background: #fff; box-shadow: 2px 2px 10px rgba(0,0,0,0.05); height: 100%;
        }
        .dash-title { font-size: 1.2rem; font-weight: 800; color: #111; margin-bottom: 15px; border-bottom: 2px solid #eee; padding-bottom: 10px; }
        .dash-stat { font-size: 1.5rem; font-weight: 900; color: #d9534f; }
        .status-ok { color: #5cb85c; font-weight: bold; }
        .status-err { color: #d9534f; font-weight: bold; }
        .sub-text { font-size: 0.85rem; color: #888; margin-top: 10px; }
        </style>
    """, unsafe_allow_html=True)

    # 🚀 구글 시트 연결 상태 체크 (대표님의 실제 시트 이름에 맞게 수정 필요)
    # 속도를 위해 캐시된 데이터를 살짝 찔러보기만 합니다.
    modules = {
        "자사 재고": {"sheet_name": "ecount_stock", "icon": "📦"},
        "쿠팡 재고": {"sheet_name": "coupang_stock", "icon": "🚀"},
        "판매 현황": {"sheet_name": "sales_record", "icon": "📈"},
        "거래처 현황": {"sheet_name": "trade_record", "icon": "🤝"},
        "채권 분석": {"sheet_name": "ar_memo", "icon": "💳"} # ar_trend에서 쓰는 메모 시트 기준
    }

    cols = st.columns(3)
    
    for idx, (m_name, m_info) in enumerate(modules.items()):
        col = cols[idx % 3] # 3열로 줄바꿈하며 배치
        
        with col:
            # 데이터 로딩 시도
            df = load_sheet_data(m_info["sheet_name"])
            
            # 카드 렌더링
            if df is not None:
                row_count = len(df)
                now_str = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                st.markdown(f"""
                    <div class="dash-card">
                        <div class="dash-title">{m_info['icon']} {m_name}</div>
                        <div>연동 상태: <span class="status-ok">🟢 정상 수신중</span></div>
                        <div style="margin-top:10px;">확보된 데이터: <span class="dash-stat">{row_count:,}</span>건</div>
                        <div class="sub-text">⏳ 최종 체크: {now_str}</div>
                    </div>
                """, unsafe_allow_html=True)
            else:
                st.markdown(f"""
                    <div class="dash-card">
                        <div class="dash-title">{m_info['icon']} {m_name}</div>
                        <div>연동 상태: <span class="status-err">🔴 점검 필요</span></div>
                        <div class="sub-text">구글 시트({m_info['sheet_name']})를 찾을 수 없거나 접근 권한이 없습니다.</div>
                    </div>
                """, unsafe_allow_html=True)
                
    st.markdown("<br><br>", unsafe_allow_html=True)
    st.info("💡 **Tip:** 좌측 메뉴를 클릭하여 각 모듈의 상세 데이터를 확인하고 관리할 수 있습니다.")

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
