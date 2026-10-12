"""Testy zapytan, ktorymi aplikacja czyta dane z DuckDB."""

import json
from datetime import date

import pandas as pd
import pytest

from energia import magazyn, odczyt


@pytest.fixture
def baza():
    con = magazyn.polacz(":memory:")
    yield con
    con.close()


def zapisz_kwadranse(con, *czasy: str):
    idx = pd.DatetimeIndex([pd.Timestamp(t, tz="UTC") for t in czasy], name="ts_utc")
    magazyn.zapisz_wykonanie(
        con,
        pd.DataFrame(
            {"doba": [t.date() for t in idx], "zapotrzebowanie": 18000.0, "wiatr": 3000.0, "pv": 5000.0,
             "publikacja_utc": pd.Timestamp("2026-10-11 20:00", tz="UTC")},
            index=idx,
        ),
    )


def test_wykonanie_od_zwraca_kwadranse_od_podanego_momentu_w_czasie_polskim(baza):
    zapisz_kwadranse(baza, "2026-10-10 21:45", "2026-10-10 22:00", "2026-10-10 22:15")

    df = odczyt.wykonanie_od(baza, pd.Timestamp("2026-10-10 22:00", tz="UTC"))

    # 22:00 UTC to polnoc czasu polskiego (CEST, UTC+2)
    assert list(df.index) == [
        pd.Timestamp("2026-10-11 00:00", tz="Europe/Warsaw"),
        pd.Timestamp("2026-10-11 00:15", tz="Europe/Warsaw"),
    ]
    assert list(df.columns) == ["Zapotrzebowanie", "Wiatr", "Fotowoltaika", "Rezydualne"]
    assert df.iloc[0]["Rezydualne"] == 10000.0


def test_stan_danych_liczy_brakujace_kwadranse(baza):
    # 10:00, 10:15 i 10:45 sa, brakuje 10:30
    zapisz_kwadranse(baza, "2026-10-11 10:00", "2026-10-11 10:15", "2026-10-11 10:45")

    stan = odczyt.stan_danych(baza)

    assert stan["wykonanie"]["wierszy"] == 3
    assert stan["wykonanie"]["braki"] == 1
    assert stan["wykonanie"]["od"] == pd.Timestamp("2026-10-11 10:00", tz="UTC")
    assert stan["wykonanie"]["do"] == pd.Timestamp("2026-10-11 10:45", tz="UTC")


def test_stan_danych_podaje_ostatnie_pobranie_z_logu(baza):
    magazyn.zapisz_uruchomienie(baza, pd.Timestamp("2026-10-10 20:00", tz="UTC"), "wykonanie", date(2026, 10, 7), date(2026, 10, 10), 10)
    magazyn.zapisz_uruchomienie(baza, pd.Timestamp("2026-10-11 20:00", tz="UTC"), "wykonanie", date(2026, 10, 8), date(2026, 10, 11), 10)

    stan = odczyt.stan_danych(baza)

    assert stan["wykonanie"]["pobrano"] == pd.Timestamp("2026-10-11 20:00", tz="UTC")


def test_stan_pustej_bazy_ma_zera_zamiast_bledu(baza):
    stan = odczyt.stan_danych(baza)

    assert {t: s["wierszy"] for t, s in stan.items()} == {"wykonanie": 0, "plan_pse": 0, "pogoda": 0}
    assert stan["wykonanie"]["braki"] == 0


def test_wyniki_testow_dbt_licza_tylko_testy_i_wymieniaja_nieudane(tmp_path):
    plik = tmp_path / "run_results.json"
    plik.write_text(json.dumps({
        "metadata": {"generated_at": "2026-10-12T18:24:27Z"},
        "results": [
            {"unique_id": "model.energia.fct_energia_godzinowa", "status": "success"},
            {"unique_id": "test.energia.unique_fct_energia_godzinowa_godzina_utc.abc", "status": "pass"},
            {"unique_id": "test.energia.assert_brak_dziur_godzinowych", "status": "fail"},
        ],
    }))

    wynik = odczyt.wyniki_testow_dbt(plik)

    assert wynik["testow"] == 2
    assert wynik["zaliczonych"] == 1
    assert wynik["nieudane"] == ["assert_brak_dziur_godzinowych"]


def test_brak_pliku_z_wynikami_dbt_to_none(tmp_path):
    assert odczyt.wyniki_testow_dbt(tmp_path / "nie_ma.json") is None
