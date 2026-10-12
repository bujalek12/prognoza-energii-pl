"""Eksport tabel marts do plikow Parquet dla Power BI.

Uruchomienie: uv run python -m energia.eksport   (pliki trafiaja do powerbi/dane/)

Dlaczego Parquet: Power BI czyta go natywnie (Pobierz dane -> Parquet), zachowuje typy
kolumn (daty, liczby) i jest kilka razy mniejszy od CSV. Nie trzeba sterownika ODBC do DuckDB.
"""

from pathlib import Path

import duckdb

from energia.pipeline import BAZA, PROJEKT

KATALOG = PROJEKT / "powerbi" / "dane"
TABELE = ["fct_energia_godzinowa", "fct_bilans_dzienny", "dim_data"]


def eksportuj(baza: Path = BAZA, katalog: Path = KATALOG) -> list[Path]:
    """Zapisuje kazda tabele z TABELE jako <katalog>/<tabela>.parquet. Zwraca liste plikow."""
    katalog.mkdir(parents=True, exist_ok=True)
    pliki = []
    with duckdb.connect(str(baza), read_only=True) as con:
        # Power BI nie rozumie stref czasowych w Parquet. Ustawiamy sesje na UTC i rzutujemy
        # timestamptz -> timestamp, wiec godzina_utc trafia jako zwykly czas w UTC.
        con.execute("set TimeZone = 'UTC'")
        for tabela in TABELE:
            kolumny = con.execute(
                "select column_name, data_type from information_schema.columns "
                "where table_schema = 'marts' and table_name = ? order by ordinal_position",
                [tabela],
            ).fetchall()
            wybor = ", ".join(
                f'"{nazwa}"::timestamp as "{nazwa}"' if typ.startswith("TIMESTAMP WITH TIME ZONE") else f'"{nazwa}"'
                for nazwa, typ in kolumny
            )
            plik = katalog / f"{tabela}.parquet"
            con.execute(f"copy (select {wybor} from marts.{tabela}) to '{plik}' (format parquet)")
            pliki.append(plik)
    return pliki


if __name__ == "__main__":
    for plik in eksportuj():
        print(f"{plik.relative_to(PROJEKT)}  {plik.stat().st_size / 1e6:.1f} MB")
