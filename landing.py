import base64
from pathlib import Path

import streamlit as st

# 첫 화면 색 · 배경 · 글자 · 강조
BACKGROUND = "#2e7dbe"
TEXT = "#eb3e41"
ACCENT = "#fccd0f"

# 히어로 배경 영상 · app.py 와 같은 폴더
HERO_VIDEO = Path(__file__).parent / "hero.mp4"

# 하는 일 세 가지 · PRD.md 「3. 범위 → 넣을 기능」 그대로
FEATURES = [
    "실습 번호를 넣으면 실습마다 결과물 게시판이 한 번에 생긴다",
    "게시판에 이름 · 사진 · 한 줄 설명을 올린다",
    "올라온 결과물을 갤러리처럼 모아 본다",
]

STYLE = f"""
<style>
.stApp {{ background: {BACKGROUND}; }}
[data-testid="stHeader"] {{ background: transparent; }}
[data-testid="stSidebar"], [data-testid="stSidebarCollapsedControl"] {{ display: none; }}
/* 영상은 화면 전체 뒤에 깔고, 글자와 버튼은 그 위에 올린다 */
[data-testid="stMain"] {{ position: relative; z-index: 0; background: transparent; }}
.hero-video {{ position: fixed; inset: 0; width: 100vw; height: 100vh; object-fit: cover; z-index: -1; }}
.landing {{ color: {TEXT}; text-align: center; text-shadow: 0 2px 12px rgba(0, 0, 0, 0.35); }}
.landing.hero {{ padding-top: 22vh; }}
.landing h1 {{ color: {TEXT}; font-size: 3.6rem; margin-bottom: 0.4rem; }}
.landing .intro {{ font-size: 1.3rem; font-weight: 600; margin-bottom: 1.5rem; }}
.landing.below {{ text-shadow: none; padding-top: 22vh; }}
.landing .features {{ display: flex; gap: 1rem; flex-wrap: wrap; justify-content: center; margin-bottom: 2.5rem; }}
.landing .feature {{
    flex: 1 1 200px; max-width: 240px; background: #ffffff; border-top: 6px solid {ACCENT};
    border-radius: 12px; padding: 1.2rem 1rem; text-align: left; font-size: 1rem; line-height: 1.5;
}}
.landing .feature b {{ display: block; color: {ACCENT}; font-size: 1.8rem; -webkit-text-stroke: 1px {TEXT}; }}
.st-key-start {{ align-self: center; }}
.st-key-start button {{
    background: {ACCENT}; color: {TEXT}; border: none; font-size: 1.2rem; font-weight: 700;
    padding: 0.7rem 2.6rem; border-radius: 999px; box-shadow: 0 4px 16px rgba(0, 0, 0, 0.25);
}}
.st-key-start button:hover {{ background: #ffffff; color: {TEXT}; }}
.st-key-start button p {{ font-size: 1.2rem; font-weight: 700; }}
</style>
"""


@st.cache_data
def hero_video_src():
    """hero.mp4 를 페이지 안에 바로 넣을 수 있는 글자(data 주소)로 바꾼다. 파일이 없으면 빈 글자."""
    if not HERO_VIDEO.is_file():
        return ""
    return "data:video/mp4;base64," + base64.b64encode(HERO_VIDEO.read_bytes()).decode()


def start():
    """[시작하기] · 첫 화면을 닫고 기능 화면(화면 1)으로 간다."""
    st.session_state.started = True


def back_to_landing():
    """[← 첫 화면으로] · 기능 화면을 닫고 첫 화면으로 돌아간다."""
    st.session_state.started = False


def show_landing():
    """첫 화면 · 영상 배경 위에 큰 제목, 한 줄 소개, [시작하기] · 그 아래 하는 일 세 가지"""
    features = "".join(
        f'<div class="feature"><b>{number}</b>{text}</div>' for number, text in enumerate(FEATURES, start=1)
    )
    st.markdown(STYLE, unsafe_allow_html=True)

    # 히어로 · 소리 없이(muted) 자동 재생(autoplay) · 끝나면 처음부터(loop)
    src = hero_video_src()
    video = f'<video class="hero-video" src="{src}" autoplay muted loop playsinline></video>' if src else ""
    st.markdown(
        video + '<div class="landing hero">'
        "<h1>실습 게시판</h1>"
        '<div class="intro">실습 번호만 넣으면 실습마다 결과물 게시판이 한 번에 생깁니다.</div>'
        "</div>",
        unsafe_allow_html=True,
    )
    st.button("시작하기", key="start", on_click=start)

    st.markdown(f'<div class="landing below"><div class="features">{features}</div></div>', unsafe_allow_html=True)
