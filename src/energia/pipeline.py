"""Codzienna aktualizacja danych: PSE (wykonanie + plan) i Open-Meteo -> DuckDB.

Uruchomienie:  uv run python -m energia.pipeline            (baza: data/energia.duckdb)
               uv run python -m energia.pipeline --baza x.duckdb
"""

import argparse
import logging
import time
from collections.abc import Callable
from datetime import date, timedelta
from pathlib import Path

import duckdb
import httpx
import pandas as pd

from energia import magazyn
from energia.ladowanie import okno_do_pobrania
from energia.pogoda import pobierz_pogode
from energia.pse import plan_do_ramki, pobierz_raport, wykonanie_do_ramki

POCZATEK_HISTORII = date(2024, 6, 14)  # pierwsza doba dostepna w API PSE
BAZA = Path(__file__).resolve().parents[2] / "data" / "energia.duckdb"

log = logging.getLogger("energia")


def aktualizuj(
    con: duckdb.DuckDBPyConnection,
    dzis: date,
    klient_pse: httpx.Client | None = None,
    klient_pogoda: httpx.Client | None = None,
    czekaj: Callable[[float], None] = time.sleep,
) -> dict[str, int]:
    """Dociaga brakujace dane ze wszystkich zrodel. Zwraca liczbe zapisanych wierszy na zrodlo.

    Kazde zrodlo jest niezalezne: awaria jednego (np. PSE nie odpowiada) nie blokuje
    pozostalych. Nieudane zrodlo trafia do logu z wierszy = -1, a na koniec funkcja
    zglasza blad, zeby harmonogram (cron, GitHub Actions) oznaczyl uruchomienie jako nieudane.
    """
    teraz = pd.Timestamp.now(tz="UTC")
    jutro = dzis + timedelta(days=1)

    def wykonanie(od: date, do: date) -> int:
        df = wykonanie_do_ramki(pobierz_raport("his-wlk-cal", od, do, klient=klient_pse, czekaj=czekaj))
        return magazyn.zapisz_wykonanie(con, df)

    def plan(od: date, do: date) -> int:
        # Zapisujemy tylko nowe wersje planu; stare zostaja w archiwum.
        df = plan_do_ramki(pobierz_raport("pdgobpkd", od, do, klient=klient_pse, czekaj=czekaj))
        return magazyn.zapisz_plan(con, df, pobrano=teraz)

    def pogoda(od: date, do: date) -> int:
        return magazyn.zapisz_pogode(con, pobierz_pogode(od, do, klient=klient_pogoda, czekaj=czekaj))

    # (zrodlo, funkcja pobierajaca, do kiedy pobierac)
    # Plan PSE siega do JUTRA, bo plan na jutro publikowany jest dzis. Dlatego jako "dzis"
    # podajemy jutro: w bazie legalnie jest juz doba jutrzejsza i nie moze to byc blad.
    kroki = [("wykonanie", wykonanie, dzis), ("plan_pse", plan, jutro), ("pogoda", pogoda, dzis)]

    wynik: dict[str, int] = {}
    nieudane: list[str] = []
    for zrodlo, pobierz, koniec in kroki:
        od, do = okno_do_pobrania(magazyn.ostatnia_doba(con, zrodlo), koniec, POCZATEK_HISTORII)
        log.info("%s: %s .. %s", zrodlo, od, do)
        try:
            wynik[zrodlo] = pobierz(od, do)
        except Exception:
            log.exception("%s: nie udalo sie pobrac danych", zrodlo)
            nieudane.append(zrodlo)
            magazyn.zapisz_uruchomienie(con, teraz, zrodlo, od, do, -1)
            continue
        magazyn.zapisz_uruchomienie(con, teraz, zrodlo, od, do, wynik[zrodlo])

    log.info("zapisano: %s", wynik)
    if nieudane:
        raise RuntimeError(f"nie udalo sie pobrac: {', '.join(nieudane)}")
    return wynik


def main() -> None:
    parser = argparse.ArgumentParser(description="Aktualizacja danych energetycznych w DuckDB")
    parser.add_argument("--baza", type=Path, default=BAZA, help="sciezka do pliku DuckDB")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    logging.getLogger("httpx").setLevel(logging.WARNING)  # bez linii na kazde zapytanie HTTP
    args.baza.parent.mkdir(parents=True, exist_ok=True)
    with magazyn.polacz(str(args.baza)) as con:
        aktualizuj(con, dzis=date.today())


if __name__ == "__main__":
    main()
