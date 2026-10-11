# Prognozowanie polskiego systemu energetycznego

Czy da sie prognozowac zapotrzebowanie na energie oraz generacje z wiatru i fotowoltaiki
na dobe naprzod dokladniej niz oficjalny plan operatora (PSE)?

Projekt end-to-end: pipeline danych -> hurtownia -> analiza (Power BI) -> model ML -> wdrozenie.

> Status: **etap 1 / 8 — eksploracja danych zakonczona**

## Dane
- [API PSE](https://api.raporty.pse.pl) — wykonanie KSE (co 15 min), plany koordynacyjne
- [Open-Meteo](https://open-meteo.com) — historyczne prognozy pogody

## Najwazniejsze odkrycia (etap 1)
- Czas lokalny w danych PSE jest niejednoznaczny przy zmianie czasu (`02a:15`, doby 92/100 kwadransow) -> pracujemy w UTC
- Plan PSE dostepny w API jest **nadpisywany do konca doby**, wiec nie jest uczciwym benchmarkiem
  prognozy dobowej -> pipeline archiwizuje kazda publikacje
- Model musi korzystac z **prognoz** pogody, nie z pogody faktycznej (unikamy wycieku danych)

Szczegoly: [notebook eksploracyjny](notebooks/01_eksploracja.ipynb), [architektura](docs/architektura.md).

## Uruchomienie
```bash
uv sync
uv run streamlit run app/app.py   # panel projektu: postep + dane na zywo
uv run jupyter lab                # notebooki
```

## Stack
Python 3.13, uv, httpx, pandas, Streamlit, Altair · (wkrotce) DuckDB, dbt, LightGBM, MLflow, GitHub Actions
