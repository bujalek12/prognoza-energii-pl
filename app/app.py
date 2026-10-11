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
NAZWY = {"demand": "Zapotrzebowanie", "wi": "Wiatr", "pv": "Fotowoltaika"}
REZ = "Rezydualne"

# Dwa motywy. Kolory serii sa dobrane osobno pod kazde tlo i sprawdzone walidatorem
# palety (rozroznialnosc dla daltonistow, kontrast z tlem), nie odwrocone automatycznie.
MOTYWY = {
    "ciemny": {
        "tlo": "#0f1a24", "panel": "#162433", "linia": "#24384b",
        "tekst": "#e6edf2", "przygaszony": "#8ca0b3",
        "serie": {"Zapotrzebowanie": "#e6edf2", REZ: "#3987e5", "Wiatr": "#199e70", "Fotowoltaika": "#c98500"},
    },
    "jasny": {
        "tlo": "#f2f5f7", "panel": "#ffffff", "linia": "#d5dee5",
        "tekst": "#14212b", "przygaszony": "#5b6b78",
        "serie": {"Zapotrzebowanie": "#14212b", REZ: "#2a78d6", "Wiatr": "#1baf7a", "Fotowoltaika": "#eda100"},
    },
}


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
    # API zwraca tez przyszle (albo jeszcze niepelne) kwadranse z pustymi wartosciami
    df = df.dropna(subset=["demand", "wi", "pv"]).sort_values("czas").set_index("czas")
    df = df.rename(columns=NAZWY)[list(NAZWY.values())]
    df[REZ] = df["Zapotrzebowanie"] - df["Wiatr"] - df["Fotowoltaika"]
    return df


def liczba(x: float) -> str:
    return f"{x:,.0f}".replace(",", " ")


# --- Motyw ----------------------------------------------------------------------
# Wybor trzymany w adresie strony, zeby przetrwal odswiezenie (?motyw=jasny)
if "ciemny" not in st.session_state:
    st.session_state.ciemny = st.query_params.get("motyw", "ciemny") != "jasny"

gora_l, gora_p = st.columns([4, 1], vertical_alignment="center")
gora_l.markdown('<p class="marka">Bilans KSE</p>', unsafe_allow_html=True)
ciemny = gora_p.toggle("Tryb ciemny", key="ciemny")
st.query_params["motyw"] = "ciemny" if ciemny else "jasny"
m = MOTYWY["ciemny" if ciemny else "jasny"]
SERIE = m["serie"]

st.markdown(
    f"""
    <style>
      :root {{
        --tlo: {m["tlo"]}; --panel: {m["panel"]}; --linia: {m["linia"]};
        --tekst: {m["tekst"]}; --przygaszony: {m["przygaszony"]};
      }}
      .stApp {{ background: var(--tlo); color: var(--tekst); }}
      [data-testid="stHeader"] {{ display: none !important; }}
      .block-container {{ padding-top: 2rem; max-width: 1120px; }}
      .stApp p, .stApp li, .stApp label, .stApp summary, .stApp td {{ color: var(--tekst); }}
      .stApp a {{ color: {SERIE[REZ]}; }}

      .marka {{ font-family: "Barlow Semi Condensed"; font-weight: 600; font-size: 1.05rem;
                margin: 0; letter-spacing: .01em; }}
      .teza {{ font-family: "Barlow Semi Condensed"; font-weight: 500; color: var(--tekst);
               font-size: clamp(1.9rem, 4.2vw, 3.1rem); line-height: 1.08; letter-spacing: -.01em;
               margin: 1.6rem 0 1.4rem; max-width: 28ch; text-wrap: balance; font-variant-numeric: tabular-nums; }}

      .bilans {{ display: flex; gap: 2px; height: 46px; border-radius: 4px; overflow: hidden; }}
      .bilans div {{ height: 100%; }}
      .bilans-opis {{ display: flex; gap: 2px; margin-top: .45rem; }}
      .bilans-opis div {{ min-width: 5.5rem; font-size: .88rem; color: var(--przygaszony); line-height: 1.3;
                          overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }}
      .bilans-opis b {{ display: block; color: var(--tekst); font-weight: 600;
                        font-variant-numeric: tabular-nums; }}
      .porownanie {{ color: var(--przygaszony) !important; font-size: .92rem; margin: 1.1rem 0 2.2rem; }}

      h2, h3 {{ font-family: "Barlow Semi Condensed" !important; font-weight: 600 !important;
                color: var(--tekst) !important; }}
      .przypis {{ color: var(--przygaszony) !important; font-size: .85rem; }}
      .notatka {{ border-left: 2px solid var(--linia); padding: .1rem 0 .1rem .9rem; margin: 0 0 1.05rem; max-width: 62ch; }}
      .notatka b {{ font-weight: 600; }}
      code {{ background: var(--panel) !important; color: var(--tekst) !important; }}

      table.lista {{ border-collapse: collapse; width: 100%; font-size: .92rem; }}
      table.lista td, table.lista th {{ border: none; border-bottom: 1px solid var(--linia);
                                       padding: .42rem .35rem; text-align: left; }}
      table.lista th {{ color: var(--przygaszony); font-weight: 500; }}
      table.lista .nr {{ color: var(--przygaszony); width: 1.6rem; }}
      table.lista .prawo {{ text-align: right; font-variant-numeric: tabular-nums; white-space: nowrap; }}
      table.lista td.czeka {{ color: var(--przygaszony); }}
      .przewijana {{ max-height: 360px; overflow-y: auto; }}

      /* Kontrolki Streamlit dopasowane do motywu */
      [data-testid="stButtonGroup"] button {{ background: var(--panel); color: var(--tekst);
                                              border-color: var(--linia); }}
      [data-testid="stButtonGroup"] button[kind$="Active"] {{ border-color: {SERIE[REZ]}; color: {SERIE[REZ]}; }}
      [data-testid="stExpander"] details {{ border-color: var(--linia); background: var(--panel); }}
      [data-testid="stExpander"] summary:hover {{ color: {SERIE[REZ]}; }}
      [data-testid="stWidgetLabel"] p {{ color: var(--tekst); }}
      #vg-tooltip-element {{ background: var(--panel); color: var(--tekst); border: 1px solid var(--linia);
                             font-family: Barlow, sans-serif; box-shadow: none; }}
      #vg-tooltip-element td.key {{ color: var(--przygaszony); }}
      hr {{ border-color: var(--linia) !important; }}
      .legenda {{ display: flex; flex-wrap: wrap; gap: .35rem 1.3rem; font-size: .9rem; margin: .2rem 0 -.4rem; }}
      .legenda span {{ display: inline-flex; align-items: center; gap: .45rem; }}
      .legenda i.kreska {{ width: 16px; height: 2px; border-radius: 1px; }}
      .legenda i.pole {{ width: 11px; height: 11px; border-radius: 2px; opacity: .8; }}
      [data-testid="stCheckbox"] label:has(input:not(:checked)) > span + div {{ background: var(--linia); }}
      [data-testid="stCheckbox"] label > span + div > div {{ background: var(--panel);
                                                            box-shadow: 0 0 0 1px var(--linia); }}
    </style>
    """,
    unsafe_allow_html=True,
)

