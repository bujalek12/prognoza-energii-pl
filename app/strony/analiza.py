"""Strona Analiza: jak OZE zmieniaja polski system energetyczny (dane z hurtowni dbt).

Liczby w tekstach sa liczone z danych przy kazdym otwarciu, nie wpisane na sztywno,
wiec wnioski aktualizuja sie razem z hurtownia.
"""

import altair as alt
import duckdb
import pandas as pd
import streamlit as st

from wspolne import REZ, komunikat, liczba, motyw, os_y_mw, procent, rampa, sprawdz_baze, ulamek, wyglad, zapytanie

m = motyw()
SERIE = m["serie"]
MIESIACE = ["sty", "lut", "mar", "kwi", "maj", "cze", "lip", "sie", "wrz", "paź", "lis", "gru"]

sprawdz_baze()
try:
    rdr = zapytanie("""
        select year(data) as rok, sum(wiatr_gwh + pv_gwh) / sum(zapotrzebowanie_gwh) as udzial,
               count(*) as dni
        from marts.fct_bilans_dzienny where miesiac in (7, 8, 9) group by 1 order by 1
    """)
    mies = zapytanie("""
        select date_trunc('month', data) as miesiac,
               sum(wiatr_gwh) / sum(zapotrzebowanie_gwh) as "Wiatr",
               sum(pv_gwh) / sum(zapotrzebowanie_gwh) as "Fotowoltaika"
        from marts.fct_bilans_dzienny group by 1 order by 1
    """)
    ponad50 = zapytanie("""
        select year(czas_lokalny) as rok, count(*) filter (where udzial_oze > 0.5) as godzin
        from marts.fct_energia_godzinowa where miesiac between 6 and 9 group by 1 order by 1
    """)
    mapa = zapytanie("""
        select miesiac, godzina, avg(udzial_oze) as udzial
        from marts.fct_energia_godzinowa
        where czas_lokalny >= (select max(czas_lokalny) from marts.fct_energia_godzinowa) - interval 12 month
        group by 1, 2
    """)
    kaczka = zapytanie("""
        select year(czas_lokalny) as rok, godzina, avg(rezydualne_mw) as rezydualne
        from marts.fct_energia_godzinowa where miesiac in (6, 7, 8) and czy_dzien_roboczy
        group by 1, 2 order by 1, 2
    """)
    minimum = zapytanie("""
        select czas_lokalny, rezydualne_mw, zapotrzebowanie_mw, pv_mw
        from marts.fct_energia_godzinowa order by rezydualne_mw limit 1
    """)
    temp = zapytanie("""
        select temperatura_srednia_c, zapotrzebowanie_gwh, data
        from marts.fct_bilans_dzienny where czy_dzien_roboczy
    """)
    typy = zapytanie("""
        select d.typ_dnia, avg(b.zapotrzebowanie_gwh) as gwh
        from marts.fct_bilans_dzienny b join marts.dim_data d using (data) group by 1
    """).set_index("typ_dnia")["gwh"]
except duckdb.IOException:
    komunikat("Trwa aktualizacja danych.", "Pipeline zapisuje teraz bazę. Odśwież stronę za kilka minut.")
except duckdb.CatalogException:
    komunikat("Brak hurtowni.", "Zbuduj ją poleceniem <code>cd dbt && uv run dbt build</code>.")

# --- Teza ---------------------------------------------------------------------------
pelne = rdr[rdr["dni"] >= 90]  # tylko lata z pelnym lipcem-wrzesniem
if pelne.empty:
    komunikat("Za mało danych na analizę.", "Potrzebny jest co najmniej jeden pełny okres lipiec–wrzesień.")
pierwszy, ostatni = pelne.iloc[0], pelne.iloc[-1]
st.markdown(
    f'<h1 class="teza">W lipcu–wrześniu {int(ostatni.rok)} wiatr i słońce pokryły {procent(ostatni.udzial)} '
    f"zapotrzebowania. W {int(pierwszy.rok)} było to {procent(pierwszy.udzial)}.</h1>",
    unsafe_allow_html=True,
)
st.markdown(
    '<p class="porownanie">Analiza danych PSE z hurtowni dbt: '
    f"{liczba(len(temp))} dni roboczych, czerwiec 2024 – dziś. Porównujemy te same miesiące rok do roku, "
    "bo zimą słońca jest kilka razy mniej.</p>",
    unsafe_allow_html=True,
)


def legenda(pozycje: dict[str, str], ksztalt: str = "pole") -> None:
    html = "".join(f'<span><i class="{ksztalt}" style="background:{k}"></i>{n}</span>' for n, k in pozycje.items())
    st.markdown(f'<div class="legenda">{html}</div>', unsafe_allow_html=True)


