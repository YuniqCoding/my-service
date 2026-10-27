"""구독 정리함 · Supabase 의 subscriptions 표를 보여 주고, 줄을 더하고 · 고치고 · 지운다.

표에서 바로 고친 뒤 [저장] 을 누르면, 바뀐 줄만 골라 Supabase 에 넣기 · 고치기 · 지우기를 보낸다.
표는 02_output/subscriptions.sql 로 만든다.
"""
from datetime import date, timedelta
from pathlib import Path

import pandas as pd
import requests
import streamlit as st

# 이 파일과 같은 폴더의 .env 에서 Supabase 주소와 키를 찾는다
ENV_PATH = Path(__file__).parent / ".env"
# 표에서 쓰는 칸 · id 는 Supabase 가 붙이는 번호라 고치지 않는다
COLUMNS = ["id", "name", "category", "monthly_fee", "last_used"]
# 이 날수보다 오래 안 쓴 구독을 「안 쓰는 구독」 으로 센다
IDLE_DAYS = 30

st.set_page_config(page_title="구독 정리함", layout="wide")


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

# subscriptions 표의 주소와, 요청마다 같이 보내는 키
TABLE_URL = f"{SUPABASE_URL}/rest/v1/subscriptions"
HEADERS = {"apikey": SUPABASE_ANON_KEY, "Authorization": f"Bearer {SUPABASE_ANON_KEY}"}

# 저장 뒤에 띄울 안내 문구 · 표를 새로 그릴 때 바꾸는 번호
if "notice" not in st.session_state:
    st.session_state.notice = None
if "editor_version" not in st.session_state:
    st.session_state.editor_version = 0


def load_subs():
    """subscriptions 표를 월 요금이 비싼 순으로 가져온다 · 요금이 같으면 번호 순"""
    response = requests.get(
        TABLE_URL,
        headers=HEADERS,
        params={"select": ",".join(COLUMNS), "order": "monthly_fee.desc,id"},
        timeout=10,
    )
    response.raise_for_status()
    return response.json()


def to_payload(row):
    """한 줄을 Supabase 에 보낼 모양으로 바꾼다. 빈 칸이 있으면 None 을 돌려준다."""
    name, category = row["name"], row["category"]
    fee, used = row["monthly_fee"], row["last_used"]
    if any(pd.isna(value) for value in (name, category, fee, used)):
        return None
    if not str(name).strip() or not str(category).strip():
        return None
    return {
        "name": str(name).strip(),
        "category": str(category).strip(),
        "monthly_fee": int(fee),
        "last_used": pd.Timestamp(used).date().isoformat(),
    }


def save(rows, edited):
    """[저장] · 처음 받은 줄(rows)과 표에서 고친 줄(edited)을 견주어 바뀐 것만 보낸다."""
    before = {row["id"]: to_payload(row) for row in rows}
    kept_ids = set()
    added, changed = [], []
    for row in edited.to_dict("records"):
        payload = to_payload(row)
        if payload is None:
            return "error", "이름 · 분류 · 월 요금 · 마지막 사용일을 모두 채워 주세요"
        if pd.isna(row["id"]):
            added.append(payload)
            continue
        row_id = int(row["id"])
        kept_ids.add(row_id)
        if payload != before[row_id]:
            changed.append((row_id, payload))
    deleted = [row_id for row_id in before if row_id not in kept_ids]

    if not (added or changed or deleted):
        return "info", "바뀐 줄이 없습니다"
    try:
        if added:
            requests.post(TABLE_URL, headers=HEADERS, json=added, timeout=10).raise_for_status()
        for row_id, payload in changed:
            requests.patch(
                TABLE_URL, headers=HEADERS, params={"id": f"eq.{row_id}"}, json=payload, timeout=10
            ).raise_for_status()
        if deleted:
            ids = ",".join(str(row_id) for row_id in deleted)
            requests.delete(TABLE_URL, headers=HEADERS, params={"id": f"in.({ids})"}, timeout=10).raise_for_status()
    except requests.RequestException as error:
        return "error", f"저장하지 못했습니다 · {error}"
    return "success", f"저장했습니다 · 더한 줄 {len(added)} · 고친 줄 {len(changed)} · 지운 줄 {len(deleted)}"


def show_summary(table):
    """요약 숫자 · 구독 개수, 한 달 합계, 오래 안 쓴 구독"""
    idle_since = date.today() - timedelta(days=IDLE_DAYS)
    idle = table[table["last_used"] < idle_since]
    a, b, c = st.columns(3)
    a.metric("구독", f"{len(table):,}개")
    b.metric("한 달 합계", f"{int(table['monthly_fee'].sum()):,}원", help=f"1년이면 {int(table['monthly_fee'].sum()) * 12:,}원")
    c.metric(
        f"{IDLE_DAYS}일 넘게 안 쓴 구독",
        f"{len(idle):,}개",
        help=f"한 달 {int(idle['monthly_fee'].sum()):,}원 · 마지막 사용일이 {idle_since.isoformat()} 보다 앞선 줄",
    )
    if not idle.empty:
        st.caption("오래 안 쓴 구독 · " + " · ".join(idle.sort_values("last_used")["name"]))


st.title("구독 정리함")

try:
    rows = load_subs()
except requests.RequestException as error:
    st.error(f"subscriptions 표를 불러오지 못했습니다 · {error}")
    st.caption("표가 아직 없다면 02_output/subscriptions.sql 을 Supabase SQL Editor 에서 먼저 실행해 주세요")
    st.stop()

table = pd.DataFrame(rows, columns=COLUMNS)
table["last_used"] = pd.to_datetime(table["last_used"]).dt.date

if rows:
    show_summary(table)
else:
    st.info("아직 구독이 없습니다 · 표 맨 아래 줄에 넣고 [저장] 을 눌러 주세요")

st.caption("칸을 눌러 고치고 · 맨 아래 빈 줄에 더하고 · 줄 왼쪽을 골라 휴지통으로 지운 뒤 [저장] 을 누르세요")
edited = st.data_editor(
    table,
    key=f"subs_editor_{st.session_state.editor_version}",
    num_rows="dynamic",
    hide_index=True,
    use_container_width=True,
    column_config={
        "id": st.column_config.NumberColumn("번호", disabled=True),
        "name": st.column_config.TextColumn("이름", required=True),
        "category": st.column_config.TextColumn("분류", required=True),
        "monthly_fee": st.column_config.NumberColumn("월 요금", min_value=0, step=1, format="%d원", required=True),
        "last_used": st.column_config.DateColumn("마지막 사용일", format="YYYY-MM-DD", required=True),
    },
)

if st.button("저장", type="primary"):
    st.session_state.notice = save(rows, edited)
    # 저장했으면 표를 Supabase 에서 다시 받아 새로 그린다
    if st.session_state.notice[0] == "success":
        st.session_state.editor_version += 1
        st.rerun()

# 안내 자리 · [저장] 을 누른 결과가 보인다
if st.session_state.notice:
    kind, text = st.session_state.notice
    getattr(st, kind)(text)
    st.session_state.notice = None
