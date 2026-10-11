"""Surowa warstwa danych w DuckDB (w etapie 3 zbuduje na niej dbt).

Zasady zapisu:
- wykonanie i pogoda: klucz = moment (i punkt), nowsze dane NADPISUJA starsze,
  bo PSE poprawia pomiary wstecz, a my chcemy miec ostatnia, poprawiona wartosc;
- plan PSE: klucz = (kwadrans, moment publikacji), nic nie nadpisujemy,
  bo kazda wersja prognozy jest potrzebna do uczciwego porownania.
Dzieki temu kazde uruchomienie mozna powtorzyc bez dublowania danych (idempotentnosc).
"""

from datetime import date

import duckdb
import pandas as pd

SCHEMAT = """
create table if not exists wykonanie (
    ts_utc          timestamptz primary key,  -- koniec kwadransa
    doba            date not null,            -- doba handlowa PSE
    zapotrzebowanie double not null,          -- MW
    wiatr           double not null,          -- MW
    pv              double not null,          -- MW
    publikacja_utc  timestamptz,              -- kiedy PSE opublikowalo ta wartosc
    pobrano_utc     timestamptz not null      -- kiedy my ja pobralismy
);

create table if not exists plan_pse (
    ts_utc               timestamptz not null,
    publikacja_utc       timestamptz not null,
    doba                 date not null,
    zapotrzebowanie_plan double not null,
    wiatr_plan           double,
    pv_plan              double,
    pobrano_utc          timestamptz not null,
    primary key (ts_utc, publikacja_utc)
);

create table if not exists pogoda (
    ts_utc         timestamptz not null,  -- poczatek godziny, UTC
    punkt          varchar not null,
    temperatura    double,                -- st. C, 2 m
    wiatr_100m     double,                -- km/h, 100 m
    promieniowanie double,                -- W/m2
    zachmurzenie   integer,               -- %
    primary key (ts_utc, punkt)
);

create table if not exists uruchomienia (
    kiedy_utc timestamptz not null,
    zrodlo    varchar not null,
    od        date not null,
    do_       date not null,  -- "do" to slowo kluczowe SQL
    wierszy   integer not null
);
"""

# Z ktorej kolumny liczyc "ostatnia dobe" w kazdej tabeli
_KOLUMNA_DOBY = {
    "wykonanie": "doba",
    "plan_pse": "doba",
    "pogoda": "cast(ts_utc as date)",
}


def polacz(sciezka: str) -> duckdb.DuckDBPyConnection:
    """Otwiera baze (plik albo ":memory:") i zaklada tabele, jesli ich nie ma."""
    con = duckdb.connect(sciezka)
    con.execute("set TimeZone = 'UTC'")  # znaczniki czasu odczytujemy zawsze w UTC
    con.execute(SCHEMAT)
    return con


def ostatnia_doba(con: duckdb.DuckDBPyConnection, tabela: str) -> date | None:
    """Najpozniejsza doba zapisana w tabeli albo None, gdy tabela jest pusta."""
    kolumna = _KOLUMNA_DOBY[tabela]  # slownik zamiast wklejania nazwy z zewnatrz do SQL
    return con.execute(f"select max({kolumna}) from {tabela}").fetchone()[0]


def zapisz_wykonanie(con: duckdb.DuckDBPyConnection, df: pd.DataFrame) -> int:
    """Upsert pomiarow (indeks ts_utc). Zwraca liczbe zapisanych wierszy."""
    nowe = df.reset_index()  # DuckDB czyta ramke pandas po nazwie zmiennej w zapytaniu
    con.execute(
        """
        insert or replace into wykonanie
        select ts_utc, doba, zapotrzebowanie, wiatr, pv, publikacja_utc, now() from nowe
        """
    )
    return len(nowe)


def zapisz_plan(con: duckdb.DuckDBPyConnection, df: pd.DataFrame, pobrano: pd.Timestamp) -> int:
    """Dopisuje do archiwum wersje planu, ktorych jeszcze nie ma. Zwraca liczbe nowych wierszy."""
    przed = con.execute("select count(*) from plan_pse").fetchone()[0]
    nowe = df.assign(pobrano_utc=pobrano)
    con.execute(
        """
        insert or ignore into plan_pse
        select ts_utc, publikacja_utc, doba, zapotrzebowanie_plan, wiatr_plan, pv_plan, pobrano_utc from nowe
        """
    )
    return con.execute("select count(*) from plan_pse").fetchone()[0] - przed


def zapisz_pogode(con: duckdb.DuckDBPyConnection, df: pd.DataFrame) -> int:
    """Upsert prognoz pogody po (godzina, punkt). Zwraca liczbe zapisanych wierszy."""
    con.execute(
        """
        insert or replace into pogoda
        select ts_utc, punkt, temperatura, wiatr_100m, promieniowanie, zachmurzenie from df
        """
    )
    return len(df)


def zapisz_uruchomienie(
    con: duckdb.DuckDBPyConnection, kiedy: pd.Timestamp, zrodlo: str, od: date, do: date, wierszy: int
) -> None:
    """Jeden wiersz logu na zrodlo i uruchomienie: widac, co i kiedy bylo pobierane."""
    con.execute("insert into uruchomienia values (?, ?, ?, ?, ?)", [kiedy, zrodlo, od, do, wierszy])
