"""Zapytania do DuckDB uzywane przez aplikacje Streamlit."""

import json
from pathlib import Path

import duckdb
import pandas as pd

TABELE = {
    # tabela: (kolumna czasu, krok w minutach dla liczenia brakow albo None)
    "wykonanie": ("ts_utc", 15),
    "plan_pse": ("ts_utc", None),  # wiele wersji na kwadrans, braki nie maja sensu
    "pogoda": ("ts_utc", None),  # 5 punktow na godzine, braki liczymy w etapie 3 (dbt)
}


def wykonanie_od(con: duckdb.DuckDBPyConnection, od_utc: pd.Timestamp) -> pd.DataFrame:
    """Pomiary od podanego momentu; indeks w czasie polskim, nazwy kolumn do wyswietlenia."""
    df = con.execute(
        """
        select ts_utc, zapotrzebowanie, wiatr, pv
        from wykonanie
        where ts_utc >= ?
        order by ts_utc
        """,
        [od_utc],
    ).df()
    df["czas"] = pd.to_datetime(df.pop("ts_utc"), utc=True).dt.tz_convert("Europe/Warsaw")
    df = df.set_index("czas").rename(
        columns={"zapotrzebowanie": "Zapotrzebowanie", "wiatr": "Wiatr", "pv": "Fotowoltaika"}
    )
    # Zapotrzebowanie rezydualne: to, co musza pokryc zrodla konwencjonalne i import
    df["Rezydualne"] = df["Zapotrzebowanie"] - df["Wiatr"] - df["Fotowoltaika"]
    return df


def stan_danych(con: duckdb.DuckDBPyConnection) -> dict[str, dict]:
    """Dla kazdej tabeli: liczba wierszy, zakres czasu, ostatnie pobranie i (dla wykonania) braki."""
    stan = {}
    for tabela, (kolumna, krok) in TABELE.items():
        wierszy, od, do = con.execute(f"select count(*), min({kolumna}), max({kolumna}) from {tabela}").fetchone()
        pobrano = con.execute("select max(kiedy_utc) from uruchomienia where zrodlo = ?", [tabela]).fetchone()[0]
        braki = 0
        if krok and wierszy:
            # ile kwadransow powinno byc miedzy pierwszym a ostatnim, minus ile jest
            oczekiwane = int((pd.Timestamp(do) - pd.Timestamp(od)) / pd.Timedelta(minutes=krok)) + 1
            braki = oczekiwane - wierszy
        stan[tabela] = {
            "wierszy": wierszy,
            "od": pd.Timestamp(od) if od else None,
            "do": pd.Timestamp(do) if do else None,
            "pobrano": pd.Timestamp(pobrano) if pobrano else None,
            "braki": braki,
        }
    return stan


def wyniki_testow_dbt(run_results: Path) -> dict | None:
    """Podsumowanie testow z ostatniego `dbt build` (plik dbt/target/run_results.json)."""
    if not run_results.exists():
        return None
    dane = json.loads(run_results.read_text())
    testy = [r for r in dane["results"] if r["unique_id"].startswith("test.")]
    return {
        "testow": len(testy),
        "zaliczonych": sum(r["status"] == "pass" for r in testy),
        "nieudane": [r["unique_id"].split(".")[2] for r in testy if r["status"] in ("fail", "error")],
        "kiedy": pd.Timestamp(dane["metadata"]["generated_at"]),
    }
