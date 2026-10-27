"""근처 맛집 대시보드 · 카카오 로컬 API 로 음식점을 찾아, 걸러 보고 · 줄 세우고 · 차트로 본다.

기준 장소(역 · 동네 이름)를 카카오에서 찾아 그 좌표를 중심으로 삼고, 고른 반경 안에서 고른 음식을 찾는다.
카카오는 [검색] 을 눌렀을 때만 부른다. 받은 결과는 화면에 남겨 두고, 걸러 보기 · 정렬은 그 결과만으로 한다.
"""
from pathlib import Path
from urllib.parse import quote

import altair as alt
import pandas as pd
import requests
import streamlit as st

# 이 파일과 같은 폴더의 .env 에서 카카오 키를 찾는다
ENV_PATH = Path(__file__).parent / ".env"

# 카카오 로컬 API 주소 · 카카오 공식 문서(developers.kakao.com/docs/ko/local/dev-guide) 기준
KEYWORD_URL = "https://dapi.kakao.com/v2/local/search/keyword.json"
CATEGORY_URL = "https://dapi.kakao.com/v2/local/search/category.json"
ADDRESS_URL = "https://dapi.kakao.com/v2/local/search/address.json"
# 네이버 지도 검색 주소 · 뒤에 「가게 이름 도로명 주소」 를 붙여 그 가게를 연다
NAVER_SEARCH_URL = "https://map.naver.com/p/search/"
# 기준 장소 칸의 처음 값 · 좌표는 지어내지 않고 카카오에서 받아 온다
DEFAULT_PLACE = "전주 객사"
# 찾을 음식 고르기 · 「음식점 전체」 는 검색어 없이 음식점 전체를 찾는다
ALL_FOOD = "음식점 전체"
FOODS = [ALL_FOOD, "한식", "중식", "일식", "양식", "분식", "국밥", "고기", "치킨"]
# 카카오 카테고리 코드 · FD6 = 음식점
RESTAURANT_CODE = "FD6"
# 카카오가 한 페이지에 주는 최대 개수(15) · 한 검색에서 볼 수 있는 최대 개수(45)
PAGE_SIZE = 15
MAX_RESULTS = 45
# 차트 막대 색 (한 가지 값만 보여 주는 차트라 한 색만 쓴다)
BAR_COLOR = "#2a78d6"

SORTS = {
    "가까운 순": ("distance", True),
    "먼 순": ("distance", False),
    "이름 순": ("place_name", True),
    "종류 순": ("kind", True),
}

st.set_page_config(page_title="근처 맛집 대시보드", layout="wide")


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


KAKAO_KEY = load_env().get("KAKAO_REST_API_KEY", "")


class KakaoError(Exception):
    """카카오에서 답을 못 받았을 때 · 화면에 보여 줄 글을 담는다."""


def call_kakao(url, params):
    """카카오 로컬 API 를 한 번 부르고 받은 JSON 을 돌려준다."""
    try:
        response = requests.get(
            url,
            headers={"Authorization": f"KakaoAK {KAKAO_KEY}"},
            params=params,
            timeout=10,
        )
    except requests.RequestException:
        raise KakaoError("카카오에 연결하지 못했습니다 · 인터넷 연결을 확인해 주세요")
    if response.status_code == 401:
        raise KakaoError("카카오 키가 맞지 않습니다 · .env 의 KAKAO_REST_API_KEY 를 확인해 주세요")
    if response.status_code == 429:
        raise KakaoError("요청이 너무 많습니다 · 잠시 뒤에 다시 눌러 주세요")
    if not response.ok:
        try:
            message = response.json().get("message", "")
        except ValueError:
            message = ""
        raise KakaoError(f"카카오에서 답을 받지 못했습니다 · {response.status_code} {message}".strip())
    return response.json()


def find_center(place):
    """기준 장소를 카카오에서 찾아 맨 위 결과를 중심으로 삼는다.

    장소 이름(역 · 건물)으로 먼저 찾고, 없으면 주소(동네 이름)로 찾는다.
    화면에 보여 줄 이름 · 주소 · 좌표는 모두 카카오가 준 값만 쓴다.
    """
    data = call_kakao(KEYWORD_URL, {"query": place, "size": 1})
    if data["documents"]:
        doc = data["documents"][0]
        return {
            "name": doc["place_name"],
            "address": doc["road_address_name"] or doc["address_name"],
            "category": doc["category_name"],
            "url": doc["place_url"],
            "x": doc["x"],
            "y": doc["y"],
        }
    data = call_kakao(ADDRESS_URL, {"query": place, "size": 1})
    if data["documents"]:
        doc = data["documents"][0]
        return {
            "name": doc["address_name"],
            "address": doc["address_name"],
            "category": "주소",
            "url": "",
            "x": doc["x"],
            "y": doc["y"],
        }
    raise KakaoError(f"「{place}」 를 카카오에서 찾지 못했습니다 · 역 이름이나 동네 이름을 조금 더 자세히 넣어 주세요 (예: 강남역, 전주 객사)")


