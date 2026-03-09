import streamlit as st
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import json

# 1. 페이지 기본 설정 (가장 먼저 와야 함)
st.set_page_config(page_title="마코 재고 대시보드", page_icon="📦", layout="wide")

# 2. 구글 시트 데이터 불러오기 (캐싱 적용으로 속도 10배 향상)
# @st.cache_data를 쓰면 사용자가 드롭다운을 바꿀 때마다 구글을 찌르지 않고 메모리에서 바로 꺼냅니다.
@st.cache_data(ttl=600) # 10분마다 새로고침
def load_stock_data():
    scope = [
        "https://spreadsheets.google.com/feeds",
        "https://www.googleapis.com/auth/drive"
    ]
    
    # 💡 스트림릿 클라우드용 보안(Secrets) 설정
    # 로컬의 credentials.json 대신 Streamlit의 안전한 금고(secrets)에서 키를 꺼내옵니다.
    creds_dict = json.loads(st.secrets["gcp_service_account"])
    creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
    client = gspread.authorize(creds)
    
    # ecount_stock 시트 불러오기
    doc = client.open("통합재고관리")
    stock_sheet = doc.worksheet("ecount_stock")
    
    data = stock_sheet.get_all_values()
    
    # 데이터프레임(표)으로 변환 (첫 줄은 제목)
    df = pd.DataFrame(data[1:], columns=data[0])
    
    # '현재재고' 열을 문자가 아닌 '숫자'로 변환 (그래프를 그리기 위함)
    df['현재재고'] = pd.to_numeric(df['현재재고'], errors='coerce').fillna(0)
    
    return df

# 데이터 로딩 시도
try:
    df_stock = load_stock_data()
except Exception as e:
    st.error(f"데이터를 불러오는 중 에러가 발생했습니다: {e}")
    st.stop()


# 3. 사이드바 (왼쪽 메뉴) 구성
st.sidebar.header("🔍 검색 필터")

# 브랜드 목록 추출 (중복 제거 후 가나다 정렬, 맨 앞에 '전체보기' 추가)
brand_list = ["전체보기"] + sorted(list(df_stock['브랜드'].unique()))
selected_brand = st.sidebar.selectbox("브랜드를 선택하세요", brand_list)


# 4. 메인 화면 구성
st.title("📦 자사 재고 현황")

# 언제 업데이트된 데이터인지 표시
last_update_time = df_stock['업데이트 시간'].iloc[0] if not df_stock.empty else '정보 없음'
st.caption(f"최근 데이터 동기화: {last_update_time}")

st.markdown("---")

# 선택한 브랜드에 맞춰 데이터 필터링 (엑셀의 필터 기능과 동일)
if selected_brand == "전체보기":
    filtered_df = df_stock
else:
    filtered_df = df_stock[df_stock['브랜드'] == selected_brand]


# 5. 화면에 시각화 (차트 및 표)
st.subheader(f"📊 [{selected_brand}] 재고 수량 차트")

# 바 차트 (가로축: 품목명, 세로축: 현재재고)
chart_data = filtered_df.set_index('품목명')['현재재고']
st.bar_chart(chart_data)

st.subheader(f"📋 [{selected_brand}] 상세 재고 표")
# 표 출력 (업데이트 시간 같은 불필요한 열은 숨기고 핵심만 보여줌)
st.dataframe(filtered_df[['브랜드', '품목코드', '품목명', '현재재고']], use_container_width=True)