import streamlit as st
import time
from contextlib import contextmanager

@contextmanager
def custom_fullscreen_spinner(text="로딩 중입니다..."):
    """화면 전체를 덮는 고급스러운 커스텀 로딩 팝업"""
    
    # 🚀 [핵심] 파이썬 들여쓰기 때문에 HTML이 텍스트로 깨지는 버그를 막기 위해
    # 아래 HTML 코드는 무조건 '왼쪽 끝'에 딱 붙여서 작성해야 합니다!
    html_code = f"""
<style>
.fs-overlay {{
    position: fixed; top: 0px; left: 0px; width: 100vw; height: 100vh;
    background-color: rgba(15, 23, 42, 0.8) !important;
    backdrop-filter: blur(8px) !important;
    -webkit-backdrop-filter: blur(8px) !important;
    z-index: 999999 !important;
    display: flex !important; flex-direction: column !important; 
    justify-content: center !important; align-items: center !important;
}}
.fs-spinner {{
    display: block !important;
    width: 70px !important; height: 70px !important;
    border: 6px solid rgba(255, 255, 255, 0.1) !important;
    border-top: 6px solid #3B82F6 !important;
    border-radius: 50% !important;
    animation: fs-spin 1s cubic-bezier(0.5, 0.1, 0.5, 0.9) infinite !important;
    margin-bottom: 25px !important;
    box-sizing: border-box !important;
}}
.fs-text {{
    font-family: 'Pretendard', sans-serif !important;
    font-size: 1.6rem !important; font-weight: 700 !important; color: #ffffff !important;
    animation: fs-pulse 1.5s ease-in-out infinite !important;
    text-shadow: 0 2px 10px rgba(0,0,0,0.5) !important;
}}
@keyframes fs-spin {{ 0% {{ transform: rotate(0deg); }} 100% {{ transform: rotate(360deg); }} }}
@keyframes fs-pulse {{ 0%, 100% {{ opacity: 1; }} 50% {{ opacity: 0.5; }} }}
</style>

<div class="fs-overlay">
    <span class="fs-spinner" style="color: transparent; overflow: hidden;">.</span>
    <div class="fs-text">{text}</div>
</div>
"""
    
    placeholder = st.empty()
    placeholder.markdown(html_code, unsafe_allow_html=True)
    
    # 브라우저가 화면을 렌더링할 시간을 0.1초 보장
    time.sleep(0.1)
    
    try:
        yield
    finally:
        placeholder.empty()