# --- 1. Udzial miesiecznie --------------------------------------------------------------
st.subheader("Udział OZE miesiąc po miesiącu")
legenda({"Wiatr": SERIE["Wiatr"], "Fotowoltaika": SERIE["Fotowoltaika"]})
dlugi = mies.melt("miesiac", var_name="zrodlo", value_name="udzial")
wykres = (
    alt.Chart(dlugi)
    .mark_area(opacity=0.85, line={"strokeWidth": 1}, interpolate="monotone")
    .encode(
        x=alt.X("miesiac:T", title=None, axis=alt.Axis(format="%m.%Y", labelAngle=0, grid=False, tickCount=8)),
        y=alt.Y("udzial:Q", stack="zero", title=None, axis=alt.Axis(format="%", domain=False, tickCount=5)),
        color=alt.Color("zrodlo:N", scale=alt.Scale(domain=["Wiatr", "Fotowoltaika"],
                        range=[SERIE["Wiatr"], SERIE["Fotowoltaika"]]), legend=None),
        order=alt.Order("zrodlo:N", sort="descending"),
        tooltip=[alt.Tooltip("miesiac:T", title="Miesiąc", format="%m.%Y"), alt.Tooltip("zrodlo:N", title="Źródło"),
                 alt.Tooltip("udzial:Q", title="Udział", format=".1%")],
    )
)
st.altair_chart(wyglad(wykres, m, 320), width="stretch", theme=None)
st.markdown(
    '<p class="przypis">Latem dominuje fotowoltaika, zimą wiatr. Najsłabsze są miesiące od listopada '
    "do lutego, gdy słońca jest najmniej, a wiatr nie zawsze to nadrabia.</p>",
    unsafe_allow_html=True,
)

# --- 2. Godziny > 50% i mapa ciepla -------------------------------------------------------
st.subheader("Kiedy OZE pokrywają ponad połowę zapotrzebowania")
liczby = " → ".join(f"{liczba(r.godzin)} ({r.rok})" for r in ponad50.itertuples())
st.markdown(
    f"<p>Godzin z udziałem OZE powyżej 50% w sezonie czerwiec–wrzesień: <b>{liczby}</b>. "
    "Prawie wyłącznie między 10 a 15, od kwietnia do września.</p>",
    unsafe_allow_html=True,
)
mapa["nazwa_miesiaca"] = mapa["miesiac"].map(lambda x: MIESIACE[x - 1])
wykres = (
    alt.Chart(mapa)
    .mark_rect(stroke=m["tlo"], strokeWidth=1)
    .encode(
        x=alt.X("nazwa_miesiaca:O", sort=MIESIACE, title=None, axis=alt.Axis(labelAngle=0, domain=False, ticks=False)),
        y=alt.Y("godzina:O", title=None, axis=alt.Axis(domain=False, ticks=False, labelExpr="datum.value + ':00'",
                values=list(range(0, 24, 3)))),
        color=alt.Color("udzial:Q", scale=alt.Scale(range=m["skala"], domain=[0, 0.7], clamp=True),
                        legend=alt.Legend(title="udział OZE", format="%", orient="right", gradientLength=200)),
        tooltip=[alt.Tooltip("nazwa_miesiaca:O", title="Miesiąc"), alt.Tooltip("godzina:O", title="Godzina"),
                 alt.Tooltip("udzial:Q", title="Średni udział OZE", format=".1%")],
    )
)
st.altair_chart(wyglad(wykres, m, 420), width="stretch", theme=None)
st.markdown('<p class="przypis">Średni udział OZE w ostatnich 12 miesiącach, wg godziny i miesiąca.</p>',
            unsafe_allow_html=True)

