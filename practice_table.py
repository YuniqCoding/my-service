from pathlib import Path

import pandas as pd
import streamlit as st

# 이 파일과 같은 폴더의 data 폴더에서 CSV 를 찾는다
CSV_PATH = Path(__file__).parent / "data" / "56_practice-inquiries.csv"

st.set_page_config(page_title="56_practice-inquiries.csv")

st.title("56_practice-inquiries.csv")

df = pd.read_csv(CSV_PATH, encoding="utf-8")

# type 열로 거르는 필터 · 처음에는 전체가 보인다
selected = st.selectbox("type", ["전체"] + sorted(df["type"].dropna().unique()))

# status 열로 거르는 필터 · 처음에는 전체가 보인다
selected_status = st.selectbox("status", ["전체"] + sorted(df["status"].dropna().unique()))

# 두 필터에서 고른 값이 둘 다 맞는 줄만 남긴다
if selected != "전체":
    df = df[df["type"] == selected]
if selected_status != "전체":
    df = df[df["status"] == selected_status]

# 지금 보이는 줄 수
st.write(f"{len(df)}줄")

# 표로 보여 준다
st.dataframe(df)
