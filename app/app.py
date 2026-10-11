"""Panel projektu: postep etapow + dane na zywo z PSE.

Uruchomienie: uv run streamlit run app/app.py
"""

from datetime import date, timedelta

import altair as alt
import httpx
import pandas as pd
import streamlit as st

from etapy import ETAPY, ODKRYCIA

st.set_page_config(page_title="Prognoza energii PL", page_icon="⚡", layout="wide")

PSE_API = "https://api.raporty.pse.pl/api"
IKONY = {"zrobione": "✅", "nastepny": "🔜", "w toku": "🛠️", "czeka": "⏳"}


# Tymczasowe pobieranie danych: w etapie 2 zastapi je modul ingestii z retry i walidacja.
@st.cache_data(ttl=3600, show_spinner="Pobieram dane z PSE…")
def pobierz_wykonanie(od: date, do: date) -> pd.DataFrame:
    url = f"{PSE_API}/his-wlk-cal"
    params = {"$filter": f"business_date ge '{od}' and business_date le '{do}'"}
    wiersze = []
    with httpx.Client(timeout=60) as klient:
        while url:
            odp = klient.get(url, params=params)
            odp.raise_for_status()
            dane = odp.json()
            wiersze.extend(dane["value"])
            url, params = dane.get("nextLink"), None
    df = pd.DataFrame(wiersze)
    df["czas"] = (
        pd.to_datetime(df["dtime_utc"]).dt.tz_localize("UTC").dt.tz_convert("Europe/Warsaw")
    )
    # API zwraca tez przyszle kwadranse biezacej doby z pustymi wartosciami
    return df[["czas", "demand", "wi", "pv"]].dropna(subset=["demand"]).sort_values("czas")


# --- Pasek boczny: postep -----------------------------------------------------
zrobione = sum(e["status"] == "zrobione" for e in ETAPY)
with st.sidebar:
    st.header("Postęp projektu")
    st.progress(zrobione / len(ETAPY), text=f"Etap {zrobione} / {len(ETAPY)} zakończony")
    for e in ETAPY:
        st.markdown(f"{IKONY[e['status']]} **{e['nr']}.** {e['nazwa']}  \n`{e['rola']}`")

# --- Naglowek -----------------------------------------------------------------
st.title("⚡ Prognozowanie polskiego systemu energetycznego")
st.caption(
    "Czy da się prognozować zapotrzebowanie i generację z OZE na dobę naprzód "
    "dokładniej niż oficjalny plan PSE?"
)

zakladka_dane, zakladka_odkrycia = st.tabs(["📈 Dane na żywo", "🔍 Odkrycia"])

# --- Dane na zywo ---------------------------------------------------------------
with zakladka_dane:
    dni = st.slider("Ile ostatnich dni pokazać", 2, 14, 7)
    do = date.today()
    df = pobierz_wykonanie(do - timedelta(days=dni), do)

    ostatni = df.iloc[-1]
    oze = (ostatni["wi"] + ostatni["pv"]) / ostatni["demand"]
    k1, k2, k3, k4 = st.columns(4)
    k1.metric("Zapotrzebowanie", f"{ostatni['demand']:,.0f} MW".replace(",", " "))
    k2.metric("Wiatr", f"{ostatni['wi']:,.0f} MW".replace(",", " "))
    k3.metric("Fotowoltaika", f"{ostatni['pv']:,.0f} MW".replace(",", " "))
    k4.metric("Udział wiatru + PV", f"{oze:.0%}")
    st.caption(f"Ostatni kwadrans w danych: {ostatni['czas']:%Y-%m-%d %H:%M} (czas polski)")

    dlugi = df.rename(columns={"demand": "Zapotrzebowanie", "wi": "Wiatr", "pv": "Fotowoltaika"}).melt(
        "czas", var_name="seria", value_name="MW"
    )
    wykres = (
        alt.Chart(dlugi)
        .mark_line(strokeWidth=1.2)
        .encode(
            x=alt.X("czas:T", title=None),
            y=alt.Y("MW:Q", title="MW"),
            color=alt.Color(
                "seria:N",
                title=None,
                scale=alt.Scale(
                    domain=["Zapotrzebowanie", "Wiatr", "Fotowoltaika"],
                    range=["#4c78a8", "#54a24b", "#f2a33a"],
                ),
            ),
            tooltip=[alt.Tooltip("czas:T", format="%Y-%m-%d %H:%M"), "seria:N", alt.Tooltip("MW:Q", format=",.0f")],
        )
        .properties(height=420)
        .interactive()
    )
    st.altair_chart(wykres, width="stretch")
    st.caption("Źródło: API PSE, raport his-wlk-cal (dane co 15 minut).")

# --- Odkrycia -------------------------------------------------------------------
with zakladka_odkrycia:
    for nr, lista in ODKRYCIA.items():
        st.subheader(f"Etap {nr}: {ETAPY[nr - 1]['nazwa']}")
        for tytul, opis in lista:
            with st.container(border=True):
                st.markdown(f"**{tytul}**  \n{opis}")
    st.caption("Szczegóły: notebooks/01_eksploracja.ipynb oraz docs/architektura.md")
