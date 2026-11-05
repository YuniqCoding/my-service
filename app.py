import pandas as pd
import requests
import streamlit as st

from chatbot import show_chatbot
from env_keys import load_env
from landing import back_to_landing, show_landing
from theme import apply_theme

st.set_page_config(page_title="실습 게시판", page_icon="❤️")

# 처음 열면 첫 화면(랜딩)부터 보여 주고, [시작하기]를 누르기 전에는 아래 기능 화면을 그리지 않는다
if not st.session_state.get("started"):
    show_landing()
    st.stop()

# 기능 화면 꾸밈 · 글자와 기능은 그대로 두고 색과 배치만 바꾼다
apply_theme()

# [시작하기] 뒤에는 구글 계정으로 들어와야 기능 화면이 보인다 · 키는 .streamlit/secrets.toml 의 [auth.google]
if not st.user.is_logged_in:
    st.title("구글 계정으로 들어오기")
    st.button("구글 계정으로 들어오기", on_click=st.login, args=("google",))
    st.stop()


env = load_env()
SUPABASE_ANON_KEY = env.get("SUPABASE_ANON_KEY", "")
# submissions 표의 주소와, 요청마다 같이 보내는 키
TABLE_URL = f"{env.get('SUPABASE_URL', '').rstrip('/')}/rest/v1/submissions"
HEADERS = {"apikey": SUPABASE_ANON_KEY, "Authorization": f"Bearer {SUPABASE_ANON_KEY}"}
# 구글 계정에서 메일을 못 받아 owner 를 정할 수 없을 때 띄우는 안내
EMAIL_NOTICE = "구글 계정 메일을 확인하지 못했습니다. 로그아웃 뒤 다시 들어와 주세요"


def load_saved():
    """submissions 표에 쌓인 결과물을 올린 차례대로 가져온다. 못 가져오면 빈 채로 둔다."""
    try:
        response = requests.get(
            TABLE_URL,
            headers=HEADERS,
            params={"select": "id,practice_no,comment,owner", "order": "id.asc"},
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
    # owner 칸에는 로그인한 사람의 구글 메일을 적는다 · 메일을 못 받으면 올리지 않는다
    owner = current_owner()
    if not owner:
        st.session_state.notice = EMAIL_NOTICE
        return
    # submissions 표에 실습 번호 · 한 줄 설명 · 메일(owner)을 한 줄 쌓는다 · 사진은 표에 넣지 않는다
    try:
        response = requests.post(
            TABLE_URL,
            headers={**HEADERS, "Prefer": "return=representation"},
            json={
                "practice_no": st.session_state.practice,
                "comment": st.session_state.comment.strip() or None,
                "owner": owner,
            },
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
            "owner": owner,
            "이름": my_name(),
            "사진": photo.getvalue(),
            "파일 이름": photo.name,
            "한 줄 설명": st.session_state.comment,
        }
    )
    # 올린 뒤에는 칸과 안내 문구를 비운다
    st.session_state.notice = ""
    st.session_state.comment = ""
    st.session_state.photo_round += 1


def is_admin():
    """들어온 사람의 구글 메일이 st.secrets 의 ADMIN_EMAILS 목록에 있으면 관리자다."""
    emails = st.secrets.get("ADMIN_EMAILS", [])
    # 목록 대신 "a@x.com, b@y.com" 처럼 한 줄 글자로 넣어도 읽는다
    if isinstance(emails, str):
        emails = emails.split(",")
    my_email = (st.user.get("email") or "").strip().lower()
    return bool(my_email) and my_email in {str(email).strip().lower() for email in emails}


def current_owner():
    """owner 칸에 적고 거를 때 쓰는 값 · 로그인한 사람의 구글 메일. 못 받으면 빈 글자."""
    return (st.user.get("email") or "").strip().lower()


def my_name():
    """카드에 보여 줄 이름 · 구글 계정 이름. 없으면 메일."""
    return st.user.get("name") or st.user.get("email") or ""


