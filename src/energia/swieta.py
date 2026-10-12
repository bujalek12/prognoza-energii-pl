"""Polskie swieta ustawowo wolne od pracy. W dni swiateczne zapotrzebowanie na energie
spada jak w niedziele, wiec model i analizy potrzebuja ich listy.

Uruchomienie `python -m energia.swieta` zapisuje seed dla dbt (dbt/seeds/swieta.csv).
"""

import csv
from datetime import date, timedelta
from pathlib import Path

from dateutil.easter import easter

SEED = Path(__file__).resolve().parents[2] / "dbt" / "seeds" / "swieta.csv"


def swieta(rok: int) -> dict[date, str]:
    """Slownik {data: nazwa} wszystkich swiat w danym roku."""
    wielkanoc = easter(rok)  # algorytm gregorianski, ten sam co w kalendarzach koscielnych
    dni = {
        date(rok, 1, 1): "Nowy Rok",
        date(rok, 1, 6): "Trzech Króli",
        wielkanoc: "Wielkanoc",
        wielkanoc + timedelta(days=1): "Poniedziałek Wielkanocny",
        date(rok, 5, 1): "Święto Pracy",
        date(rok, 5, 3): "Święto Konstytucji 3 Maja",
        wielkanoc + timedelta(days=49): "Zielone Świątki",
        wielkanoc + timedelta(days=60): "Boże Ciało",
        date(rok, 8, 15): "Wniebowzięcie NMP",
        date(rok, 11, 1): "Wszystkich Świętych",
        date(rok, 11, 11): "Święto Niepodległości",
        date(rok, 12, 25): "Boże Narodzenie",
        date(rok, 12, 26): "Drugi dzień Bożego Narodzenia",
    }
    if rok >= 2025:  # Wigilia wolna od pracy od 2025 r. (nowelizacja ustawy z 2024 r.)
        dni[date(rok, 12, 24)] = "Wigilia"
    return dni


def zapisz_seed(od_roku: int = 2024, do_roku: int = 2030, sciezka: Path = SEED) -> None:
    sciezka.parent.mkdir(parents=True, exist_ok=True)
    with sciezka.open("w", newline="", encoding="utf-8") as f:
        pisz = csv.writer(f)
        pisz.writerow(["data", "nazwa"])
        for rok in range(od_roku, do_roku + 1):
            for dzien, nazwa in sorted(swieta(rok).items()):
                pisz.writerow([dzien.isoformat(), nazwa])


if __name__ == "__main__":
    zapisz_seed()
