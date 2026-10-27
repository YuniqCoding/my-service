"""기능 화면(화면 1 · 2 · 3) 꾸밈 · 글자와 기능은 그대로 두고 CSS 만 입힌다.

idea/reference.txt 의 갤러리 바퀴에서 레이아웃 생각만 빌렸다.
- 밝은 무대 한 장에 내용을 가운데로 모은다
- 화면 2 실습 카드는 활 모양으로 놓는다
- 가리킨 카드만 또렷하고, 나머지 카드는 살짝 흐리고 작아진다
- 단추와 탭은 알약 모양이고, 고르지 않은 탭은 흐리게 보인다
"""
import streamlit as st

# 기능 화면 색 · 배경 · 글자 · 강조
BACKGROUND = "#2e7dbe"
TEXT = "#eb3e41"
ACCENT = "#fccd0f"

MAIN = '[data-testid="stMainBlockContainer"]'
SIDEBAR = '[data-testid="stSidebar"]'
# 한 줄에 놓인 카드 칸 · 화면 2 실습 카드와 화면 3 갤러리 카드
ROW = '[data-testid="stHorizontalBlock"]'
COLUMN = '[data-testid="stColumn"]'
# 화면 2 실습 카드 줄만 · 칸 안에 단추가 있는 줄
CARD_ROW = f"{ROW}:has(.stButton)"
# 테두리 있는 상자(st.container(border=True)) 의 판
BOX = '[data-testid="stLayoutWrapper"] > [data-testid="stVerticalBlock"]'

STYLE = f"""
<style>
.stApp {{ background: {BACKGROUND}; }}
[data-testid="stHeader"] {{ background: transparent; }}

/* 무대 · 가운데 하얀 판 한 장 */
{MAIN} {{
    background: #ffffff; border-radius: 28px; margin: 3.5rem auto 4rem; padding: 2.5rem 2.5rem 2rem;
    box-shadow: 0 24px 60px rgba(0, 0, 0, 0.22);
}}
{MAIN}, {MAIN} p, {MAIN} label, {SIDEBAR} p, {SIDEBAR} label {{ color: {TEXT}; }}
{MAIN} h1 {{ color: {TEXT}; text-align: center; letter-spacing: -0.02em; padding-top: 0.5rem; }}
{MAIN} [data-testid="stCaptionContainer"], {MAIN} [data-testid="stCaptionContainer"] p {{ color: {TEXT}; opacity: 0.6; }}

/* 사이드바 · 무대와 같은 하얀 판 */
{SIDEBAR} {{ background: rgba(255, 255, 255, 0.96); }}

/* 넣는 칸 · 둥글게 */
[data-testid="stTextInputRootElement"] {{ border-radius: 999px; overflow: hidden; }}
[data-testid="stFileUploaderDropzone"] {{ border-radius: 16px; border: 1.5px dashed {TEXT}55; }}

/* 단추 · 알약 모양 테두리 */
{MAIN} .stButton button, {SIDEBAR} .stButton button {{
    border-radius: 999px; border: 1px solid {TEXT}55; color: {TEXT}; background: #ffffff;
    padding: 0.4rem 1.4rem; transition: border-color 0.2s, transform 0.2s;
}}
{MAIN} .stButton button:hover, {SIDEBAR} .stButton button:hover {{ border-color: {TEXT}; color: {TEXT}; transform: translateY(-1px); }}

/* 주 단추 · 화면 1 [만들기] 와 화면 3 [올리기] 는 강조색으로 채운다 */
{MAIN}:has([data-testid="stTextInput"]) .stButton button,
{SIDEBAR} .stButton:not(.st-key-back_to_landing .stButton) button {{
    background: {ACCENT}; border-color: {ACCENT}; font-weight: 700; box-shadow: 0 4px 14px {ACCENT}88;
}}
{SIDEBAR} .st-key-back_to_landing button {{ background: #ffffff; border-color: {TEXT}55; box-shadow: none; font-weight: 400; }}
/* 화면 1 · 칸과 [만들기] 를 가운데로 */
{MAIN}:has([data-testid="stTextInput"]) .stElementContainer:has(> .stButton) {{ align-self: center; }}

/* 카드 · 둥근 판, 가리키면 그 카드만 또렷하고 나머지는 살짝 물러난다 */
{ROW} > {COLUMN} {{ transition: transform 0.35s, filter 0.35s; }}
{ROW}:has(> {COLUMN}:hover) > {COLUMN}:not(:hover) {{ filter: blur(1.5px) brightness(0.92) saturate(0.6); transform: scale(0.95); }}
{ROW} {BOX} {{
    border-radius: 18px; border-color: {TEXT}22; background: #ffffff; box-shadow: 0 8px 22px rgba(46, 125, 190, 0.18);
}}
{ROW} [data-testid="stImage"] img {{ border-radius: 12px; }}

/* 화면 2 실습 카드 · 세로로 긴 카드, 위에 강조색 띠, 실습 이름을 크게 */
{CARD_ROW} {{ align-items: flex-start; padding: 0.5rem 0 1.5rem; }}
{CARD_ROW} {BOX} {{
    min-height: 170px; border-top: 6px solid {ACCENT}; justify-content: center; text-align: center;
    background: linear-gradient(180deg, #ffffff 0%, #eef5fb 100%);
}}
{CARD_ROW} .stButton button {{ border: none; background: transparent; }}
{CARD_ROW} .stButton button p {{ font-size: 1.2rem; font-weight: 700; }}
{CARD_ROW} [data-testid="stCaptionContainer"] {{ text-align: center; }}

/* 화면 2 실습 카드 · 양 끝으로 갈수록 내려가고 기울어 활 모양이 된다 */
{CARD_ROW} > {COLUMN}:first-child:not(:last-child) {{ transform: translateY(26px) rotate(-5deg); }}
{CARD_ROW} > {COLUMN}:last-child:not(:first-child) {{ transform: translateY(26px) rotate(5deg); }}
{CARD_ROW} > {COLUMN}:nth-child(2):not(:nth-last-child(2)):not(:last-child) {{ transform: translateY(8px) rotate(-2deg); }}
{CARD_ROW} > {COLUMN}:nth-last-child(2):not(:nth-child(2)):not(:first-child) {{ transform: translateY(8px) rotate(2deg); }}
{CARD_ROW} > {COLUMN}:hover {{ transform: translateY(-6px) scale(1.04); z-index: 1; }}

/* 탭 · 알약 모양, 고른 탭만 또렷하게 */
{MAIN} [role="tablist"] {{ gap: 0.6rem; justify-content: center; padding-bottom: 0.6rem; }}
{MAIN} [role="tablist"]::after, {MAIN} [role="tab"] .react-aria-SelectionIndicator {{ display: none; }}
{MAIN} [role="tab"] {{
    border: 1px solid {TEXT}55; border-radius: 999px; padding: 0.35rem 1.3rem; opacity: 0.55; transition: opacity 0.3s;
}}
{MAIN} [role="tab"][aria-selected="true"] {{ opacity: 1; background: {ACCENT}; border-color: {ACCENT}; }}
{MAIN} [role="tab"], {MAIN} [role="tab"] p {{ color: {TEXT}; font-weight: 600; }}
</style>
"""


def apply_theme():
    """기능 화면에 꾸밈을 입힌다. 첫 화면(랜딩)에는 쓰지 않는다."""
    st.markdown(STYLE, unsafe_allow_html=True)