def same_owner(value, owner):
    """표에 앞뒤 빈칸이나 대문자가 섞여 들어간 owner 도 같은 메일로 본다."""
    return (value or "").strip().lower() == owner


def cards_of(number):
    """그 실습의 결과물을 submissions 표에 쌓인 차례대로 모은다.
    일반 사용자는 owner 가 내 메일인 줄만, 관리자는 전체를 본다. 이미 쌓인 줄은 읽기만 한다."""
    owner = current_owner()
    admin = is_admin()
    # 관리자가 아닌데 메일을 못 받으면 아무것도 보여 주지 않는다
    if not admin and not owner:
        return []

    def mine(value):
        return admin or same_owner(value, owner)

    # 이번에 화면에서 올린 것은 사진까지, 그 전에 올린 것은 표에 남은 owner 와 한 줄 설명만 보인다
    uploads = {card["id"]: card for card in st.session_state.uploads.get(number, []) if mine(card["owner"])}
    cards = []
    for row in saved:
        if row["practice_no"] != number or not mine(row.get("owner")):
            continue
        card = uploads.pop(row["id"], None) or {
            "owner": (row.get("owner") or "").strip(),
            "이름": my_name(),
            "사진": "",
            "한 줄 설명": row["comment"] or "",
        }
        cards.append(card)
    cards += list(uploads.values())
    # 관리자는 여러 사람 것을 함께 보므로 카드에 owner(메일, 예전 줄은 그때 넣은 이름)를 그대로 보여 준다
    if admin:
        cards = [{**card, "이름": card["owner"]} for card in cards]
    return cards


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
    st.write("실습 번호를 넣으면 결과물 게시판을 만들어 드립니다")

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

    # 넣는 자리는 왼쪽 사이드바에 두고, 가운데는 갤러리가 다 쓴다
    with st.sidebar:
        # 넣는 자리 · 사진은 한 번에 1장 · 이름 칸은 두지 않고 구글 계정 메일로 owner 를 적는다
        st.file_uploader(
            "사진 (파일 선택)",
            type=["png", "jpg", "jpeg", "gif", "webp"],
            key=f"photo_{st.session_state.photo_round}",
        )
        st.text_input("한 줄 설명", key="comment")

        # 안내 자리 · 사진 없이 누르면 보인다
        if st.session_state.notice:
            st.error(st.session_state.notice)

        # 단추 · 사진이 있으면 가운데 갤러리에 카드가 한 장 쌓인다
        st.button("올리기", on_click=upload)

    # 갤러리 · 이 실습에 올라온 결과물을 카드로 보여 준다
    cards = cards_of(st.session_state.practice)

    # 자주 보는 갤러리는 첫 탭, 가끔 쓰는 내려받기는 둘째 탭
    gallery_tab, download_tab = st.tabs(["결과물 모아 보기", "내려받기"])

    with gallery_tab:
        with st.container(border=True):
            # 관리자가 아닌데 메일을 못 받으면 목록 대신 안내를 띄운다
            if not current_owner() and not is_admin():
                st.error(EMAIL_NOTICE)
            elif not cards:
                st.caption("빈 게시판")
            per_row = 4  # 한 줄에 네 장씩 놓아 한 화면에 더 많이 보이게 한다
            columns = st.columns(per_row)
            for index, card in enumerate(cards):
                with columns[index % per_row]:
                    with st.container(border=True):
                        # 사진은 이번에 화면에서 올린 카드에만 있다
                        if card["사진"]:
                            st.image(card["사진"])
                        # 이름과 한 줄 설명은 비어 있으면 건너뛴다
                        words = [word.strip() for word in (card["이름"], card["한 줄 설명"]) if word.strip()]
                        st.text(" · ".join(words))

    # 단추 · 지금 갤러리에 보이는 결과물을 파일 하나로 내려받는다
    with download_tab:
        if not current_owner() and not is_admin():
            st.error(EMAIL_NOTICE)
        elif cards:
            st.download_button(
                "결과물 내려받기",
                data=cards_to_csv(st.session_state.practice, cards),
                file_name=f"실습{st.session_state.practice}_결과물.csv",
                mime="text/csv",
            )
        else:
            st.caption("빈 게시판")


