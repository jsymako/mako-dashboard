# utils.py
import streamlit as st
import time
from contextlib import contextmanager

@contextmanager
def custom_fullscreen_spinner(text="로딩 중입니다..."):
    """화면 전체를 덮는 커스텀 로딩 팝업 컨텍스트 매니저"""
    
    # 1. 팝업 CSS 및 HTML 정의
    html_code = f"""
    <style>
    .fullscreen-overlay {{
        position: fixed; top: 0; left: 0; width: 100vw; height: 100vh;
        background-color: rgba(0, 0, 0, 0.7);
        z-index: 999999;
        display: flex; flex-direction: column; justify-content: center; align-items: center;
        color: white;
    }}
    .custom-spinner {{
        border: 8px solid rgba(255, 255, 255, 0.2);
        border-top: 8px solid #ffffff;
        border-radius: 50%;
        width: 65px; height: 65px;
        animation: spin 1s linear infinite;
        margin-bottom: 25px;
        box-shadow: 0 0 15px rgba(0,0,0,0.5);
    }}
    @keyframes spin {{
        0% {{ transform: rotate(0deg); }}
        100% {{ transform: rotate(360deg); }}
    }}
    </style>
    <div class="fullscreen-overlay">
        <table style="display: none;"><tr><td>백신</td></tr></table>
        
        <div class="custom-spinner"></div>
        <h2 style="font-weight: 600; text-shadow: 1px 1px 5px rgba(0,0,0,0.8);">{text}</h2>
    </div>
    """
    
    # 2. 플레이스홀더를 만들고 팝업 렌더링 (화면 덮기 시작)
    placeholder = st.empty()
    placeholder.markdown(html_code, unsafe_allow_html=True)
    
    # 🚀 [함정 2 돌파] 컴퓨터가 무거운 계산을 시작하기 전에, 브라우저가 화면에 팝업을 그릴 수 있는 시간을 딱 '0.1초' 부여합니다.
    time.sleep(0.1)
    
    try:
        # 3. 실제 작업(데이터 로딩, 연산 등) 실행
        yield
    finally:
        # 4. 작업이 끝나면 팝업 삭제
        placeholder.empty()
