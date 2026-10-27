"""화면 오른쪽 아래에 떠 있는 상담 챗봇 · 아이콘을 누르면 대화창이 열리고, PRD.md 를 근거로 Claude 가 답한다."""
import base64
import io
from datetime import datetime, timedelta, timezone
from pathlib import Path

import anthropic
import requests
import streamlit as st
from PIL import Image

# Claude 공식 안내(claude-api)대로 지금 기본으로 쓰는 모델
CLAUDE_MODEL = "claude-opus-5-5"
# 세 줄짜리 상담 답이라 깊게 생각할 필요가 없어, 생각의 깊이(effort)를 가장 낮게 둔다
CLAUDE_EFFORT = "low"
# AI에게 주는 고정 지시문 · 글자를 고칠 때는 이 파일만 고친다 ({{PRD}} 자리에 PRD.md 가 들어간다)
PROMPT_PATH = Path(__file__).parent / "chatbot_prompt.md"
# 챗봇이 답할 때 근거로 삼는 서비스 설명서
PRD_PATH = Path(__file__).parent / "PRD.md"
# 챗봇 얼굴 그림
BOT_IMAGE_PATH = Path(__file__).parent / "bot.png"
# 대화창에서 고를 수 있는 말투 · 이름 → AI에게 줄 설명 (맨 앞이 처음에 골라져 있는 말투)
TONES = {
    "친절한 존댓말": "말끝을 「~요」「~세요」로 맺는 부드러운 존댓말로 쓴다.",
    "짧고 단정하게": "꾸미는 말을 빼고 「~합니다」「~하세요」로 맺는 짧고 단정한 존댓말로 쓴다.",
    "친구처럼 반말": "친한 친구에게 말하듯 「~해」「~야」로 맺는 다정한 반말로 쓴다.",
    "아이에게 말하듯": "초등학생도 알아듣게 쉬운 낱말을 골라, 다정한 존댓말로 쓴다.",
}
# 물은 말과 받은 답을 남기는 Supabase 표 이름
LOG_TABLE = "chat_logs"
# 지난 대화 목록에 보여 줄 줄 수 (새 대화가 위로)
LOG_LIMIT = 20
# 지난 대화의 시각은 한국 시간으로 보여 준다
KST = timezone(timedelta(hours=9))
# 답 점검 · 이 글자로 시작하는 답은 줄 수 · 글자 수를 보지 않고 통과시킨다
UNSURE_PREFIX = "[확실하지 않은 내용이에요]"
# 답 점검 · 답이 넘으면 안 되는 글자 수 (줄바꿈은 세지 않는다)
ANSWER_MAX_CHARS = 300


@st.cache_resource
def bot_image():
    """bot.png 를 160px 로 줄여 한 번만 읽어 둔다. 원본은 커서 그대로 쓰면 화면이 느려진다."""
    image = Image.open(BOT_IMAGE_PATH)
    image.thumbnail((160, 160))
    return image


@st.cache_resource
def bot_image_url():
    """줄인 bot.png 를 CSS 에 바로 넣을 수 있는 글자(data URL)로 바꾼다."""
    buffer = io.BytesIO()
    bot_image().save(buffer, format="PNG")
    return "data:image/png;base64," + base64.b64encode(buffer.getvalue()).decode()


def system_instruction():
    """chatbot_prompt.md 를 읽어 {{PRD}} 자리에 PRD.md 전문을 끼워 넣는다.

    지시문 파일이 없으면 None 을 돌려준다 (대화창이 안내 문구를 띄운다).
    대화 하나에서는 처음 읽은 것을 끝까지 쓴다(chat_window 참고). 대화 중간에 이 글이 바뀌면
    Claude 가 앞에서 생각해 둔 내용을 버리게 되어서다. 두 파일을 고치면 새로 고친 화면의 새 대화부터 반영된다.
    """
    try:
        prompt = PROMPT_PATH.read_text(encoding="utf-8")
    except OSError:
        return None
    try:
        prd = PRD_PATH.read_text(encoding="utf-8")
    except OSError:
        prd = "(PRD.md 를 읽지 못했습니다)"
    # 파일 끝의 빈 줄은 빼고 쓴다
    return prompt.rstrip("\n").replace("{{PRD}}", prd)