def admin_screen():
    """관리 화면 · 관리자만 본다"""
    # 화면을 부르는 쪽에서 막더라도, 여기서 한 번 더 확인해 관리자가 아니면 아래 코드를 돌리지 않는다
    if not is_admin():
        st.stop()
    st.write("관리자만 보는 화면입니다")

    # 표 · submissions 표에서 모든 사람의 줄을 지금 다시 읽어 그대로 보여 준다 · 값을 바꾸거나 채우지 않는다
    try:
        response = requests.get(
            TABLE_URL,
            headers=HEADERS,
            params={"select": "id,practice_no,comment,owner", "order": "id.asc"},
            timeout=10,
        )
        response.raise_for_status()
        rows = response.json()
    except (requests.RequestException, ValueError):
        # 못 읽었을 때 빈 표를 보여 주면 줄이 없는 것처럼 보이므로, 표 대신 안내를 띄운다
        st.error("submissions 표를 읽지 못했습니다")
        return

    table = pd.DataFrame(rows, columns=["id", "practice_no", "comment", "owner"])
    st.caption(f"모든 사람의 줄 {len(table)}개")
    st.dataframe(table, hide_index=True)

    # 단추 · 위 표와 같은 줄을 CSV 파일 하나로 내려받는다 · 엑셀에서 한글이 깨지지 않게 utf-8-sig
    st.download_button(
        "전체 줄 CSV 내려받기",
        data=table.to_csv(index=False).encode("utf-8-sig"),
        file_name="submissions_전체.csv",
        mime="text/csv",
        key="admin_csv",
    )


# 왼쪽 사이드바 · 서비스 설명 한 줄
st.sidebar.write("실습 번호만 넣으면 실습마다 결과물 게시판이 한 번에 생깁니다.")
# 단추 · 첫 화면(랜딩)으로 돌아간다 · 세 화면 모두
st.sidebar.button("← 첫 화면으로", key="back_to_landing", on_click=back_to_landing)
# 단추 · 관리 화면으로 간다 · 관리자에게만 보인다
admin = is_admin()
if admin:
    st.sidebar.button("관리", key="go_admin", on_click=go, args=("admin",))

def sign_out():
    """[로그아웃] · 기억해 둔 것을 비우고 st.logout 으로 나간다 · 다시 열면 로그인 전 첫 화면(랜딩)부터 보인다"""
    st.session_state.clear()
    st.logout()


# 화면 맨 위 · 구글 계정으로 들어온 사람의 이름과 그 옆 [로그아웃] (세 화면 모두)
name_column, logout_column = st.columns([4, 1], vertical_alignment="center")
with name_column:
    st.caption(f"{st.user.get('name') or st.user.get('email', '')} 님")
with logout_column:
    st.button("로그아웃", key="sign_out", on_click=sign_out)

# 관리 화면은 관리자일 때만 부른다 · 관리자가 아니면 화면 1을 보여 준다
if st.session_state.screen == "admin" and admin:
    admin_screen()
elif st.session_state.screen == 2:
    screen_2()
elif st.session_state.screen == 3:
    screen_3()
else:
    screen_1()

# 화면 맨 아래 · 저작권 한 줄 (세 화면 모두)
st.caption("© 2026 실습 게시판 · 최유라")
# 화면 맨 아래 · 마지막으로 고친 날 한 줄 (세 화면 모두)
st.caption("마지막으로 고친 날 2026-11-03 · 기능 화면 안내 글을 넣음")

# 오른쪽 아래 상담 챗봇 · 세 화면 어디서나 보인다
show_chatbot(env.get("ANTHROPIC_API_KEY", ""), env.get("SUPABASE_URL", ""), SUPABASE_ANON_KEY)