def search_restaurants(center, keyword, radius):
    """중심에서 radius 미터 안 음식점을 찾는다. 검색어가 비면 음식점 전체를 찾는다.

    카카오는 한 번에 15개씩만 주므로, 마지막 페이지(is_end)가 나오거나 45개가 찰 때까지 이어 부른다.
    """
    params = {
        "category_group_code": RESTAURANT_CODE,
        "x": center["x"],
        "y": center["y"],
        "radius": radius,
        "size": PAGE_SIZE,
        "sort": "distance",
    }
    url = CATEGORY_URL
    if keyword:
        params["query"] = keyword
        url = KEYWORD_URL

    places, total = [], 0
    for page in range(1, MAX_RESULTS // PAGE_SIZE + 1):
        data = call_kakao(url, {**params, "page": page})
        places += data["documents"]
        total = data["meta"]["total_count"]
        if data["meta"]["is_end"]:
            break
    return places, total


def naver_url(name, road_address):
    """네이버 지도에서 그 가게를 찾는 링크 · 「가게 이름 도로명 주소」 를 띄어 이어 붙인다.

    카카오가 도로명 주소를 주지 않은 가게는 지어내지 않고 가게 이름만 붙인다.
    """
    words = f"{name} {road_address}".strip()
    return NAVER_SEARCH_URL + quote(words)


def to_table(places):
    """받은 장소 목록을 표로 바꾼다. 종류는 「음식점 > 한식 > 국밥」 의 두 번째 칸(한식)을 쓴다."""
    rows = []
    for place in places:
        parts = [part.strip() for part in place["category_name"].split(">")]
        rows.append({
            "place_name": place["place_name"],
            "kind": parts[1] if len(parts) > 1 else parts[0],
            "category_name": place["category_name"],
            "distance": int(place["distance"]) if place.get("distance") else None,
            "road_address_name": place["road_address_name"] or place["address_name"],
            "phone": place["phone"],
            "place_url": place["place_url"],
            "naver_url": naver_url(place["place_name"], place["road_address_name"]),
            "lat": float(place["y"]),
            "lon": float(place["x"]),
        })
    return pd.DataFrame(rows)


def run_search(place, keyword, radius):
    """[검색] · 카카오를 불러 결과를 화면 기억(session_state)에 남긴다."""
    if not place:
        st.error("기준 장소를 넣어 주세요 · 예: 강남역, 전주 객사")
        return
    if not KAKAO_KEY:
        st.error(".env 에 KAKAO_REST_API_KEY 가 없어 검색할 수 없습니다")
        return
    try:
        with st.spinner("카카오에서 찾는 중입니다"):
            center = find_center(place)
            places, total = search_restaurants(center, keyword, radius)
    except KakaoError as error:
        st.error(str(error))
        return
    st.session_state.lunch_search = {
        "place": place,
        "center": center,
        "keyword": keyword,
        "radius": radius,
        "total": total,
        "table": to_table(places),
    }


def bar_chart(data, field, title, sort):
    """가로 막대 차트 · 막대에 마우스를 올리면 개수가 보인다."""
    return (
        alt.Chart(data, title=title)
        .mark_bar(color=BAR_COLOR, cornerRadiusEnd=4)
        .encode(
            x=alt.X("가게 수:Q", axis=alt.Axis(tickMinStep=1, grid=True, gridOpacity=0.3)),
            y=alt.Y(f"{field}:N", sort=sort, title=None),
            tooltip=[alt.Tooltip(f"{field}:N"), alt.Tooltip("가게 수:Q")],
        )
    )


def show_charts(table):
    """종류별 가게 수 · 거리대별 가게 수 차트"""
    left, right = st.columns(2)

    kinds = table["kind"].value_counts().rename_axis("종류").reset_index(name="가게 수")
    left.altair_chart(bar_chart(kinds, "종류", "종류별 가게 수", "-x"), use_container_width=True)

    if table["distance"].notna().any():
        edges = [0, 100, 200, 300, 500, 700, 1000, 1500, 2000, 20000]
        names = [f"{lo}~{hi}m" if hi < 20000 else f"{lo}m 넘게" for lo, hi in zip(edges, edges[1:])]
        bands = pd.cut(table["distance"], bins=edges, labels=names, right=False)
        counts = bands.value_counts().reindex(names, fill_value=0)
        counts = counts[counts > 0].rename_axis("거리").reset_index(name="가게 수")
        right.altair_chart(bar_chart(counts, "거리", "거리대별 가게 수", list(counts["거리"])), use_container_width=True)


def show_dashboard(result):
    """검색 결과 · 요약 숫자, 걸러 보기 · 정렬, 차트, 지도, 표"""
    center, table = result["center"], result["table"]
    # 기준 장소 · 넣은 글자가 아니라 카카오가 실제로 찾아 준 이름 · 주소를 보여 준다
    link = f" · [카카오맵에서 보기]({center['url']})" if center["url"] else ""
    st.markdown(f"**기준 장소** · {center['name']} ({center['address']}){link}")
    st.caption(
        f"넣은 이름 「{result['place']}」 로 카카오에서 찾은 맨 위 결과입니다 · 카카오 분류 {center['category']}"
        " · 다른 곳이 나왔다면 이름을 더 자세히 넣어 주세요"
    )
    st.caption(f"반경 {result['radius']:,}m · 찾을 음식 {result['keyword'] or ALL_FOOD}")
    if table.empty:
        st.info("조건에 맞는 음식점이 없습니다. 반경을 넓히거나 검색어를 바꿔 보세요")
        return

    # 걸러 보기 · 정렬 · 카카오는 다시 부르지 않고 받은 결과 안에서만 한다
    left, middle, right = st.columns([2, 2, 1])
    word = left.text_input("결과 안에서 찾기", placeholder="가게 이름이나 종류 (예: 비빔밥)")
    kinds = middle.multiselect("종류", sorted(table["kind"].unique()))
    sort_name = right.selectbox("정렬", list(SORTS))

    shown = table
    if word.strip():
        found = shown["place_name"].str.contains(word.strip(), case=False, regex=False) | shown[
            "category_name"
        ].str.contains(word.strip(), case=False, regex=False)
        shown = shown[found]
    if kinds:
        shown = shown[shown["kind"].isin(kinds)]
    column, ascending = SORTS[sort_name]
    shown = shown.sort_values(column, ascending=ascending, na_position="last")

    a, b, c, d = st.columns(4)
    a.metric("보이는 가게", f"{len(shown):,}곳")
    b.metric("카카오 검색 결과 전체", f"{result['total']:,}곳", help=f"카카오는 한 검색에 최대 {MAX_RESULTS}곳까지만 보여 줍니다")
    if shown["distance"].notna().any():
        c.metric("가장 가까운 곳", f"{int(shown['distance'].min()):,}m")
        d.metric("평균 거리", f"{int(shown['distance'].mean()):,}m")

    if shown.empty:
        st.info("걸러 본 조건에 맞는 가게가 없습니다")
        return

    show_charts(shown)
    # 점 크기는 미터 단위 · 가게끼리 붙어 있어 작게 둔다
    st.map(shown, latitude="lat", longitude="lon", size=15)
    columns = ["place_name", "kind", "distance", "road_address_name", "phone", "place_url", "naver_url"]
    # 네이버 링크 칸을 붙이기 전에 받아 둔 결과에는 그 칸이 없다 · 다시 검색하면 생긴다
    if "naver_url" not in shown:
        columns.remove("naver_url")
        st.caption("네이버 지도 링크는 [검색] 을 한 번 더 누르면 생깁니다")
    # 링크 칸은 누르면 새 탭에서 열린다
    st.dataframe(
        shown[columns],
        hide_index=True,
        use_container_width=True,
        column_config={
            "place_name": "가게 이름",
            "kind": "종류",
            "distance": st.column_config.NumberColumn("거리", format="%d m"),
            "road_address_name": "주소",
            "phone": "전화",
            "place_url": st.column_config.LinkColumn("카카오맵", display_text="열기"),
            "naver_url": st.column_config.LinkColumn("네이버 지도", display_text="열기"),
        },
    )


st.title("근처 맛집 대시보드")

# 넣는 자리 · [검색] 을 눌렀을 때만 카카오를 부른다
with st.form("lunch_form"):
    left, right = st.columns([3, 2])
    place = left.text_input("기준 장소", value=DEFAULT_PLACE, placeholder="역이나 동네 이름 (예: 강남역, 연남동)")
    radius = right.slider("반경 (m)", min_value=100, max_value=2000, value=500, step=100)
    left, right = st.columns([3, 2])
    food = left.selectbox("찾을 음식", FOODS)
    typed = right.text_input("직접 넣기", placeholder="넣으면 고른 음식 대신 씀 (예: 비빔밥)")
    searched = st.form_submit_button("검색", type="primary")

if searched:
    keyword = typed.strip() or ("" if food == ALL_FOOD else food)
    run_search(place.strip(), keyword, radius)

if "lunch_search" in st.session_state:
    show_dashboard(st.session_state.lunch_search)
else:
    st.info("기준 장소 · 반경 · 찾을 음식을 고르고 [검색] 을 눌러 주세요")
