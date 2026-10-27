import streamlit as st

# 첫 화면 색 · 배경 · 글자 · 강조
BACKGROUND = "#2e7dbe"
TEXT = "#eb3e41"
ACCENT = "#fccd0f"

# 하는 일 세 가지 · PRD.md 「3. 범위 → 넣을 기능」 그대로
FEATURES = [
    "실습 번호를 넣으면 실습마다 결과물 게시판이 한 번에 생긴다",
    "게시판에 이름 · 사진 · 한 줄 설명을 올린다",
    "올라온 결과물을 갤러리처럼 모아 본다",
]

STYLE = f"""
<style>
.stApp {{ background: {BACKGROUND}; }}
[data-testid="stSidebar"], [data-testid="stSidebarCollapsedControl"] {{ display: none; }}
.landing {{ color: {TEXT}; text-align: center; padding-top: 3rem; }}
.landing h1 {{ color: {TEXT}; font-size: 3.2rem; margin-bottom: 0.4rem; }}
.landing .intro {{ font-size: 1.25rem; margin-bottom: 2.5rem; }}
.landing .features {{ display: flex; gap: 1rem; flex-wrap: wrap; justify-content: center; margin-bottom: 2.5rem; }}
.landing .feature {{
    flex: 1 1 200px; max-width: 240px; background: #ffffff; border-top: 6px solid {ACCENT};
    border-radius: 12px; padding: 1.2rem 1rem; text-align: left; font-size: 1rem; line-height: 1.5;
}}
.landing .feature b {{ display: block; color: {ACCENT}; font-size: 1.8rem; -webkit-text-stroke: 1px {TEXT}; }}
.st-key-start {{ display: flex; justify-content: center; }}
.st-key-start button {{
    background: {ACCENT}; color: {TEXT}; border: none; font-size: 1.2rem; font-weight: 700;
    padding: 0.7rem 2.6rem; border-radius: 999px;
}}
.st-key-start button:hover {{ background: #ffffff; color: {TEXT}; }}
.st-key-start button p {{ font-size: 1.2rem; font-weight: 700; }}
</style>
"""


def start():
    """[시작하기] · 첫 화면을 닫고 기능 화면(화면 1)으로 간다."""
    st.session_state.started = True


def back_to_landing():
    """[← 첫 화면으로] · 기능 화면을 닫고 첫 화면으로 돌아간다."""
    st.session_state.started = False


def show_landing():
    """첫 화면 · 큰 제목, 한 줄 소개, 하는 일 세 가지, [시작하기]"""
    features = "".join(
        f'<div class="feature"><b>{number}</b>{text}</div>' for number, text in enumerate(FEATURES, start=1)
    )
    st.markdown(STYLE, unsafe_allow_html=True)
    st.markdown(
        '<div class="landing">'
        "<h1>실습 게시판</h1>"
        '<div class="intro">실습 번호만 넣으면 실습마다 결과물 게시판이 한 번에 생깁니다.</div>'
        f'<div class="features">{features}</div>'
        "</div>",
        unsafe_allow_html=True,
    )
    st.button("시작하기", key="start", on_click=start)
