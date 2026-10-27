"""사진 보관함 · Supabase Storage 의 photos 버킷에 그림을 올리고, 올라와 있는 그림을 모두 보여 준다.

허용 규칙은 02_output/photos_storage.sql 로 넣는다 (올리기 · 목록 보기만 열려 있다).
"""
from datetime import datetime, timedelta, timezone
from pathlib import Path
from uuid import uuid4

import requests
import streamlit as st

# 이 파일과 같은 폴더의 .env 에서 Supabase 주소와 키를 찾는다
ENV_PATH = Path(__file__).parent / ".env"
# 그림을 올리는 버킷 이름
BUCKET = "photos"
# 올릴 수 있는 그림 종류
IMAGE_TYPES = ["png", "jpg", "jpeg", "gif", "webp"]
# 한 줄에 보여 줄 그림 수 · 그림 한 장의 가로 크기(픽셀)
GRID_COLUMNS = 3
THUMB_WIDTH = 200
# 올라온 때는 한국 시간으로 보여 준다
KST = timezone(timedelta(hours=9))

# 가운데 좁은 화면 · 세 칸이 작게 붙어 나란히 보인다
st.set_page_config(page_title="사진 보관함")


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

# Storage 주소들과, 요청마다 같이 보내는 키
STORAGE_URL = f"{SUPABASE_URL}/storage/v1/object"
LIST_URL = f"{STORAGE_URL}/list/{BUCKET}"
PUBLIC_URL = f"{STORAGE_URL}/public/{BUCKET}"
HEADERS = {"apikey": SUPABASE_ANON_KEY, "Authorization": f"Bearer {SUPABASE_ANON_KEY}"}

# 올린 뒤에 띄울 안내 문구 · 파일 고르는 칸을 비울 때 바꾸는 번호
if "notice" not in st.session_state:
    st.session_state.notice = None
if "uploader_version" not in st.session_state:
    st.session_state.uploader_version = 0


def load_photos():
    """photos 버킷의 그림을 새 그림이 위로 오게 가져온다. 폴더와 숨은 파일(. 으로 시작)은 뺀다."""
    response = requests.post(
        LIST_URL,
        headers=HEADERS,
        json={"prefix": "", "limit": 1000, "offset": 0, "sortBy": {"column": "created_at", "order": "desc"}},
        timeout=10,
    )
    response.raise_for_status()
    return [item for item in response.json() if item.get("id") and not item["name"].startswith(".")]


def upload(photo):
    """[올리기] · 고른 그림을 photos 버킷에 올린다.

    Storage 는 한글 파일 이름을 받지 않을 수 있고, 같은 이름은 덮어쓸 수 없으므로
    「올린 시각-무작위 8자리.확장자」 로 이름을 새로 붙인다.
    """
    extension = Path(photo.name).suffix.lower()
    name = f"{datetime.now(KST):%Y%m%d-%H%M%S}-{uuid4().hex[:8]}{extension}"
    try:
        response = requests.post(
            f"{STORAGE_URL}/{BUCKET}/{name}",
            headers={**HEADERS, "Content-Type": photo.type or "application/octet-stream"},
            data=photo.getvalue(),
            timeout=30,
        )
        response.raise_for_status()
    except requests.RequestException as error:
        return "error", f"그림을 올리지 못했습니다 · {error}"
    return "success", f"올렸습니다 · {photo.name}"


st.title("사진 보관함")

# 넣는 자리 · 그림은 한 번에 1장
photo = st.file_uploader("그림 고르기", type=IMAGE_TYPES, key=f"photo_{st.session_state.uploader_version}")
if st.button("올리기", type="primary"):
    if photo is None:
        st.session_state.notice = ("error", "사진을 1장 올려 주세요")
    else:
        st.session_state.notice = upload(photo)
        # 올렸으면 파일 고르는 칸을 비우고 목록을 다시 받는다
        if st.session_state.notice[0] == "success":
            st.session_state.uploader_version += 1
            st.rerun()

# 안내 자리 · [올리기] 를 누른 결과가 보인다
if st.session_state.notice:
    kind, text = st.session_state.notice
    getattr(st, kind)(text)
    st.session_state.notice = None

# 보관함 · photos 버킷에 올라와 있는 그림을 모두 보여 준다
try:
    photos = load_photos()
except requests.RequestException as error:
    st.error(f"그림 목록을 불러오지 못했습니다 · {error}")
    st.caption("허용 규칙이 없다면 02_output/photos_storage.sql 을 Supabase SQL Editor 에서 먼저 실행해 주세요")
    st.stop()

st.caption(f"{len(photos)}장" if photos else "아직 올라온 그림이 없습니다")
columns = st.columns(GRID_COLUMNS)
for index, item in enumerate(photos):
    with columns[index % GRID_COLUMNS].container(border=True):
        st.image(f"{PUBLIC_URL}/{item['name']}", width=THUMB_WIDTH)
        uploaded_at = datetime.fromisoformat(item["created_at"].replace("Z", "+00:00")).astimezone(KST)
        st.caption(f"{item['name']} · {uploaded_at:%Y-%m-%d %H:%M}")
