"""Bilans KSE: zapotrzebowanie, generacja wiatrowa i PV z API PSE.

Uruchomienie: uv run streamlit run app/app.py
"""

from datetime import date, timedelta

import altair as alt
import httpx
import pandas as pd
import streamlit as st

from etapy import ETAPY, NOTATKI

st.set_page_config(page_title="Bilans KSE", layout="wide", initial_sidebar_state="collapsed")

PSE_API = "https://api.raporty.pse.pl/api"
REPO = "https://github.com/bujalek12/prognoza-energii-pl"

# Kolory serii: przypisane do zjawiska, nie do kolejnosci na wykresie
SERIE = {
    "Zapotrzebowanie": "#2b2b29",
    "Zapotrzebowanie rezydualne": "#2a78d6",
    "Wiatr": "#1baf7a",
    "Fotowoltaika": "#eda100",
}

st.markdown(
    """
    <style>
      .block-container { padding-top: 2.2rem; max-width: 1180px; }
      .nadtytul { font-size: .78rem; letter-spacing: .08em; text-transform: uppercase;
                  color: #6b6a65; margin-bottom: .15rem; }
      h1 { font-weight: 600 !important; letter-spacing: -.01em; }
      [data-testid="stMetricValue"] { font-variant-numeric: tabular-nums; font-size: 1.7rem; }
      .przypis { color: #6b6a65; font-size: .85rem; }
      .notatka { border-left: 2px solid #d9d8d3; padding: .1rem 0 .1rem .9rem; margin: 0 0 1rem 0; }
      .notatka b { font-weight: 600; }
      table.etapy { border-collapse: collapse; width: 100%; font-size: .92rem; border: none; }
      table.etapy td { border: none; border-bottom: 1px solid #ecebe7; padding: .42rem .3rem; }
      table.etapy td.nr { color: #8a8984; width: 1.6rem; font-variant-numeric: tabular-nums; }
      table.etapy td.st { color: #6b6a65; text-align: right; white-space: nowrap; }
    </style>
    """,
    unsafe_allow_html=True,
)


# Tymczasowe pobieranie: w etapie 2 zastapi je modul ingestii z retry, walidacja i archiwum.
@st.cache_data(ttl=900, show_spinner="Pobieram dane z PSE…")
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
    df = df.dropna(subset=["demand"]).sort_values("czas").set_index("czas")
    df = df.rename(columns={"demand": "Zapotrzebowanie", "wi": "Wiatr", "pv": "Fotowoltaika"})
    df["Zapotrzebowanie rezydualne"] = df["Zapotrzebowanie"] - df["Wiatr"] - df["Fotowoltaika"]
    return df[list(SERIE)]


def mw(x: float) -> str:
    return f"{x:,.0f} MW".replace(",", " ")


# --- Naglowek -------------------------------------------------------------------
st.markdown('<div class="nadtytul">Krajowy System Elektroenergetyczny</div>', unsafe_allow_html=True)
st.title("Zapotrzebowanie i generacja OZE")

okres = st.segmented_control(
    "Okres", ["3 dni", "7 dni", "14 dni"], default="7 dni", label_visibility="collapsed"
)
dni = int((okres or "7 dni").split()[0])
df = pobierz_wykonanie(date.today() - timedelta(days=dni + 1), date.today())
teraz = df.iloc[-1]
wczoraj = df.loc[df.index <= df.index[-1] - pd.Timedelta(hours=24)].iloc[-1]

st.markdown(
    f'<p class="przypis">Ostatni pomiar: {df.index[-1]:%d.%m.%Y, %H:%M} · '
    "zmiana względem tej samej pory wczoraj</p>",
    unsafe_allow_html=True,
)

# --- Wskazniki ------------------------------------------------------------------
for kolumna, nazwa in zip(st.columns(4), ["Zapotrzebowanie", "Wiatr", "Fotowoltaika", "Zapotrzebowanie rezydualne"]):
    rezydualne = nazwa.endswith("rezydualne")
    kolumna.metric(
        "Rezydualne" if rezydualne else nazwa,
        mw(teraz[nazwa]),
        delta=mw(teraz[nazwa] - wczoraj[nazwa]),
        delta_color="off",
        help=(
            "Zapotrzebowanie minus wiatr i PV, czyli to, co muszą pokryć elektrownie "
            "konwencjonalne i import."
            if rezydualne
            else None
        ),
    )

