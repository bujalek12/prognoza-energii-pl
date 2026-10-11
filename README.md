# Prognozowanie polskiego systemu energetycznego

Czy da sie prognozowac zapotrzebowanie na energie oraz generacje z wiatru i fotowoltaiki
na dobe naprzod dokladniej niz oficjalny plan operatora (PSE)?

Projekt end-to-end: pipeline danych -> hurtownia -> analiza (Power BI) -> model ML -> wdrozenie.

> Status: **etap 2 / 8 — pipeline danych dziala** (38 testow)

## Dane
- [API PSE](https://api.raporty.pse.pl) — wykonanie KSE (co 15 min), plany koordynacyjne
- [Open-Meteo](https://open-meteo.com) — historyczne prognozy pogody

## Najwazniejsze odkrycia
- Czas lokalny w danych PSE jest niejednoznaczny przy zmianie czasu (`02a:15`, doby 92/100 kwadransow) -> pracujemy w UTC
- Plan PSE dostepny w API jest **nadpisywany do konca doby**, wiec nie jest uczciwym benchmarkiem
  prognozy dobowej -> pipeline archiwizuje kazda publikacje
- Model musi korzystac z **prognoz** pogody, nie z pogody faktycznej (unikamy wycieku danych)
- PSE poprawia dane wykonawcze nawet po kilku miesiacach -> kazde ladowanie odswieza okno ostatnich dob

Szczegoly: [notebook eksploracyjny](notebooks/01_eksploracja.ipynb), [architektura](docs/architektura.md).

## Uruchomienie
```bash
uv sync
uv run python -m energia.pipeline   # pobiera brakujace dane do data/energia.duckdb
uv run streamlit run app/app.py     # aplikacja
uv run pytest                       # testy
```

## Pipeline (etap 2)
| modul | rola |
|---|---|
| `energia/http.py` | GET z ponawianiem (4 proby, backoff 1/2/4 s; 4xx bez ponawiania) |
| `energia/pse.py` | API PSE: paginacja po `nextLink`, klucz czasu UTC, wykrywanie duplikatow |
| `energia/pogoda.py` | historyczne **prognozy** pogody (Open-Meteo) dla 5 punktow |
| `energia/ladowanie.py` | okno ladowania inkrementalnego z 3-dniowym oknem korekt |
| `energia/magazyn.py` | DuckDB: upsert pomiarow, archiwum **kazdej wersji** planu PSE, log uruchomien |
| `energia/pipeline.py` | sklada calosc; idempotentny (ponowne uruchomienie nie dubluje danych) |

## Stack
Python 3.13, uv, httpx, pandas, DuckDB, pytest, Streamlit, Altair · (wkrotce) dbt, LightGBM, MLflow, GitHub Actions
