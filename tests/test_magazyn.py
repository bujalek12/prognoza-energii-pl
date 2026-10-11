"""Testy zapisu do DuckDB. Baza w pamieci (":memory:"): prawdziwy DuckDB, bez pliku na dysku."""

from datetime import date

import pandas as pd
import pytest

from energia import magazyn


@pytest.fixture
def baza():
    con = magazyn.polacz(":memory:")
    yield con
    con.close()


def wykonanie(*kwadranse: tuple[str, float]) -> pd.DataFrame:
    idx = pd.DatetimeIndex([pd.Timestamp(t, tz="UTC") for t, _ in kwadranse], name="ts_utc")
    return pd.DataFrame(
        {
            "doba": [idx[i].date() for i in range(len(idx))],
            "zapotrzebowanie": [v for _, v in kwadranse],
            "wiatr": 1000.0,
            "pv": 0.0,
            "publikacja_utc": pd.Timestamp("2026-10-11 20:00", tz="UTC"),
        },
        index=idx,
    )


def plan(ts: str, publikacja: str, zapotrzebowanie: float) -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "ts_utc": pd.Timestamp(ts, tz="UTC"),
                "publikacja_utc": pd.Timestamp(publikacja, tz="UTC"),
                "doba": pd.Timestamp(ts).date(),
                "zapotrzebowanie_plan": zapotrzebowanie,
                "wiatr_plan": 1000.0,
                "pv_plan": 0.0,
            }
        ]
    )


# --- Wykonanie --------------------------------------------------------------------------


def test_pusta_baza_nie_ma_ostatniej_doby(baza):
    assert magazyn.ostatnia_doba(baza, "wykonanie") is None


def test_ostatnia_doba_to_najpozniejsza_zapisana(baza):
    magazyn.zapisz_wykonanie(baza, wykonanie(("2026-10-09 10:00", 1.0), ("2026-10-10 10:00", 2.0)))

    assert magazyn.ostatnia_doba(baza, "wykonanie") == date(2026, 10, 10)


def test_ponowny_zapis_tego_samego_kwadransa_nadpisuje_zamiast_dublowac(baza):
    # PSE poprawia dane wstecz: nowsza wartosc ma zastapic stara, a nie dodac drugi wiersz
    magazyn.zapisz_wykonanie(baza, wykonanie(("2026-10-10 10:00", 15000.0)))
    magazyn.zapisz_wykonanie(baza, wykonanie(("2026-10-10 10:00", 15100.0)))

    assert baza.sql("select zapotrzebowanie from wykonanie").fetchall() == [(15100.0,)]


def test_zapis_zwraca_liczbe_zapisanych_wierszy(baza):
    assert magazyn.zapisz_wykonanie(baza, wykonanie(("2026-10-10 10:00", 1.0), ("2026-10-10 10:15", 2.0))) == 2


# --- Archiwum planu PSE -------------------------------------------------------------------


def test_archiwum_planu_trzyma_kazda_wersje_publikacji(baza):
    # Ten sam kwadrans, dwie publikacje: obie zostaja, bo do benchmarku potrzebna jest ta sprzed doby
    magazyn.zapisz_plan(baza, plan("2026-10-12 10:00", "2026-10-11 12:00", 17000.0), pobrano=pd.Timestamp("2026-10-11 13:00", tz="UTC"))
    magazyn.zapisz_plan(baza, plan("2026-10-12 10:00", "2026-10-12 09:00", 17500.0), pobrano=pd.Timestamp("2026-10-12 10:00", tz="UTC"))

    assert baza.sql("select zapotrzebowanie_plan from plan_pse order by publikacja_utc").fetchall() == [(17000.0,), (17500.0,)]


def test_ta_sama_publikacja_pobrana_drugi_raz_nie_tworzy_duplikatu(baza):
    # Pierwsze pobranie zostaje, bo pokazuje najwczesniejszy moment, kiedy znalismy te wersje
    magazyn.zapisz_plan(baza, plan("2026-10-12 10:00", "2026-10-11 12:00", 17000.0), pobrano=pd.Timestamp("2026-10-11 13:00", tz="UTC"))
    nowe = magazyn.zapisz_plan(baza, plan("2026-10-12 10:00", "2026-10-11 12:00", 17000.0), pobrano=pd.Timestamp("2026-10-11 18:00", tz="UTC"))

    assert nowe == 0
    assert baza.sql("select pobrano_utc from plan_pse").fetchall() == [(pd.Timestamp("2026-10-11 13:00", tz="UTC").to_pydatetime(),)]


# --- Pogoda -------------------------------------------------------------------------------


def test_pogoda_nadpisuje_ten_sam_punkt_i_godzine(baza):
    def pogoda(wiatr: float) -> pd.DataFrame:
        return pd.DataFrame(
            [{"ts_utc": pd.Timestamp("2026-10-10 10:00", tz="UTC"), "punkt": "Pomorze", "temperatura": 10.0,
              "wiatr_100m": wiatr, "promieniowanie": 0.0, "zachmurzenie": 50}]
        )

    magazyn.zapisz_pogode(baza, pogoda(20.0))
    magazyn.zapisz_pogode(baza, pogoda(22.0))

    assert baza.sql("select wiatr_100m from pogoda").fetchall() == [(22.0,)]


# --- Log uruchomien -----------------------------------------------------------------------


def test_log_zapamietuje_uruchomienia(baza):
    magazyn.zapisz_uruchomienie(baza, pd.Timestamp("2026-10-11 20:00", tz="UTC"), "wykonanie", date(2026, 10, 8), date(2026, 10, 11), 384)

    assert baza.sql("select zrodlo, od, do_, wierszy from uruchomienia").fetchall() == [
        ("wykonanie", date(2026, 10, 8), date(2026, 10, 11), 384)
    ]
