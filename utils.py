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
        background-color: rgba(15, 23, 42, 0.75); /* 세련된 딥 다크 블루 배경 */
        backdrop-filter: blur(6px); /* 🚀 [핵심] 뒤쪽 화면을 뿌옇게 만들어주는 고급 블러 효과 */
        -webkit-backdrop-filter: blur(6px);
        z-index: 999999;
        display: flex; flex-direction: column; justify-content: center; align-items: center;
    }}
    
    .modern-spinner {{
        width: 75px; 
        height: 75px;
        border-radius: 50%;
        border: 5px solid rgba(255, 255, 255, 0.1); /* 투명한 바탕 링 */
        border-top-color: #3B82F6; /* 🚀 [포인트] 빛나는 블루 링 */
        animation: smoothSpin 1s cubic-bezier(0.55, 0.15, 0.45, 0.85) infinite; /* 부드러운 회전 */
        margin-bottom: 30px;
        box-shadow: 0 0 25px rgba(59, 130, 246, 0.5); /* 은은한 야광 글로우 효과 */
    }}
    
    .loading-text {{
        font-family: 'Pretendard', sans-serif;
        font-size: 1.6rem;
        font-weight: 700;
        color: #F8FAFC;
        text-shadow: 0 4px 10px rgba(0,0,0,0.5);
        animation: textPulse 1.5s ease-in-out infinite; /* 🚀 숨 쉬는 듯한 텍스트 깜빡임 */
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
        
        <div class="modern-spinner"></div>
        <div class="loading-text">{text}</div>
    </div>
    """
    
    placeholder = st.empty()
    placeholder.markdown(html_code, unsafe_allow_html=True)
    
    # 브라우저가 예쁜 팝업을 그릴 수 있도록 0.1초의 틈을 줍니다.
    time.sleep(0.1)
    
    try:
        yield
    finally:
        placeholder.empty()
