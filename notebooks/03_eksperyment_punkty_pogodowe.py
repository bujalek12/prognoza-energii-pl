# ---
# jupyter:
#   jupytext:
#     formats: py:percent,ipynb
#   kernelspec:
#     display_name: Python 3
#     language: python
#     name: python3
# ---

# %% [markdown]
# # Eksperyment: czy 16 punktów pogodowych zamiast 5 poprawia prognozę?
#
# **Hipoteza.** Farmy wiatrowe i fotowoltaika są rozproszone po całym kraju, a model widzi pogodę
# tylko w 5 punktach. W etapie 4 średnia z 5 punktów tłumaczyła generację lepiej niż którykolwiek
# pojedynczy punkt (wiatr 0,90, PV 0,96), więc więcej punktów powinno pomóc jeszcze bardziej.
#
# **Plan.** Prognozy pogody dla stolic wszystkich 16 województw (to samo źródło co w produkcji:
# archiwalne prognozy Open-Meteo), z nich cechy zbiorcze dla całego kraju. Backtest na ostatnich
# 6 miesiącach, ten sam kod co w produkcji, dwa warianty cech:
#
# - **A**: obecne cechy (5 punktów),
# - **B**: obecne cechy + cechy z 16 punktów.
#
# Do produkcji trafia B tylko wtedy, gdy błąd spadnie wyraźnie, a nie o ułamek procenta.

# %%
import dataclasses
import json
from pathlib import Path

import duckdb
import numpy as np
import pandas as pd

from energia.model.backtest import metryki, podzialy_miesieczne
from energia.model.trening import CELE, przewiduj, przygotuj_dane, trenuj

PROJEKT = Path("..")
con = duckdb.connect(str(PROJEKT / "data" / "energia.duckdb"), read_only=True)
con.execute("set TimeZone = 'UTC'")
df = przygotuj_dane(con)
pogoda16 = pd.read_parquet(PROJEKT / "data" / "eksperymenty" / "pogoda_16_wojewodztw.parquet")
print(df.shape, pogoda16["punkt"].nunique(), "punktów")

# %% [markdown]
# ## Cechy z 16 punktów
#
# Promieniowanie przesuwamy o godzinę, jak w hurtowni: Open-Meteo podaje je jako średnią
# z godziny poprzedzającej znacznik czasu. Oprócz średnich liczymy też rozrzut wiatru między
# punktami (odchylenie standardowe) i średnią z punktów północnych, gdzie stoi najwięcej farm.

# %%
p = pogoda16.sort_values(["punkt", "ts_utc"]).copy()
p["promieniowanie"] = p.groupby("punkt")["promieniowanie"].shift(-1)  # wartość o H+1 opisuje godzinę H
polnocne = {"Gdansk", "Szczecin", "Olsztyn", "Bydgoszcz", "Bialystok", "Gorzow"}

godz = p.groupby("ts_utc").agg(
    w16_wiatr_sredni=("wiatr_100m", "mean"),
    w16_wiatr_odchylenie=("wiatr_100m", "std"),
    w16_wiatr_max=("wiatr_100m", "max"),
    w16_promieniowanie_srednie=("promieniowanie", "mean"),
    w16_promieniowanie_odchylenie=("promieniowanie", "std"),
    w16_temperatura=("temperatura", "mean"),
    w16_zachmurzenie=("zachmurzenie", "mean"),
)
godz["w16_wiatr_polnoc"] = p[p["punkt"].isin(polnocne)].groupby("ts_utc")["wiatr_100m"].mean()
godz.index = pd.to_datetime(godz.index, utc=True)
godz.index.name = "godzina_utc"

df16 = df.join(godz, how="left")
NOWE = tuple(godz.columns)
print("pokrycie nowych cech:", f"{df16[list(NOWE)].notna().all(axis=1).mean():.1%}")

# %% [markdown]
# Pierwsza kontrola: korelacja z generacją, jak w etapie 4.

# %%
pd.DataFrame({
    "wiatr: 5 punktów": [df16["wiatr_mw"].corr(df16["wiatr_100m_sredni_kmh"])],
    "wiatr: 16 punktów": [df16["wiatr_mw"].corr(df16["w16_wiatr_sredni"])],
    "PV: 5 punktów": [df16["pv_mw"].corr(df16["promieniowanie_srednie_wm2"])],
    "PV: 16 punktów": [df16["pv_mw"].corr(df16["w16_promieniowanie_srednie"])],
}).round(3)

# %% [markdown]
# ## Backtest: wariant A vs B
#
# Ostatnie 6 miesięcy, model mediany (p50), rosnące okno. Ten sam kod co w produkcji
# (`trenuj`, `przewiduj`, `podzialy_miesieczne`), różni się tylko lista cech.


# %%
def backtest_nmae(dane: pd.DataFrame, cel, miesiecy: int = 6) -> tuple[float, pd.Series]:
    y_all, p_all, mies_all = [], [], []
    for miesiac, uczenie, test in podzialy_miesieczne(dane.index, miesiecy):
        d = dane[test].dropna(subset=[cel.nazwa, f"{cel.nazwa}_lag168", f"{cel.nazwa}_max30"])
        p_all.append(przewiduj(trenuj(dane[uczenie], cel, 0.5), d, cel))
        y_all.append(d[cel.nazwa].to_numpy())
        mies_all += [str(miesiac)] * len(d)
    y, pr = np.concatenate(y_all), np.concatenate(p_all)
    blad = pd.DataFrame({"m": mies_all, "b": np.abs(pr - y), "y": y}).groupby("m").apply(
        lambda g: g["b"].mean() / g["y"].mean(), include_groups=False)
    return metryki(y, pr)["nmae"], blad


wyniki, miesiecznie = {}, {}
for klucz, cel in CELE.items():
    cel_b = dataclasses.replace(cel, dodatkowe=NOWE)
    wyniki[klucz] = {"A (5 punktów)": backtest_nmae(df16, cel), "B (+16 punktów)": backtest_nmae(df16, cel_b)}

tabela = pd.DataFrame({k: {w: v[0] for w, v in r.items()} for k, r in wyniki.items()}).T
tabela["zmiana"] = tabela["B (+16 punktów)"] / tabela["A (5 punktów)"] - 1
tabela.style.format({"A (5 punktów)": "{:.2%}", "B (+16 punktów)": "{:.2%}", "zmiana": "{:+.1%}"})

# %% [markdown]
# Czy poprawa jest w każdym miesiącu, czy to efekt jednego dobrego miesiąca?

# %%
pd.concat(
    {k: pd.DataFrame({w: v[1] for w, v in r.items()}) for k, r in wyniki.items()}, axis=1
).style.format("{:.2%}")

# %%
(PROJEKT / "data" / "eksperymenty" / "wynik_punkty.json").write_text(
    json.dumps({k: {w: v[0] for w, v in r.items()} for k, r in wyniki.items()}, indent=2, ensure_ascii=False)
)
