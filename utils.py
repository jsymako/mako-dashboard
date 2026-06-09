# utils.py
import streamlit as st
from contextlib import contextmanager

@contextmanager
def custom_fullscreen_spinner(text="로딩 중입니다..."):
    """화면 전체를 덮는 커스텀 로딩 팝업 컨텍스트 매니저"""
    
    # 1. 팝업 CSS 및 HTML 정의
    html_code = f"""
    <style>
    .fullscreen-overlay {{
        position: fixed; top: 0; left: 0; width: 100vw; height: 100vh;
        background-color: rgba(0, 0, 0, 0.6);
        z-index: 999999;
        display: flex; flex-direction: column; justify-content: center; align-items: center;
        color: white;
    }}
    .custom-spinner {{
        border: 8px solid rgba(255, 255, 255, 0.3);
        border-top: 8px solid #ffffff;
        border-radius: 50%;
        width: 60px; height: 60px;
        animation: spin 1s linear infinite;
        margin-bottom: 20px;
    }}
    @keyframes spin {{
        0% {{ transform: rotate(0deg); }}
        100% {{ transform: rotate(360deg); }}
    }}
    </style>
    <div class="fullscreen-overlay">
        <div class="custom-spinner"></div>
        <h2>{text}</h2>
    </div>
    """
    
    # 2. 플레이스홀더를 만들고 팝업 렌더링 (화면 덮기 시작)
    placeholder = st.empty()
    placeholder.markdown(html_code, unsafe_allow_html=True)
    
    try:
        # 3. yield는 "이 블록 안의 실제 작업(코드)을 실행하라"는 뜻입니다.
        yield
    finally:
        # 4. 실제 작업이 성공하든, 에러가 나서 뻗든 무조건 마지막에 팝업을 지웁니다.
        placeholder.empty()