# --- Dane -------------------------------------------------------------------------
okres = st.session_state.get("okres") or "7 dni"
dni = int(okres.split()[0])
df = pobierz_wykonanie(date.today() - timedelta(days=dni + 1), date.today())
teraz = df.iloc[-1]
t = df.index[-1]
wczoraj = df.loc[df.index <= t - pd.Timedelta(hours=24)].iloc[-1]
udzial = (teraz["Wiatr"] + teraz["Fotowoltaika"]) / teraz["Zapotrzebowanie"]
udzial_wczoraj = (wczoraj["Wiatr"] + wczoraj["Fotowoltaika"]) / wczoraj["Zapotrzebowanie"]

# --- Teza: stan systemu w ostatnim kwadransie --------------------------------------
kiedy = f"Dziś o {t:%H:%M}" if t.date() == date.today() else f"{t:%d.%m} o {t:%H:%M}"
st.markdown(
    f'<h1 class="teza">{kiedy} system potrzebował {liczba(teraz["Zapotrzebowanie"])} MW. '
    f"Wiatr i fotowoltaika pokryły {udzial:.0%}.</h1>",
    unsafe_allow_html=True,
)

# Pasek bilansu: z czego sklada sie zapotrzebowanie w tym kwadransie
czesci = [(s, teraz[s]) for s in ["Wiatr", "Fotowoltaika", REZ] if teraz[s] > 0]
suma = sum(v for _, v in czesci)
pasek = "".join(
    f'<div style="flex:{v / suma:.4f};background:{SERIE[s]}" title="{s}: {liczba(v)} MW"></div>'
    for s, v in czesci
)
opisy = "".join(
    f'<div style="flex:{v / suma:.4f}"><b>{liczba(v)} MW</b>'
    f'{"konwencjonalne i import" if s == REZ else s.lower()}</div>'
    for s, v in czesci
)
st.markdown(
    f'<div class="bilans">{pasek}</div><div class="bilans-opis">{opisy}</div>'
    f'<p class="porownanie">Dobę wcześniej o tej porze: {liczba(wczoraj["Zapotrzebowanie"])} MW, '
    f"z czego OZE {udzial_wczoraj:.0%}. Wiatr {liczba(wczoraj['Wiatr'])} MW, "
    f"fotowoltaika {liczba(wczoraj['Fotowoltaika'])} MW.</p>",
    unsafe_allow_html=True,
)

# --- Wykres -----------------------------------------------------------------------
st.subheader("Ostatnie dni")
st.segmented_control(
    "Okres", ["3 dni", "7 dni", "14 dni"], default="7 dni", key="okres", label_visibility="collapsed"
)

legenda = "".join(
    f'<span><i class="{"pole" if s in ("Wiatr", "Fotowoltaika") else "kreska"}" '
    f'style="background:{k}"></i>{s}</span>'
    for s, k in SERIE.items()
)
st.markdown(f'<div class="legenda">{legenda}</div>', unsafe_allow_html=True)

