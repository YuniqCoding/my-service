from pathlib import Path

import streamlit as st

# 이 파일과 같은 폴더의 .env 에서 키를 찾는다
ENV_PATH = Path(__file__).parent / ".env"


def load_env():
    """내 컴퓨터에서는 .env 를, .env 가 없는 올린 곳에서는 Secrets 를 읽어 「이름 → 값」 으로 모은다."""
    if not ENV_PATH.is_file():
        try:
            return dict(st.secrets)
        except FileNotFoundError:  # Secrets 도 없으면 빈 채로 둔다
            return {}
    values = {}
    for line in ENV_PATH.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        name, value = line.split("=", 1)
        values[name.strip()] = value.strip()
    return values
