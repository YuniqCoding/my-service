from pathlib import Path

import pandas as pd
import requests
import streamlit as st

from chatbot import show_chatbot

# 이 파일과 같은 폴더의 .env 에서 Supabase 주소와 키를 찾는다
ENV_PATH = Path(__file__).parent / ".env"

st.set_page_config(page_title="실습 결과물 게시판 만들기")


def load_env():
    """.env 를 읽어 「이름=값」 줄만 모은다."""
    values = {}
    if not ENV_PATH.is_file():
        return values
    for line in ENV_PATH.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        name, value = line.split("=", 1)
        values[name.strip()] = value.strip()
    return values


env = load_env()
SUPABASE_ANON_KEY = env.get("SUPABASE_ANON_KEY", "")
# submissions 표의 주소와, 요청마다 같이 보내는 키
TABLE_URL = f"{env.get('SUPABASE_URL', '').rstrip('/')}/rest/v1/submissions"
HEADERS = {"apikey": SUPABASE_ANON_KEY, "Authorization": f"Bearer {SUPABASE_ANON_KEY}"}


def load_saved():
    """submissions 표에 쌓인 결과물을 올린 차례대로 가져온다. 못 가져오면 빈 채로 둔다."""
    try:
        response = requests.get(
            TABLE_URL,
            headers=HEADERS,
            params={"select": "id,practice_no,comment", "order": "id.asc"},
            timeout=10,
        )
        response.raise_for_status()
        return response.json()
    except (requests.RequestException, ValueError):
        return []


saved = load_saved()

# 지금 보여 줄 화면 번호와, 화면 3에서 보여 줄 실습 번호를 기억해 둔다
if "screen" not in st.session_state:
    st.session_state.screen = 1
if "practice" not in st.session_state:
    st.session_state.practice = 1
# 만든 게시판 개수, 화면에서 올린 결과물, 칸 아래에 띄울 안내 문구를 기억해 둔다
if "board_count" not in st.session_state:
    st.session_state.board_count = 0
if "uploads" not in st.session_state:
    st.session_state.uploads = {}
if "notice" not in st.session_state:
    st.session_state.notice = ""
# 올린 뒤 사진 칸을 비우려고 사진 칸의 이름을 바꿔 준다
if "photo_round" not in st.session_state:
    st.session_state.photo_round = 0


def go(screen, practice=None):
    """보여 줄 화면을 바꾼다."""
    st.session_state.screen = screen
    st.session_state.notice = ""
    if practice is not None:
        st.session_state.practice = practice


def make_boards():
    """[만들기] · 넣은 실습 번호만큼 게시판을 만들고, 못 만들면 안내 문구를 띄운다."""
    try:
        count = int(st.session_state.number.strip())
    except ValueError:
        st.session_state.notice = "실습 번호를 넣어 주세요. 예: 3"
        return
    if not 1 <= count <= 20:
        st.session_state.notice = "1부터 20까지 넣어 주세요"
        return
    st.session_state.board_count = count
    go(2)


def upload():
    """[올리기] · 사진이 있으면 결과물 카드를 한 장 쌓고, 없으면 안내 문구를 띄운다."""
    photo = st.session_state.get(f"photo_{st.session_state.photo_round}")
    if photo is None:
        st.session_state.notice = "사진을 1장 올려 주세요"
        return
    # submissions 표에 실습 번호와 한 줄 설명을 한 줄 쌓는다 · 사진과 이름은 표에 넣지 않는다
    try:
        response = requests.post(
            TABLE_URL,
            headers={**HEADERS, "Prefer": "return=representation"},
            json={"practice_no": st.session_state.practice, "comment": st.session_state.comment.strip() or None},
            timeout=10,
        )
        response.raise_for_status()
        saved_id = response.json()[0]["id"]
    except (requests.RequestException, ValueError, LookupError):
        st.session_state.notice = "결과물을 저장하지 못했습니다"
        return
    st.session_state.uploads.setdefault(st.session_state.practice, []).append(
        {
            "id": saved_id,
            "이름": st.session_state.name,
            "사진": photo.getvalue(),
            "파일 이름": photo.name,
            "한 줄 설명": st.session_state.comment,
        }
    )
    # 올린 뒤에는 칸과 안내 문구를 비운다
    st.session_state.notice = ""
    st.session_state.name = ""
    st.session_state.comment = ""
    st.session_state.photo_round += 1


def cards_of(number):
    """그 실습의 결과물 카드를 submissions 표에 쌓인 차례대로 모은다."""
    # 이번에 화면에서 올린 것은 사진과 이름까지, 그 전에 올린 것은 표에 남은 한 줄 설명만 보인다
    uploads = {card["id"]: card for card in st.session_state.uploads.get(number, [])}
    cards = [
        uploads.pop(row["id"], None) or {"이름": "", "사진": "", "한 줄 설명": row["comment"] or ""}
        for row in saved
        if row["practice_no"] == number
    ]
    return cards + list(uploads.values())


