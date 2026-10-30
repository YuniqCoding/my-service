import requests
import streamlit as st

from env_keys import load_env

# Gemini 공식 문서(ai.google.dev/gemini-api/docs/text-generation · interactions)의 주소와 모델 이름
GEMINI_URL = "https://generativelanguage.googleapis.com/v1beta/interactions"
GEMINI_MODEL = "gemini-3.8-flash"

st.set_page_config(page_title="챗봇")


def ask_gemini(api_key, question):
    """넣은 말을 Gemini 에 보내고, 받은 답의 글자와 토큰 수(usage)를 돌려준다."""
    response = requests.post(
        GEMINI_URL,
        headers={"x-goog-api-key": api_key, "Content-Type": "application/json"},
        json={"model": GEMINI_MODEL, "input": question},
        timeout=120,
    )
    if not response.ok:
        # 키는 빼고, Gemini 가 알려 준 까닭만 보여 준다
        try:
            body = response.json()
            # 잘못된 요청은 [{"error": …}] 처럼 목록으로 올 때도 있다
            if isinstance(body, list):
                body = body[0]
            reason = body["error"]["message"]
        except (ValueError, KeyError, TypeError, IndexError):
            reason = response.text[:200]
        raise RuntimeError(f"{response.status_code} · {reason}")
    body = response.json()
    # 답은 type 이 model_output 인 단계의 content 안, type 이 text 인 칸에 있다
    texts = [
        block["text"]
        for step in body.get("steps", [])
        if step.get("type") == "model_output"
        for block in step.get("content", [])
        if block.get("type") == "text"
    ]
    return "".join(texts), body.get("usage") or {}


def usage_line(usage):
    """토큰 수를 한 줄 글로 바꾼다. 받지 못한 값은 「확인 필요」 로 적는다."""
    def count(name):
        value = usage.get(name)
        return f"{value:,}" if isinstance(value, int) else "확인 필요"

    return (
        f"이번 요청에 쓴 토큰 · 모두 {count('total_tokens')}"
        f" (보낸 말 {count('total_input_tokens')} · 받은 답 {count('total_output_tokens')}"
        f" · 생각 {count('total_thought_tokens')})"
    )


st.title("챗봇")

# 키 값은 화면에 보여 주지 않고, 채워져 있는지만 알려 준다
api_key = load_env().get("GEMINI_API_KEY", "")
if api_key:
    st.success("GEMINI_API_KEY 가 채워져 있습니다")
else:
    st.error("GEMINI_API_KEY 가 비어 있습니다 · .env 에 값을 넣어 주세요")

# 넣는 자리 · 칸 이름은 칸 안에 흐리게 보인다
question = st.text_input("물어볼 말", placeholder="물어볼 말", label_visibility="collapsed")

# 단추 · 넣은 말을 Gemini 에 보내고, 받은 답을 아래에 보여 준다
if st.button("보내기"):
    if not api_key:
        st.error("GEMINI_API_KEY 가 비어 있어 보낼 수 없습니다")
    elif not question.strip():
        st.error("물어볼 말을 넣어 주세요")
    else:
        try:
            with st.spinner("답을 기다리는 중입니다"):
                answer, usage = ask_gemini(api_key, question.strip())
        except (requests.RequestException, RuntimeError, ValueError) as error:
            st.error(f"답을 받지 못했습니다 · {error}")
        else:
            st.write(answer or "(받은 답에 글자가 없습니다)")
            # 답 바로 아래 한 줄 · 이번 요청에 쓴 토큰 수
            st.caption(usage_line(usage))
