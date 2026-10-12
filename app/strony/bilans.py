"""Strona Bilans: stan systemu w ostatnim kwadransie, ostatnie dni, stan danych, etapy."""

from datetime import date

import altair as alt
import duckdb
import pandas as pd
import streamlit as st

from energia import odczyt
from energia.formatowanie import odmiana
from energia.pipeline import BAZA, DBT
from etapy import ETAPY, NOTATKI
from wspolne import PL, POLECENIE, REPO, REZ, komunikat, liczba, motyw, os_y_mw, sprawdz_baze, wyglad

m = motyw()
SERIE = m["serie"]


# Aplikacja czyta lokalna baze zasilana przez pipeline (python -m energia.pipeline).
# Polaczenie tylko do odczytu, zeby nie blokowac pipeline'u, gdy pisze do bazy.
@st.cache_data(ttl=300, show_spinner=False)
def wczytaj(dni: int) -> tuple[pd.DataFrame, dict]:
    with duckdb.connect(str(BAZA), read_only=True) as con:
        con.execute("set TimeZone = 'UTC'")
        ostatni = con.execute("select max(ts_utc) from wykonanie").fetchone()[0]
        if ostatni is None:
            return pd.DataFrame(), {}
        od = pd.Timestamp(ostatni) - pd.Timedelta(days=dni + 1)
        stan = odczyt.stan_danych(con)
        # ile dob ma juz plan PSE opublikowany przed ich poczatkiem (uczciwy benchmark)
        stan["plan_pse"]["doby_z_benchmarkiem"] = con.execute(
            "select count(distinct doba) from plan_pse "
            "where publikacja_utc < timezone('Europe/Warsaw', doba::timestamp)"
        ).fetchone()[0]
        return odczyt.wykonanie_od(con, od), stan


# --- Dane -------------------------------------------------------------------------
okres = st.session_state.get("okres") or "7 dni"
dni = int(okres.split()[0])

sprawdz_baze()
try:
    df, stan = wczytaj(dni)
except duckdb.IOException:
    # DuckDB pozwala otworzyc plik tylko jednemu procesowi, gdy ktos do niego pisze
    komunikat("Trwa aktualizacja danych.", "Pipeline zapisuje teraz bazę. Odśwież stronę za kilka minut.")
if df.empty:
    komunikat("Baza nie ma jeszcze pomiarów.", f"Uruchom {POLECENIE} i odśwież stronę.")
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
os_y = os_y_mw()

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
st.altair_chart(wyglad(alt.layer(oze, linie, linia_kursora), m, 420), width="stretch", theme=None)
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

# --- Stan danych --------------------------------------------------------------------
st.subheader("Stan danych")
OPISY = {
    "wykonanie": "Pomiary PSE (co 15 min)",
    "plan_pse": "Archiwum planów PSE (każda wersja)",
    "pogoda": "Prognozy pogody, 5 punktów (co 1 h)",
}
wiersze = "".join(
    f"<tr><td>{OPISY[t]}</td><td class='prawo'>{liczba(s['wierszy'])}</td>"
    f"<td class='prawo'>{s['od'].tz_convert(PL):%d.%m.%Y} – {s['do'].tz_convert(PL):%d.%m.%Y}</td>"
    f"<td class='prawo'>{'—' if t != 'wykonanie' else liczba(s['braki'])}</td>"
    f"<td class='prawo'>{s['pobrano'].tz_convert(PL):%d.%m %H:%M}</td></tr>"
    if s["wierszy"] else f"<tr><td>{OPISY[t]}</td><td class='prawo czeka' colspan='4'>brak danych</td></tr>"
    for t, s in stan.items()
)
st.markdown(
    "<table class='lista'><tr><th>Źródło</th><th class='prawo'>Wierszy</th><th class='prawo'>Zakres</th>"
    f"<th class='prawo'>Brakujące kwadranse</th><th class='prawo'>Ostatnie pobranie</th></tr>{wiersze}</table>",
    unsafe_allow_html=True,
)
testy = odczyt.wyniki_testow_dbt(DBT / "target" / "run_results.json")
uwagi = [
    f"Plan PSE opublikowany przed dobą, której dotyczy: {(n := stan['plan_pse'].get('doby_z_benchmarkiem', 0))} "
    f"{odmiana(n, 'doba', 'doby', 'dób')} w archiwum. Ta liczba rośnie o jedną dobę dziennie."
]
if testy:
    if testy["zaliczonych"] == testy["testow"]:
        wynik = f"wszystkie {testy['testow']} zaliczone"
    else:
        wynik = f"{testy['zaliczonych']} z {testy['testow']} zaliczonych"
        if testy["nieudane"]:
            wynik += f", nieudane: {', '.join(testy['nieudane'])}"
        if testy["ostrzezenia"]:
            wynik += f", ostrzeżenia: {', '.join(testy['ostrzezenia'])}"
    uwagi.insert(0, f"Testy jakości danych (dbt, {testy['kiedy'].tz_convert(PL):%d.%m %H:%M}): {wynik}.")
st.markdown("".join(f'<p class="przypis">{u}</p>' for u in uwagi), unsafe_allow_html=True)

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