def cards_to_csv(number, cards):
    """지금 갤러리에 보이는 결과물 카드를 CSV 글자로 바꾼다. 사진은 파일 이름만 담는다."""
    rows = [
        {
            "실습": f"실습 {number}",
            "이름": card["이름"],
            "사진": card.get("파일 이름", card["사진"]),
            "한 줄 설명": card["한 줄 설명"],
        }
        for card in cards
    ]
    # 엑셀에서 한글이 깨지지 않게 utf-8-sig 로 내보낸다
    return pd.DataFrame(rows).to_csv(index=False).encode("utf-8-sig")


def screen_1():
    """화면 1 · 넣는 화면"""
    st.title("실습 결과물 게시판 만들기")

    # 넣는 자리 · 칸 이름은 칸 안에 흐리게 보인다
    st.text_input("실습 번호 (예: 3)", placeholder="실습 번호 (예: 3)", label_visibility="collapsed", key="number")

    # 안내 자리 · 비워 두거나 1부터 20 밖의 숫자를 넣고 누르면 보인다
    if st.session_state.notice:
        st.error(st.session_state.notice)

    # 단추 · 넣은 번호가 맞으면 화면 2로 넘어간다
    st.button("만들기", on_click=make_boards)


def screen_2():
    """화면 2 · 나오는 화면"""
    st.button("← 처음으로", on_click=go, args=(1,))

    st.title("만들어진 결과물 게시판")

    # 넣은 실습 번호만큼 카드를 놓는다 · 카드 안의 실습 이름을 누르면 화면 3으로 넘어간다
    numbers = list(range(1, st.session_state.board_count + 1))
    per_row = 5  # 한 줄에 다섯 장까지 놓고, 넘으면 다음 줄로 내린다
    for start in range(0, len(numbers), per_row):
        row_numbers = numbers[start:start + per_row]
        for number, column in zip(row_numbers, st.columns(min(len(numbers), per_row))):
            with column:
                with st.container(border=True):
                    st.button(f"실습 {number}", on_click=go, args=(3, number), width="stretch")
                    count = len(cards_of(number))
                    st.caption(f"결과물 {count}개" if count else "빈 게시판")


def screen_3():
    """화면 3 · 올리고 모아 보는 화면"""
    st.button("← 게시판 목록으로", on_click=go, args=(2,))

    st.title(f"「실습 {st.session_state.practice}」 결과물 게시판")

    # 넣는 자리 · 사진은 한 번에 1장
    st.text_input("이름", key="name")
    st.file_uploader(
        "사진 (파일 선택)",
        type=["png", "jpg", "jpeg", "gif", "webp"],
        key=f"photo_{st.session_state.photo_round}",
    )
    st.text_input("한 줄 설명", key="comment")

    # 안내 자리 · 사진 없이 누르면 보인다
    if st.session_state.notice:
        st.error(st.session_state.notice)

    # 단추 · 사진이 있으면 아래 갤러리에 카드가 한 장 쌓인다
    st.button("올리기", on_click=upload)

    # 갤러리 · 이 실습에 올라온 결과물을 카드로 보여 준다
    cards = cards_of(st.session_state.practice)

    # 단추 · 지금 갤러리에 보이는 결과물을 파일 하나로 내려받는다
    if cards:
        st.download_button(
            "결과물 내려받기",
            data=cards_to_csv(st.session_state.practice, cards),
            file_name=f"실습{st.session_state.practice}_결과물.csv",
            mime="text/csv",
        )

    with st.container(border=True):
        if not cards:
            st.caption("빈 게시판")
        columns = st.columns(2)
        for index, card in enumerate(cards):
            with columns[index % 2]:
                with st.container(border=True):
                    # 사진은 이번에 화면에서 올린 카드에만 있다
                    if card["사진"]:
                        st.image(card["사진"])
                    # 이름과 한 줄 설명은 비어 있으면 건너뛴다
                    words = [word.strip() for word in (card["이름"], card["한 줄 설명"]) if word.strip()]
                    st.text(" · ".join(words))


# 왼쪽 사이드바 · 서비스 설명 한 줄
st.sidebar.write("실습 번호만 넣으면 실습마다 결과물 게시판이 한 번에 생깁니다.")

if st.session_state.screen == 2:
    screen_2()
elif st.session_state.screen == 3:
    screen_3()
else:
    screen_1()

# 오른쪽 아래 상담 챗봇 · 세 화면 어디서나 보인다
show_chatbot(env.get("ANTHROPIC_API_KEY", ""), env.get("SUPABASE_URL", ""), SUPABASE_ANON_KEY)
