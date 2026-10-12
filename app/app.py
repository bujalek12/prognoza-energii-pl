"""Aplikacja Bilans KSE: dwie strony (bilans na zywo i analiza), wspolny motyw.

Uruchomienie: uv run streamlit run app/app.py
"""

import streamlit as st

from wspolne import naglowek

st.set_page_config(page_title="Bilans KSE", layout="wide", initial_sidebar_state="collapsed")

strony = [
    st.Page("strony/bilans.py", title="Bilans", default=True),
    st.Page("strony/analiza.py", title="Analiza", url_path="analiza"),
]
nawigacja = st.navigation(strony, position="hidden")  # wlasny pasek u gory zamiast menu bocznego
naglowek(strony)
nawigacja.run()
