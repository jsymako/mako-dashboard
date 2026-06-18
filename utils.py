import streamlit as st
import time
from contextlib import contextmanager

@contextmanager
def custom_fullscreen_spinner(text="로딩 중입니다..."):
    """화면 전체를 덮는 고급스러운 커스텀 로딩 팝업"""
    
    html_code = f"""
    <style>
    .fullscreen-overlay {{
        position: fixed; top: 0; left: 0; width: 100vw; height: 100vh;
        background-color: rgba(15, 23, 42, 0.75) !important;
        backdrop-filter: blur(6px) !important;
        -webkit-backdrop-filter: blur(6px) !important;
        z-index: 999999 !important;
        display: flex !important; flex-direction: column !important; justify-content: center !important; align-items: center !important;
    }}
    
    .modern-spinner {{
        width: 75px !important; 
        height: 75px !important;
        border-radius: 50% !important;
        border: 6px solid rgba(255, 255, 255, 0.1) !important;
        border-top: 6px solid #3B82F6 !important;
        animation: smoothSpin 1s cubic-bezier(0.55, 0.15, 0.45, 0.85) infinite !important;
        margin-bottom: 30px !important;
        box-shadow: 0 0 25px rgba(59, 130, 246, 0.5) !important;
        display: flex !important;
        color: transparent !important; /* 🚀 안의 투명 글자가 보이지 않게 처리 */
    }}
    
    .loading-text {{
        font-family: 'Pretendard', sans-serif !important;
        font-size: 1.6rem !important;
        font-weight: 700 !important;
        color: #F8FAFC !important;
        text-shadow: 0 4px 10px rgba(0,0,0,0.5) !important;
        animation: textPulse 1.5s ease-in-out infinite !important;
    }}
    
    @keyframes smoothSpin {{
        0% {{ transform: rotate(0deg); }}
        100% {{ transform: rotate(360deg); }}
    }}
    
    @keyframes textPulse {{
        0%, 100% {{ opacity: 1; transform: scale(1); }}
        50% {{ opacity: 0.6; transform: scale(0.98); }}
    }}
    </style>
    
    <div class="fullscreen-overlay">
        <table style="display: none;"><tr><td>백신</td></tr></table>
        
        <div class="modern-spinner">&nbsp;</div>
        
        <div class="loading-text">{text}</div>
    </div>
    """
    
    placeholder = st.empty()
    placeholder.markdown(html_code, unsafe_allow_html=True)
    
    # 🚀 브라우저가 화면을 그릴 수 있는 시간을 확실하게 보장
    time.sleep(0.1)
    
    try:
        yield
    finally:
        placeholder.empty()
