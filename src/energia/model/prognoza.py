"""Prognoza na jutro: cechy z historii pomiarow + prognoza pogody + kalendarz -> modele LightGBM.

Uruchomienie: uv run python -m energia.model.prognoza  (zwykle wola ja pipeline po dbt build)
Wynik trafia do tabeli prognozy_modelu z momentem wygenerowania, zeby pozniej rozliczyc trafnosc.
"""

import json
import logging
from datetime import date, timedelta

import duckdb
import lightgbm as lgb
import numpy as np
import pandas as pd

from energia import magazyn
from energia.model.backtest import poszerz
from energia.model.cechy import dodaj_opoznienia
from energia.model.trening import CELE, KATALOG, KWANTYLE, dodaj_cechy_czasu

log = logging.getLogger("energia.model")


def ramka_prognozy(historia: pd.DataFrame, przyszle: pd.DataFrame) -> pd.DataFrame:
    """Doklada do przyszlych godzin cechy z przeszlosci (lagi, srednie, maksima) z `historia`.

    historia: pomiary (indeks godzina_utc, kolumny celow), przyszle: godziny do prognozy z
    kalendarzem i pogoda. Opoznienia >= 48 h, wiec dla jutra siegaja tylko do danych juz znanych.
    """
    cele = [c.nazwa for c in CELE.values()]
    # historia daje wartosci celow, przyszle wiersze maja je puste (NaN) i maja pogode z kalendarzem
    # godziny obecne w obu ramkach (prognoza na czesciowo zmierzona dobe) laczymy w jeden wiersz:
    # wartosci celow z historii, kalendarz i pogoda z przyszlych
    razem = historia[cele].combine_first(przyszle.drop(columns=cele, errors="ignore")).sort_index()
    for cel in cele:
        razem = dodaj_opoznienia(razem, cel)
    return razem.loc[przyszle.index]


def posortuj_kwantyle(df: pd.DataFrame) -> pd.DataFrame:
    """Osobne modele kwantylowe moga dac p10 > p50. Sortujemy wartosci w wierszu: p10 <= p50 <= p90."""
    wynik = df.copy()
    wynik[["p10", "p50", "p90"]] = np.sort(df[["p10", "p50", "p90"]].to_numpy(), axis=1)
    return wynik


def prognozuj(con: duckdb.DuckDBPyConnection, doba: date) -> pd.DataFrame:
    """Prognoza wszystkich celow na dobe (czas polski). Zwraca ramke: godzina_utc, cel, p10, p50, p90."""
    historia = con.sql(
        "select godzina_utc, zapotrzebowanie_mw, wiatr_mw, pv_mw from marts.fct_energia_godzinowa"
    ).df()
    historia = historia.set_index(pd.to_datetime(historia.pop("godzina_utc"), utc=True))
    przyszle = con.execute(
        """
        select c.godzina_utc, c.data, c.godzina, c.dzien_tygodnia, c.miesiac, c.czy_swieto, c.czy_dzien_roboczy, w.*
        exclude (godzina_utc, liczba_punktow)
        from marts.dim_czas c
        join intermediate.int_pogoda_prognoza_godzinowa w using (godzina_utc)
        where c.data = ?
        order by c.godzina_utc
        """,
        [doba],
    ).df()
    if przyszle.empty:
        raise RuntimeError(f"brak prognozy pogody albo kalendarza na {doba}")
    przyszle = przyszle.set_index(pd.to_datetime(przyszle.pop("godzina_utc"), utc=True))
    ramka = dodaj_cechy_czasu(ramka_prognozy(historia, przyszle))

    kalibracja = json.loads((KATALOG / "metryki.json").read_text())
    wyniki = []
    for klucz, cel in CELE.items():
        skala = np.maximum(ramka[f"{cel.nazwa}_max30"].to_numpy(), 1.0) if cel.wzgledny else 1.0
        wynik = pd.DataFrame({"godzina_utc": ramka.index, "cel": klucz})
        for q in KWANTYLE:
            model = lgb.Booster(model_file=str(KATALOG / f"{klucz}_p{int(q * 100)}.txt"))
            wynik[f"p{int(q * 100)}"] = np.maximum(model.predict(ramka[cel.cechy]) * skala, 0.0)
        wynik = posortuj_kwantyle(wynik)
        # kalibracja konformalna z backtestu: surowe przedzialy kwantylowe byly za waskie
        k = kalibracja.get(cel.nazwa, {}).get("kalibracja", {}).get("k", 0.0)
        dol, gora = poszerz(wynik["p10"].to_numpy(), wynik["p90"].to_numpy(), k)
        wynik["p10"], wynik["p90"] = np.maximum(dol, 0.0), gora
        wyniki.append(wynik)
    return pd.concat(wyniki, ignore_index=True)


def prognozuj_i_zapisz(con: duckdb.DuckDBPyConnection, doba: date | None = None) -> int:
    doba = doba or date.today() + timedelta(days=1)
    prognoza = prognozuj(con, doba)
    n = magazyn.zapisz_prognoze_modelu(con, prognoza, wygenerowano=pd.Timestamp.now(tz="UTC"))
    log.info("prognoza na %s: %d wierszy", doba, n)
    return n


if __name__ == "__main__":
    from energia.pipeline import BAZA

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    with magazyn.polacz(str(BAZA)) as con:
        prognozuj_i_zapisz(con)