# --- Wykres ---------------------------------------------------------------------
wykres_df = df.loc[df.index >= df.index[-1] - pd.Timedelta(days=dni)].reset_index()
dlugi = wykres_df.melt("czas", var_name="seria", value_name="MW")
kolor = alt.Color(
    "seria:N",
    scale=alt.Scale(domain=list(SERIE), range=list(SERIE.values())),
    legend=alt.Legend(
        title=None, orient="top", direction="horizontal", symbolStrokeWidth=2, labelLimit=0
    ),
)
os_x = alt.X(
    "czas:T", title=None, axis=alt.Axis(format="%d.%m", labelAngle=0, tickCount=dni, grid=False)
)
# d3-format w Vega nie zna polskiego locale, wiec separator tysiecy podmieniam recznie
os_y_osie = alt.Axis(
    gridColor="#ecebe7",
    domain=False,
    tickCount=5,
    labelExpr="replace(format(datum.value, ',.0f'), /,/g, '\u202f')",
)

oze = (
    alt.Chart(dlugi)
    .transform_filter(alt.FieldOneOfPredicate("seria", ["Wiatr", "Fotowoltaika"]))
    .mark_area(opacity=0.55, line={"strokeWidth": 1}, interpolate="monotone")
    .encode(
        x=os_x,
        y=alt.Y("MW:Q", stack="zero", title="MW", axis=os_y_osie),
        color=kolor,
        order=alt.Order("seria:N", sort="descending"),
    )
)
linie = (
    alt.Chart(dlugi)
    .transform_filter(
        alt.FieldOneOfPredicate("seria", ["Zapotrzebowanie", "Zapotrzebowanie rezydualne"])
    )
    .mark_line(strokeWidth=2, interpolate="monotone")
    .encode(x=os_x, y=alt.Y("MW:Q", stack=None, title="MW", axis=os_y_osie), color=kolor)
)

# Kursor: pionowa linia + tooltip ze wszystkimi seriami w danym kwadransie
kursor = alt.selection_point(
    fields=["czas"], nearest=True, on="pointerover", clear="pointerout", empty=False
)
tooltip_df = wykres_df.assign(
    **{f"{s} ": wykres_df[s].map(mw) for s in SERIE}  # tekst z polskim separatorem
)
linia_kursora = (
    alt.Chart(tooltip_df)
    .mark_rule(color="#8a8984", strokeWidth=1)
    .encode(
        x="czas:T",
        opacity=alt.condition(kursor, alt.value(1), alt.value(0)),
        tooltip=[alt.Tooltip("czas:T", title="Czas", format="%d.%m.%Y %H:%M")]
        + [alt.Tooltip(f"{s} :N", title=s) for s in SERIE],
    )
    .add_params(kursor)
)

st.altair_chart(
    alt.layer(oze, linie, linia_kursora).properties(height=430).configure_view(strokeWidth=0),
    width="stretch",
)
st.markdown(
    '<p class="przypis">Wiatr i PV skumulowane. Źródło: PSE, raport <code>his-wlk-cal</code>, '
    "rozdzielczość 15 min.</p>",
    unsafe_allow_html=True,
)

with st.expander("Dane w tabeli"):
    st.dataframe(
        wykres_df.sort_values("czas", ascending=False),
        hide_index=True,
        column_config={"czas": st.column_config.DatetimeColumn("Czas", format="DD.MM.YYYY HH:mm")}
        | {s: st.column_config.NumberColumn(s, format="%.0f") for s in SERIE},
    )

st.divider()

# --- Notatki i stan projektu ----------------------------------------------------
lewa, prawa = st.columns([3, 2], gap="large")
with lewa:
    st.subheader("Notatki z eksploracji")
    for tytul, opis in NOTATKI:
        st.markdown(f'<div class="notatka"><b>{tytul}.</b> {opis}</div>', unsafe_allow_html=True)

with prawa:
    st.subheader("Stan projektu")
    wiersze = "".join(
        f'<tr><td class="nr">{e["nr"]}</td><td>{e["nazwa"]}</td><td class="st">{e["status"]}</td></tr>'
        for e in ETAPY
    )
    st.markdown(f'<table class="etapy">{wiersze}</table>', unsafe_allow_html=True)
    st.markdown(
        f'<p class="przypis">Kod: <a href="{REPO}">{REPO.removeprefix("https://")}</a></p>',
        unsafe_allow_html=True,
    )
