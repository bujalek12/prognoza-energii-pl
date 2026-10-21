"""Aplikacja Bilans KSE: bilans na zywo, analiza i prognoza na jutro, wspolny motyw.

Uruchomienie: uv run streamlit run app/app.py
"""

import sys
from pathlib import Path

import streamlit as st

# kod projektu (src/energia) bez instalowania pakietu: tak dziala tez Streamlit Community Cloud
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from wspolne import naglowek  # noqa: E402

st.set_page_config(page_title="Bilans KSE", layout="wide", initial_sidebar_state="collapsed")

strony = [
    st.Page("strony/bilans.py", title="Bilans", default=True),
    st.Page("strony/analiza.py", title="Analiza", url_path="analiza"),
    st.Page("strony/prognoza.py", title="Prognoza", url_path="prognoza"),
]
nawigacja = st.navigation(strony, position="hidden")  # wlasny pasek u gory zamiast menu bocznego
naglowek(strony)
nawigacja.run()