def as_lines(text):
    """줄바꿈이 화면에서도 줄바꿈으로 보이게 한다. 그냥 두면 세 줄이 한 덩어리로 붙어 보인다."""
    return "  \n".join(text.splitlines())


# 아이콘을 오른쪽 아래에 띄우고, 동그랗게 만든다
CHATBOT_CSS = """
<style>
.st-key-chatbot {
    position: fixed;
    right: 28px;
    bottom: 28px;
    z-index: 1000;
    width: auto !important;
}
/* 동그란 버튼 한가운데에 bot.png 를 넣는다 */
.st-key-chatbot button {
    width: 96px;
    height: 96px;
    padding: 0;
    border-radius: 50%;
    /* 그림을 원보다 크게 넣어 얼굴과 윗몸이 크게 보이게 한다 (발끝은 원 밖으로 잘린다) */
    background: #e9faf3 url("BOT_IMAGE_URL") 50% 22% / 125% no-repeat;
    border: 2px solid #7fdcbf;
    box-shadow: 0 4px 14px rgba(0, 0, 0, 0.18);
    transition: transform 0.15s;
}
.st-key-chatbot button:hover {
    background-color: #d4f5e8;
    border-color: #3fc49c;
    transform: scale(1.06);
}
/* 버튼 글자(상담 챗봇)와 펼침 표시는 숨기고 그림만 보이게 한다 */
.st-key-chatbot button > * {
    visibility: hidden;
}
[data-testid="stPopoverBody"]:has(.st-key-chatbot_window) {
    width: 440px;
}
/* 대화창 안의 챗봇 얼굴도 키운다 */
.st-key-chatbot_window [data-testid="stChatMessage"] > div:first-child {
    width: 40px;
    height: 40px;
}
.st-key-chatbot_window [data-testid="stChatMessage"] > img:first-child,
.st-key-chatbot_window [data-testid="stChatMessage"] > div:first-child img {
    width: 40px;
    height: 40px;
}
/* [보내기] 글자가 두 줄로 꺾이지 않게 한다 */
.st-key-chatbot_window button p {
    white-space: nowrap;
}
</style>
"""


@st.cache_resource
def claude_client(api_key):
    """Claude 에 말을 보내는 창구를 한 번만 만들어 둔다."""
    # PRD.md 전문을 함께 보내서 답이 늦을 때가 있어, 넉넉히 기다린다
    return anthropic.Anthropic(api_key=api_key, timeout=120)


def ask_claude(api_key, system, history):
    """지금까지 나눈 말(history)을 통째로 Claude 에 보내고, 받은 답 전체를 돌려준다.

    Claude 는 앞의 말을 따로 기억하지 않아서, 매번 처음부터 끝까지 다시 보낸다.
    """
    return claude_client(api_key).beta.messages.create(
        model=CLAUDE_MODEL,
        max_tokens=16000,
        output_config={"effort": CLAUDE_EFFORT},
        # 같은 PRD.md 를 매번 보내니, 앞부분을 저장해 두고 다시 읽어 값을 아낀다
        cache_control={"type": "ephemeral"},
        system=system,
        messages=history,
        # Claude 가 안전 때문에 답을 거절하면, Anthropic 이 정한 다른 모델이 이어서 답한다
        betas=["server-side-fallback-2026-07-01"],
        fallbacks="default",
    )


def tone_message(tone):
    """고른 말투를 알려 주는 지시 한 줄 · 질문 바로 뒤에 붙여 보낸다.

    고정 지시문(system)은 대화 중간에 바꾸면 안 되어서, 말투는 이렇게 질문마다 따로 알려 준다.
    """
    return {
        "role": "system",
        "content": (
            f"[말투] 이번 답은 「{tone}」 말투로 쓴다. {TONES[tone]} "
            "세 줄 형식과 화면 · 버튼 · 칸 · 안내 문구의 글자는 그대로 지킨다."
        ),
    }


def answer_text(response):
    """받은 답에서 글자 부분만 이어 붙인다. (생각한 내용 등 다른 조각은 빼고)"""
    return "".join(block.text for block in response.content if block.type == "text")


