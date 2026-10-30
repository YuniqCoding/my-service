"""문서 보관함 · Supabase Storage 의 docs 버킷에 문서를 올리고, 문서마다 잠깐만 열리는 내려받기 링크를 보여 준다.

허용 규칙은 02_output/docs_storage.sql 로 넣는다 (올리기 · 목록 보기만 열려 있다).
내려받기 링크는 Supabase 가 서명해 준 주소라서 LINK_SECONDS 가 지나면 열리지 않는다.
"""
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path
from uuid import uuid4

import requests
import streamlit as st

from env_keys import load_env

# 문서를 올리는 버킷 이름
BUCKET = "docs"
# 올릴 수 있는 문서 종류
DOC_TYPES = ["pdf", "docx", "xlsx", "pptx", "hwp", "hwpx", "txt", "md", "csv"]
# 내려받기 링크가 열리는 시간(초)
LINK_SECONDS = 60
# 올라온 때는 한국 시간으로 보여 준다
KST = timezone(timedelta(hours=9))

st.set_page_config(page_title="문서 보관함")


env = load_env()
SUPABASE_URL = env.get("SUPABASE_URL", "").rstrip("/")
SUPABASE_ANON_KEY = env.get("SUPABASE_ANON_KEY", "")
if not SUPABASE_URL or not SUPABASE_ANON_KEY:
    st.error(".env 의 SUPABASE_URL 과 SUPABASE_ANON_KEY 에 값을 넣어 주세요")
    st.stop()

# Storage 주소들과, 요청마다 같이 보내는 키
STORAGE_URL = f"{SUPABASE_URL}/storage/v1"
LIST_URL = f"{STORAGE_URL}/object/list/{BUCKET}"
SIGN_URL = f"{STORAGE_URL}/object/sign/{BUCKET}"
HEADERS = {"apikey": SUPABASE_ANON_KEY, "Authorization": f"Bearer {SUPABASE_ANON_KEY}"}

# 올린 뒤에 띄울 안내 문구 · 파일 고르는 칸을 비울 때 바꾸는 번호
if "notice" not in st.session_state:
    st.session_state.notice = None
if "uploader_version" not in st.session_state:
    st.session_state.uploader_version = 0


def load_docs():
    """docs 버킷의 문서를 새 문서가 위로 오게 가져온다. 폴더와 숨은 파일(. 으로 시작)은 뺀다."""
    response = requests.post(
        LIST_URL,
        headers=HEADERS,
        json={"prefix": "", "limit": 1000, "offset": 0, "sortBy": {"column": "created_at", "order": "desc"}},
        timeout=10,
    )
    response.raise_for_status()
    return [item for item in response.json() if item.get("id") and not item["name"].startswith(".")]


def sign_links(names):
    """문서 이름마다 LINK_SECONDS 동안만 열리는 내려받기 링크를 한 번에 받는다."""
    if not names:
        return {}
    response = requests.post(
        SIGN_URL,
        headers=HEADERS,
        json={"expiresIn": LINK_SECONDS, "paths": names},
        timeout=10,
    )
    response.raise_for_status()
    # Supabase 는 「/object/sign/...?token=...」 처럼 앞 주소를 뺀 링크를 준다 · download 를 붙이면 열지 않고 내려받는다
    return {
        item["path"]: f"{STORAGE_URL}{item['signedURL']}&download="
        for item in response.json()
        if item.get("signedURL")
    }


def upload(doc):
    """[올리기] · 고른 문서를 docs 버킷에 올린다.

    Storage 는 한글 파일 이름을 받지 않을 수 있고, 같은 이름은 덮어쓸 수 없으므로
    「올린 시각-무작위 8자리-원래 이름의 영문 · 숫자.확장자」 로 이름을 새로 붙인다.
    """
    original = Path(doc.name)
    stem = re.sub(r"[^A-Za-z0-9_-]+", "", original.stem)[:40]
    name = f"{datetime.now(KST):%Y%m%d-%H%M%S}-{uuid4().hex[:8]}"
    name += f"-{stem}" if stem else ""
    name += original.suffix.lower()
    try:
        response = requests.post(
            f"{STORAGE_URL}/object/{BUCKET}/{name}",
            headers={**HEADERS, "Content-Type": doc.type or "application/octet-stream"},
            data=doc.getvalue(),
            timeout=60,
        )
        response.raise_for_status()
    except requests.RequestException as error:
        return "error", f"문서를 올리지 못했습니다 · {error}"
    return "success", f"올렸습니다 · {doc.name}"


def readable_size(size):
    """바이트 수를 KB · MB 로 읽기 쉽게 바꾼다."""
    if size >= 1024 * 1024:
        return f"{size / 1024 / 1024:.1f}MB"
    return f"{max(size / 1024, 0.1):.1f}KB"


st.title("문서 보관함")

# 넣는 자리 · 문서는 한 번에 1개
doc = st.file_uploader("문서 고르기", type=DOC_TYPES, key=f"doc_{st.session_state.uploader_version}")
if st.button("올리기", type="primary"):
    if doc is None:
        st.session_state.notice = ("error", "문서를 1개 골라 주세요")
    else:
        st.session_state.notice = upload(doc)
        # 올렸으면 파일 고르는 칸을 비우고 목록을 다시 받는다
        if st.session_state.notice[0] == "success":
            st.session_state.uploader_version += 1
            st.rerun()

# 안내 자리 · [올리기] 를 누른 결과가 보인다
if st.session_state.notice:
    kind, text = st.session_state.notice
    getattr(st, kind)(text)
    st.session_state.notice = None

# 보관함 · docs 버킷에 올라와 있는 문서와 내려받기 링크
try:
    docs = load_docs()
    links = sign_links([item["name"] for item in docs])
except requests.RequestException as error:
    st.error(f"문서 목록을 불러오지 못했습니다 · {error}")
    st.caption("허용 규칙이 없다면 02_output/docs_storage.sql 을 Supabase SQL Editor 에서 먼저 실행해 주세요")
    st.stop()

if not docs:
    st.caption("아직 올라온 문서가 없습니다")
    st.stop()

# 링크를 받은 때부터 LINK_SECONDS 뒤가 기한이다
expires_at = datetime.now(KST) + timedelta(seconds=LINK_SECONDS)
left, right = st.columns([3, 1])
left.caption(f"{len(docs)}개 · 링크는 {expires_at:%H:%M:%S} 까지 {LINK_SECONDS}초 동안만 열립니다")
# 다시 그리면 링크를 새로 받는다
right.button("링크 새로 받기")

for item in docs:
    with st.container(border=True):
        uploaded_at = datetime.fromisoformat(item["created_at"].replace("Z", "+00:00")).astimezone(KST)
        size = (item.get("metadata") or {}).get("size", 0)
        st.markdown(f"**{item['name']}**")
        st.caption(f"{readable_size(size)} · {uploaded_at:%Y-%m-%d %H:%M}")
        # 주소 글자를 그대로 보여 준다 · 누르면 내려받는다 · 주소 안의 _ 가 기울임꼴로 바뀌지 않게 ` 로 감싼다
        if item["name"] in links:
            url = links[item["name"]]
            st.markdown(f"[`{url}`]({url})")
        else:
            st.caption("링크를 받지 못했습니다")
