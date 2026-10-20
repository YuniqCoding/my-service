from datetime import datetime, timedelta, timezone
from pathlib import Path

import requests
import streamlit as st

# 이 파일과 같은 폴더의 .env 에서 Supabase 주소와 키를 찾는다
ENV_PATH = Path(__file__).parent / ".env"
# 글이 올라온 때는 한국 시간으로 보여 준다
KST = timezone(timedelta(hours=9))

st.set_page_config(page_title="한 줄 방명록")


def load_env():
    """.env 를 읽어 「이름=값」 줄만 모은다."""
    values = {}
    for line in ENV_PATH.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        name, value = line.split("=", 1)
        values[name.strip()] = value.strip()
    return values


env = load_env()
SUPABASE_URL = env.get("SUPABASE_URL", "").rstrip("/")
SUPABASE_ANON_KEY = env.get("SUPABASE_ANON_KEY", "")
if not SUPABASE_URL or not SUPABASE_ANON_KEY:
    st.error(".env 의 SUPABASE_URL 과 SUPABASE_ANON_KEY 에 값을 넣어 주세요")
    st.stop()

# guestbook 표의 주소와, 요청마다 같이 보내는 키
TABLE_URL = f"{SUPABASE_URL}/rest/v1/guestbook"
HEADERS = {"apikey": SUPABASE_ANON_KEY, "Authorization": f"Bearer {SUPABASE_ANON_KEY}"}

# 칸 아래에 띄울 안내 문구를 기억해 둔다
if "notice" not in st.session_state:
    st.session_state.notice = ""


def load_messages():
    """guestbook 표의 글을 새 글이 위로 오게 가져온다."""
    response = requests.get(
        TABLE_URL,
        headers=HEADERS,
        params={"select": "created_at,message", "order": "created_at.desc"},
        timeout=10,
    )
    response.raise_for_status()
    return response.json()


def write():
    """[남기기] · 글이 있으면 guestbook 표에 한 줄 쌓고, 없으면 안내 문구를 띄운다."""
    message = st.session_state.message.strip()
    if not message:
        st.session_state.notice = "한 줄을 적어 주세요"
        return
    try:
        response = requests.post(TABLE_URL, headers=HEADERS, json={"message": message}, timeout=10)
        response.raise_for_status()
    except requests.RequestException as error:
        st.session_state.notice = f"글을 남기지 못했습니다 · {error}"
        return
    # 남긴 뒤에는 칸과 안내 문구를 비운다
    st.session_state.notice = ""
    st.session_state.message = ""


st.title("한 줄 방명록")

# 넣는 자리 · 칸 이름은 칸 안에 흐리게 보인다
st.text_input("한 줄 남기기", placeholder="한 줄 남기기", label_visibility="collapsed", key="message")

# 안내 자리 · 비워 두고 누르거나 글을 남기지 못하면 보인다
if st.session_state.notice:
    st.error(st.session_state.notice)

# 단추 · 글이 있으면 아래에 한 줄 쌓인다
st.button("남기기", on_click=write)

# 방명록 · guestbook 표에 쌓인 글을 보여 준다
try:
    messages = load_messages()
except requests.RequestException as error:
    st.error(f"방명록을 불러오지 못했습니다 · {error}")
    st.stop()

st.caption(f"{len(messages)}줄" if messages else "아직 남긴 글이 없습니다")
for row in messages:
    with st.container(border=True):
        st.text(row["message"])
        written_at = datetime.fromisoformat(row["created_at"]).astimezone(KST)
        st.caption(written_at.strftime("%Y-%m-%d %H:%M"))
