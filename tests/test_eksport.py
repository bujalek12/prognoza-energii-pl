"""Testy eksportu tabel marts do plikow Parquet dla Power BI."""

import duckdb
import pandas as pd
import pytest

from energia.eksport import TABELE, eksportuj


@pytest.fixture
def baza(tmp_path):
    """Plik DuckDB z minimalnymi tabelami marts (jak po dbt build)."""
    sciezka = tmp_path / "test.duckdb"
    with duckdb.connect(str(sciezka)) as con:
        con.execute("set TimeZone = 'UTC'")
        con.execute("create schema marts")
        con.execute("""create table marts.fct_energia_godzinowa as
            select timestamptz '2026-10-11 08:00:00+00' as godzina_utc, timestamp '2026-10-11 10:00:00' as czas_lokalny,
                   date '2026-10-11' as data, 18000.0 as zapotrzebowanie_mw""")
        con.execute("create table marts.fct_bilans_dzienny as select date '2026-10-11' as data, 430.5 as zapotrzebowanie_gwh")
        con.execute("create table marts.dim_data as select date '2026-10-11' as data, 'sobota' as typ_dnia")
    return sciezka


def test_zapisuje_po_jednym_pliku_parquet_na_tabele(baza, tmp_path):
    katalog = tmp_path / "dane"

    pliki = eksportuj(baza, katalog)

    assert sorted(p.name for p in pliki) == sorted(f"{t}.parquet" for t in TABELE)
    assert pd.read_parquet(katalog / "fct_bilans_dzienny.parquet").to_dict("records") == [
        {"data": pd.Timestamp("2026-10-11").date(), "zapotrzebowanie_gwh": 430.5}
    ]


def test_czas_w_power_bi_jest_bez_strefy_czasowej(baza, tmp_path):
    # Power BI nie obsluguje stref w Parquet: godzina UTC trafia jako zwykly znacznik czasu w UTC
    eksportuj(baza, tmp_path)

    df = pd.read_parquet(tmp_path / "fct_energia_godzinowa.parquet")

    assert df["godzina_utc"].dt.tz is None
    assert df["godzina_utc"].iloc[0] == pd.Timestamp("2026-10-11 08:00")
    assert df["czas_lokalny"].iloc[0] == pd.Timestamp("2026-10-11 10:00")


def test_ponowny_eksport_nadpisuje_pliki(baza, tmp_path):
    eksportuj(baza, tmp_path)
    eksportuj(baza, tmp_path)

    assert len(pd.read_parquet(tmp_path / "dim_data.parquet")) == 1