def answer_ok(answer):
    """보여 주기 전 점검 · 빈 줄 없이 정확히 세 줄이고 300자 이하면 통과한다.

    "[확실하지 않은 내용이에요]" 로 시작하는 답은 줄 수 · 글자 수를 보지 않고 통과시킨다.
    """
    answer = answer.strip()
    if answer.startswith(UNSURE_PREFIX):
        return True
    lines = answer.splitlines()
    return (
        len(lines) == 3
        and all(line.strip() for line in lines)
        and len("".join(lines)) <= ANSWER_MAX_CHARS
    )


def usage_line(usage):
    """토큰 수를 한 줄 글로 바꾼다. 저장해 둔 앞부분을 다시 읽은 토큰은 따로 적는다."""
    cached = (usage.cache_read_input_tokens or 0) + (usage.cache_creation_input_tokens or 0)
    sent = usage.input_tokens + cached
    total = sent + usage.output_tokens
    return (
        f"이번 요청에 쓴 토큰 · 모두 {total:,}"
        f" (보낸 말 {sent:,} · 그중 저장해 둔 것 다시 읽음 {usage.cache_read_input_tokens or 0:,}"
        f" · 받은 답 {usage.output_tokens:,})"
    )


def save_log(supabase, tone, question, answer):
    """물은 말과 받은 답을 chat_logs 표에 한 줄 남긴다. 못 남기면 False 를 돌려준다."""
    url, key = supabase
    try:
        response = requests.post(
            f"{url}/rest/v1/{LOG_TABLE}",
            headers={"apikey": key, "Authorization": f"Bearer {key}"},
            json={"tone": tone, "question": question, "answer": answer},
            timeout=10,
        )
        response.raise_for_status()
    except requests.RequestException:
        return False
    return True


def load_logs(supabase):
    """chat_logs 표에서 최근 대화를 새것부터 가져온다. 못 가져오면 None 을 돌려준다."""
    url, key = supabase
    try:
        response = requests.get(
            f"{url}/rest/v1/{LOG_TABLE}",
            headers={"apikey": key, "Authorization": f"Bearer {key}"},
            params={"select": "created_at,tone,question,answer", "order": "id.desc", "limit": LOG_LIMIT},
            timeout=10,
        )
        response.raise_for_status()
        return response.json()
    except (requests.RequestException, ValueError):
        return None


def show_logs(supabase):
    """대화창 아래 · 지난 대화 목록 (눌러야 펼쳐진다)"""
    with st.expander("지난 대화"):
        logs = load_logs(supabase)
        if logs is None:
            st.caption("지난 대화를 불러오지 못했습니다")
            return
        if not logs:
            st.caption("아직 남은 대화가 없습니다")
            return
        for row in logs:
            with st.container(border=True):
                written_at = datetime.fromisoformat(row["created_at"]).astimezone(KST)
                st.caption(f"{written_at:%Y-%m-%d %H:%M} · {row['tone'] or '말투 없음'}")
                st.text(f"물은 말 · {row['question']}")
                st.write(as_lines(row["answer"]))


def send_question(api_key, supabase, tone, question, history):
    """[보내기] · 물은 말을 Claude 에 보내 답을 보여 주고, 대화에 쌓고, 표에 남긴다."""
    if not api_key:
        st.error("ANTHROPIC_API_KEY 가 비어 있어 보낼 수 없습니다")
        return
    if st.session_state.chatbot_system is None:
        st.error("chatbot_prompt.md 를 읽지 못해 보낼 수 없습니다")
        return
    if not question.strip():
        st.error("물어볼 말을 넣어 주세요")
        return

    question = question.strip()
    new_history = st.session_state.chatbot_history + [
        {"role": "user", "content": question},
        tone_message(tone),
    ]
    with history:
        with st.chat_message("user"):
            st.write(question)
        with st.chat_message("assistant", avatar=bot_image()):
            try:
                with st.spinner("답을 기다리는 중입니다"):
                    response = ask_claude(api_key, st.session_state.chatbot_system, new_history)
                    # 점검에 걸리면 같은 말로 한 번 더 묻는다
                    if response.stop_reason != "refusal" and not answer_ok(answer_text(response)):
                        response = ask_claude(api_key, st.session_state.chatbot_system, new_history)
            except anthropic.RateLimitError:
                st.error("답을 받지 못했습니다 · 요청이 너무 많습니다. 잠시 뒤에 다시 보내 주세요")
                return
            except anthropic.APIStatusError as error:
                st.error(f"답을 받지 못했습니다 · {error.status_code} · {error.message}")
                return
            except anthropic.APIConnectionError:
                st.error("답을 받지 못했습니다 · 인터넷 연결을 확인해 주세요")
                return
            # 다른 모델까지 모두 답을 거절했을 때 · 이 말은 대화에 남기지 않는다
            if response.stop_reason == "refusal":
                st.error("이 말에는 답할 수 없습니다. 다르게 물어봐 주세요")
                return
            answer = answer_text(response) or "(받은 답에 글자가 없습니다)"
            # 두 번 다 점검에 걸렸을 때 · 답은 보여 주지 않고, 이 말은 대화에 남기지 않는다
            if not answer_ok(answer):
                st.error("다시 시도해 주세요")
                return
            st.caption("AI가 쓴 초안입니다 · 확인하고 쓰세요")
            st.write(as_lines(answer))
            st.caption(usage_line(response.usage))
            # 표에 못 남겨도 대화는 이어 간다
            if not save_log(supabase, tone, question, answer):
                st.caption("이 대화는 지난 대화 목록에 남기지 못했습니다")

    st.session_state.chatbot_history = new_history + [
        {"role": "assistant", "content": response.content}
    ]
    st.session_state.chatbot_messages += [
        {"role": "user", "text": question},
        {"role": "assistant", "text": answer, "usage": response.usage},
    ]