# --- 3. Kaczka ------------------------------------------------------------------------------
st.subheader("Kaczka: czego potrzebują elektrownie konwencjonalne")
pivot = kaczka.pivot(index="godzina", columns="rok", values="rezydualne")
lata = list(pivot.columns)
poludnie = pivot.loc[11:13].mean() / 1000
wieczor = pivot.loc[19:20].mean() / 1000
mn = minimum.iloc[0]
st.markdown(
    f"<p>W letnie dni robocze zapotrzebowanie rezydualne w południe spadło z <b>{ulamek(poludnie[lata[0]])} GW</b> "
    f"({lata[0]}) do <b>{ulamek(poludnie[lata[-1]])} GW</b> ({lata[-1]}), a wieczorem wciąż wynosi ok. "
    f"{ulamek(wieczor[lata[-1]])} GW. Między południem a 20:00 trzeba więc dołożyć "
    f"<b>{ulamek(wieczor[lata[-1]] - poludnie[lata[-1]])} GW</b> ({ulamek(wieczor[lata[0]] - poludnie[lata[0]])} GW "
    f"w {lata[0]}).</p>",
    unsafe_allow_html=True,
)
kolory_lat = dict(zip(lata, rampa(*m["lata"], len(lata))))
legenda({str(r): k for r, k in kolory_lat.items()}, "kreska")
kaczka["rok_txt"] = kaczka["rok"].astype(str)
kaczka["GW"] = kaczka["rezydualne"] / 1000
wykres = (
    alt.Chart(kaczka)
    .mark_line(strokeWidth=2.4, interpolate="monotone")
    .encode(
        x=alt.X("godzina:Q", title=None, scale=alt.Scale(domain=[0, 23], nice=False),
                axis=alt.Axis(values=list(range(0, 24, 2)), labelExpr="datum.value + ':00'", grid=False)),
        y=alt.Y("GW:Q", title="GW", scale=alt.Scale(zero=False), axis=alt.Axis(domain=False, tickCount=5)),
        color=alt.Color("rok_txt:N", scale=alt.Scale(domain=[str(r) for r in lata], range=list(kolory_lat.values())),
                        legend=None),
        tooltip=[alt.Tooltip("rok_txt:N", title="Rok"), alt.Tooltip("godzina:Q", title="Godzina"),
                 alt.Tooltip("GW:Q", title="Rezydualne (GW)", format=".1f")],
    )
)
st.altair_chart(wyglad(wykres, m, 360), width="stretch", theme=None)
st.markdown(
    f'<p class="przypis">Czerwiec–sierpień, dni robocze. Najniższe zapotrzebowanie rezydualne w danych: '
    f"{mn.czas_lokalny:%d.%m.%Y, %H:%M}, tylko {liczba(mn.rezydualne_mw)} MW przy zapotrzebowaniu "
    f"{liczba(mn.zapotrzebowanie_mw)} MW i PV {liczba(mn.pv_mw)} MW.</p>",
    unsafe_allow_html=True,
)

# --- 4. Temperatura i typ dnia ----------------------------------------------------------------
st.subheader("Temperatura i dzień tygodnia")
koszyki = temp.assign(t=(temp["temperatura_srednia_c"] / 2.5).round() * 2.5).groupby("t")["zapotrzebowanie_gwh"]
srednie = koszyki.mean()[koszyki.size() >= 5].reset_index()
najnizej = srednie.loc[srednie["zapotrzebowanie_gwh"].idxmin()]
mroz = srednie.iloc[0]
st.markdown(
    f"<p>Zależność ma kształt litery U z minimum przy ok. <b>{ulamek(najnizej.t, 0)}°C</b>. "
    f"Przy {ulamek(mroz.t, 0)}°C zapotrzebowanie jest wyższe o <b>{procent(mroz.zapotrzebowanie_gwh / najnizej.zapotrzebowanie_gwh - 1)}</b>. "
    f"W soboty system potrzebuje o {procent(1 - typy['sobota'] / typy['dzień roboczy'])} mniej energii niż w dzień roboczy, "
    f"w niedziele i święta o {procent(1 - typy['niedziela i święto'] / typy['dzień roboczy'])} mniej.</p>",
    unsafe_allow_html=True,
)
punkty = (
    alt.Chart(temp)
    .mark_circle(size=22, opacity=0.4, color=SERIE[REZ])
    .encode(
        x=alt.X("temperatura_srednia_c:Q", title="średnia dobowa temperatura (°C)", axis=alt.Axis(grid=False)),
        y=alt.Y("zapotrzebowanie_gwh:Q", title="GWh / doba", scale=alt.Scale(zero=False), axis=os_y_mw()),
        tooltip=[alt.Tooltip("data:T", title="Dzień", format="%d.%m.%Y"),
                 alt.Tooltip("temperatura_srednia_c:Q", title="Temperatura", format=".1f"),
                 alt.Tooltip("zapotrzebowanie_gwh:Q", title="GWh", format=".0f")],
    )
)
linia = alt.Chart(srednie).mark_line(strokeWidth=2.4, color=SERIE["Zapotrzebowanie"], interpolate="monotone").encode(
    x="t:Q", y="zapotrzebowanie_gwh:Q"
)
st.altair_chart(wyglad(punkty + linia, m, 360), width="stretch", theme=None)
st.markdown('<p class="przypis">Dni robocze. Linia: średnia w przedziałach co 2,5°C. '
            "Pełna analiza z metodą: notebooks/02_analiza.ipynb.</p>", unsafe_allow_html=True)
