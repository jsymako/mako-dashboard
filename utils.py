import streamlit as st
import time
from contextlib import contextmanager

@contextmanager
def custom_fullscreen_spinner(text="로딩 중입니다..."):
    """화면 전체를 덮는 고급스러운 커스텀 로딩 팝업"""
    
    # 🚀 [최종 완결판 패치 포인트]
    # 1. 제가 실수로 지웠던 '가짜 table(백신)'을 다시 부활시켰습니다. (style.css 숨김 방어)
    # 2. 스트림릿이 코드를 마크다운 텍스트로 오해하지 못하도록 모든 코드를 줄바꿈 없이 한 줄로 묶었습니다.
    # 3. 빈 div 삭제 방지용 투명 텍스트(.) 포함
    
    html_code = (
        "<style>"
        ".fs-overlay { position: fixed; top: 0; left: 0; width: 100vw; height: 100vh; background-color: rgba(15, 23, 42, 0.75) !important; backdrop-filter: blur(6px) !important; -webkit-backdrop-filter: blur(6px) !important; z-index: 999999 !important; display: flex !important; flex-direction: column !important; justify-content: center !important; align-items: center !important; }"
        ".fs-spinner { width: 75px !important; height: 75px !important; border: 6px solid rgba(255, 255, 255, 0.1) !important; border-top: 6px solid #3B82F6 !important; border-radius: 50% !important; animation: fs-spin 1s cubic-bezier(0.55, 0.15, 0.45, 0.85) infinite !important; margin-bottom: 25px !important; box-shadow: 0 0 25px rgba(59, 130, 246, 0.5) !important; color: transparent !important; user-select: none !important; display: flex !important; align-items: center !important; justify-content: center !important; }"
        ".fs-text { font-family: 'Pretendard', sans-serif !important; font-size: 2.1rem !important; font-weight: 700 !important; color: #F8FAFC !important; text-shadow: 0 4px 10px rgba(0,0,0,0.5) !important; animation: fs-pulse 1.5s ease-in-out infinite !important; margin: 0 !important; padding: 0 !important; }"
        "@keyframes fs-spin { 0% { transform: rotate(0deg); } 100% { transform: rotate(360deg); } }"
        "@keyframes fs-pulse { 0%, 100% { opacity: 1; } 50% { opacity: 0.6; } }"
        "</style>"
        "<div class='fs-overlay'>"
        "<table style='display:none;'><tr><td>백신</td></tr></table>"
        "<div class='fs-spinner'>.</div>"
        f"<div class='fs-text'>{text}</div>"
        "</div>"
    )
    
    placeholder = st.empty()
    placeholder.markdown(html_code, unsafe_allow_html=True)
    
    # 파이썬이 연산을 시작하기 전, 브라우저가 예쁜 화면을 그릴 수 있도록 0.1초 멈춤
    time.sleep(0.1)
    
    try:
        yield
    finally:
        placeholder.empty()