wykres_df = df.loc[df.index >= t - pd.Timedelta(days=dni)].reset_index()
dlugi = wykres_df.melt("czas", var_name="seria", value_name="MW")
kolor = alt.Color(
    "seria:N",
    scale=alt.Scale(domain=list(SERIE), range=list(SERIE.values())),
    legend=None,  # legenda w HTML nad wykresem, bo ta z Vegi nie zawija sie na telefonie
)
os_x = alt.X("czas:T", title=None, axis=alt.Axis(format="%d.%m", labelAngle=0, tickCount=dni, grid=False))
# d3-format w Vega nie zna polskiego locale, wiec separator tysiecy podmieniam recznie
os_y = alt.Axis(domain=False, tickCount=5, labelExpr="replace(format(datum.value, ',.0f'), /,/g, '\u00a0')")

oze = (
    alt.Chart(dlugi)
    .transform_filter(alt.FieldOneOfPredicate("seria", ["Wiatr", "Fotowoltaika"]))
    .mark_area(opacity=0.6, line={"strokeWidth": 1}, interpolate="monotone")
    .encode(x=os_x, y=alt.Y("MW:Q", stack="zero", title="MW", axis=os_y), color=kolor,
            order=alt.Order("seria:N", sort="descending"))
)
linie = (
    alt.Chart(dlugi)
    .transform_filter(alt.FieldOneOfPredicate("seria", ["Zapotrzebowanie", REZ]))
    .mark_line(strokeWidth=2, interpolate="monotone")
    .encode(x=os_x, y=alt.Y("MW:Q", stack=None, title="MW", axis=os_y), color=kolor)
)
kursor = alt.selection_point(fields=["czas"], nearest=True, on="pointerover", clear="pointerout", empty=False)
tooltip_df = wykres_df.assign(**{f"{s} ": wykres_df[s].map(lambda x: f"{liczba(x)} MW") for s in SERIE})
linia_kursora = (
    alt.Chart(tooltip_df)
    .mark_rule(color=m["przygaszony"], strokeWidth=1)
    .encode(
        x="czas:T",
        opacity=alt.condition(kursor, alt.value(1), alt.value(0)),
        tooltip=[alt.Tooltip("czas:T", title="Czas", format="%d.%m.%Y %H:%M")]
        + [alt.Tooltip(f"{s} :N", title=s) for s in SERIE],
    )
    .add_params(kursor)
)
wykres = (
    alt.layer(oze, linie, linia_kursora)
    .properties(height=420, background="transparent")
    .configure_view(strokeWidth=0)
    .configure_axis(
        labelColor=m["przygaszony"], titleColor=m["przygaszony"], gridColor=m["linia"],
        tickColor=m["linia"], labelFont="Barlow", titleFont="Barlow", labelFontSize=12,
    )
)
st.altair_chart(wykres, width="stretch", theme=None)
st.markdown(
    '<p class="przypis">Wiatr i fotowoltaika skumulowane. Źródło: PSE, raport his-wlk-cal, '
    "pomiar co 15 minut.</p>",
    unsafe_allow_html=True,
)

with st.expander("Pokaż dane godzinowe"):
    godz = wykres_df.set_index("czas").resample("1h").mean().dropna().sort_index(ascending=False)
    naglowek = "".join(f'<th class="prawo">{s}</th>' for s in SERIE)
    wiersze = "".join(
        f"<tr><td>{c:%d.%m %H:%M}</td>"
        + "".join(f'<td class="prawo">{liczba(r[s])}</td>' for s in SERIE)
        + "</tr>"
        for c, r in godz.iterrows()
    )
    st.markdown(
        f'<div class="przewijana"><table class="lista"><tr><th>Godzina</th>{naglowek}</tr>{wiersze}</table></div>'
        '<p class="przypis">Średnie godzinowe w MW.</p>',
        unsafe_allow_html=True,
    )

st.divider()

# --- Notatki i etapy -----------------------------------------------------------------
lewa, prawa = st.columns([3, 2], gap="large")
with lewa:
    st.subheader("Co wyszło z eksploracji")
    for tytul, opis in NOTATKI:
        st.markdown(f'<div class="notatka"><b>{tytul}.</b> {opis}</div>', unsafe_allow_html=True)

with prawa:
    st.subheader("Etapy projektu")
    wiersze = "".join(
        f'<tr><td class="nr">{e["nr"]}</td>'
        f'<td class="{"" if e["status"] == "gotowe" else "czeka"}">{e["nazwa"]}</td>'
        f'<td class="prawo czeka">{e["status"]}</td></tr>'
        for e in ETAPY
    )
    st.markdown(f'<table class="lista">{wiersze}</table>', unsafe_allow_html=True)
    st.markdown(
        f'<p class="przypis">Kod źródłowy: <a href="{REPO}">{REPO.removeprefix("https://")}</a></p>',
        unsafe_allow_html=True,
    )