@st.fragment
def chat_window(api_key, supabase):
    """대화창 · 말을 보내도 이 창만 다시 그려서, 뒤의 화면은 그대로 있고 창도 닫히지 않는다."""
    if "chatbot_messages" not in st.session_state:
        # 화면에 보여 줄 말
        st.session_state.chatbot_messages = []
        # Claude 에 다시 보낼 말 · 받은 답은 생각한 조각까지 고치지 않고 그대로 쌓는다
        st.session_state.chatbot_history = []
        # 이 대화에서 쓸 역할과 PRD.md · 대화 중간에 바뀌지 않게 처음 한 번만 읽는다
        st.session_state.chatbot_system = system_instruction()

    with st.container(key="chatbot_window"):
        st.markdown("**상담 챗봇**")

        # 말투 고르는 칸 · 대화 중간에 바꿔도 다음 답부터 바뀐 말투로 답한다
        tone = st.selectbox("말투", list(TONES), key="chatbot_tone")

        # 나눈 말 · 위에서부터 차례대로 쌓인다
        history = st.container(height=320)
        with history:
            if not st.session_state.chatbot_messages:
                with st.chat_message("assistant", avatar=bot_image()):
                    st.write("안녕하세요! 이 게시판 서비스에 대해 궁금한 것을 물어봐 주세요.")
            for message in st.session_state.chatbot_messages:
                avatar = bot_image() if message["role"] == "assistant" else None
                with st.chat_message(message["role"], avatar=avatar):
                    # AI의 답 위에는 안내 한 줄을 붙인다
                    if message["role"] == "assistant":
                        st.caption("AI가 쓴 초안입니다 · 확인하고 쓰세요")
                    st.write(as_lines(message["text"]))
                    if message.get("usage") is not None:
                        st.caption(usage_line(message["usage"]))

        # 넣는 자리 · 보낸 뒤에는 칸을 비운다
        with st.form("chatbot_form", clear_on_submit=True, border=False):
            left, right = st.columns([3, 1], vertical_alignment="bottom")
            question = left.text_input("물어볼 말", placeholder="물어볼 말", label_visibility="collapsed")
            sent = right.form_submit_button("보내기")

        if sent:
            send_question(api_key, supabase, tone, question, history)

        # 지난 대화 · 방금 보낸 말까지 들어가도록 보내기를 마친 뒤에 불러온다
        show_logs(supabase)


def show_chatbot(api_key, supabase_url, supabase_key):
    """화면 오른쪽 아래에 챗봇 아이콘을 둔다. 누르면 대화창이 열린다."""
    st.markdown(CHATBOT_CSS.replace("BOT_IMAGE_URL", bot_image_url()), unsafe_allow_html=True)
    with st.container(key="chatbot"):
        with st.popover("상담 챗봇", help="상담 챗봇"):
            chat_window(api_key, (supabase_url.rstrip("/"), supabase_key))
