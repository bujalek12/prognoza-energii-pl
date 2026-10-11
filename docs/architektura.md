# Architektura

Decyzje wynikaja z eksploracji danych (`notebooks/01_eksploracja.ipynb`).

```
 ZRODLA                 INGESTIA (Python)            HURTOWNIA (DuckDB + dbt)         KONSUMPCJA
 ─────────              ─────────────────            ────────────────────────         ──────────
 PSE his-wlk-cal ─┐                                  raw      -> surowe JSON-y
 (wykonanie)      │     - paginacja nextLink         staging  -> typy, UTC, deduplikacja     Power BI
                  ├──>  - retry + backoff     ──>    marts    -> fakt_energia_h,       ──>  Model ML (LightGBM)
 PSE pdgobpkd ────┤     - walidacja (pydantic)                   fakt_prognoza_pse,         Streamlit
 (plan PSE)       │     - ladowanie inkrementalne                fakt_pogoda_prognoza,
                  │     - SNAPSHOT prognoz                       dim_czas, dim_swieta
 Open-Meteo ──────┘       (zapis momentu pobrania)
 historical forecast
```

## Decyzje

| # | Decyzja | Powod (odkrycie z eksploracji) |
|---|---------|-------------------------------|
| 1 | Klucz czasu = `ts_utc`; czas lokalny wyliczany z UTC | Czas lokalny PSE ma zapisy `02a:15` i doby 92/96/100 kwadransow |
| 2 | Pobieranie z paginacja po `nextLink` | API zwraca max 100 wierszy na strone |
| 3 | Archiwum kazdej publikacji prognozy PSE (`pobrano_ts`) | API nadpisuje plan; ostatnia wersja publikowana ~22,5 h po starcie doby |
| 4 | Pogoda tylko z *historical forecast* | Reanaliza = faktyczna pogoda = wyciek danych |
| 5 | Retry z wykladniczym backoffem | Zerwane polaczenia podczas eksploracji |
| 6 | Model na rozdzielczosci godzinowej | Pogoda jest godzinowa, PSE 15-minutowe |
| 7 | Kalendarz swiat jako wymiar | Wyrazny spadek popytu w Wielkanoc |
| 8 | Ladowanie idempotentne (upsert po kluczu) | Ponowne uruchomienie nie moze dublowac danych |

## Rozstrzygniete w etapie 2
- **Czy dane wykonawcze bywaja korygowane?** Tak, nawet po miesiacach (26.10.2025 opublikowane
  ponownie 18.01.2026). Pipeline odswieza 3 ostatnie doby przy kazdym ladowaniu; pelne
  przeladowanie okresowe w etapie 7.

## Otwarte pytania
- Definicje `kse_pow_dem` (plan) vs `demand` (wykonanie) — dokumentacja PSE
- Dwie galezie na wykresie PV vs promieniowanie — przesuniecie czasowe? (etap 5)
