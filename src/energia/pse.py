"""Klient API raportow PSE (https://api.raporty.pse.pl).

API zwraca max 100 wierszy na strone i link do kolejnej w polu `nextLink`.
Polaczenie bywa zrywane, wiec bledy sieci i serwera ponawiamy z rosnacym odstepem.
"""

import time
from collections.abc import Callable
from datetime import date

import httpx
import pandas as pd

PSE_API = "https://api.raporty.pse.pl/api"
PROBY = 4


class BladPobierania(Exception):
    """API nie zwrocilo danych mimo ponowien albo odrzucilo zapytanie."""


def _pobierz_strone(
    klient: httpx.Client, url: str, params: dict | None, czekaj: Callable[[float], None]
) -> dict:
    for proba in range(PROBY):
        try:
            odp = klient.get(url, params=params)
        except httpx.TransportError as e:
            blad = f"blad polaczenia: {e}"
        else:
            if odp.is_success:
                return odp.json()
            # 4xx to blad zapytania (zla nazwa raportu, zly filtr): ponawianie nic nie zmieni
            if odp.is_client_error and odp.status_code != 429:
                raise BladPobierania(f"{url}: HTTP {odp.status_code}")
            blad = f"HTTP {odp.status_code}"
        if proba < PROBY - 1:
            czekaj(2**proba)
    raise BladPobierania(f"{url}: {blad} (po {PROBY} probach)")


def pobierz_raport(
    raport: str,
    od: date,
    do: date,
    klient: httpx.Client | None = None,
    czekaj: Callable[[float], None] = time.sleep,
) -> list[dict]:
    """Pobiera wszystkie wiersze raportu dla dob handlowych od `od` do `do` wlacznie."""
    wlasny_klient = klient is None
    klient = klient or httpx.Client(base_url=PSE_API, timeout=60)
    try:
        url: str | None = raport  # wzgledem base_url klienta; nextLink jest juz pelnym adresem
        params: dict | None = {"$filter": f"business_date ge '{od}' and business_date le '{do}'"}
        wiersze: list[dict] = []
        while url:
            dane = _pobierz_strone(klient, url, params, czekaj)
            wiersze.extend(dane["value"])
            url = dane.get("nextLink")
            params = None  # nextLink zawiera juz wszystkie parametry
        return wiersze
    finally:
        if wlasny_klient:
            klient.close()


def wykonanie_do_ramki(wiersze: list[dict]) -> pd.DataFrame:
    """Raport his-wlk-cal -> ramka z kluczem ts_utc (koniec kwadransa, UTC).

    Czasu lokalnego z PSE nie uzywamy: przy zmianie czasu ma zapisy typu "02a:15".
    """
    df = pd.DataFrame(wiersze, columns=["dtime_utc", "business_date", "demand", "wi", "pv", "publication_ts_utc"])
    df = df.dropna(subset=["demand", "wi", "pv"])
    df["ts_utc"] = pd.to_datetime(df["dtime_utc"]).dt.tz_localize("UTC")
    if df["ts_utc"].duplicated().any():
        raise ValueError(f"duplikat kwadransa w danych PSE: {df.loc[df['ts_utc'].duplicated(), 'ts_utc'].tolist()}")
    return (
        df.assign(
            doba=pd.to_datetime(df["business_date"]).dt.date,
            publikacja_utc=pd.to_datetime(df["publication_ts_utc"]).dt.tz_localize("UTC"),
        )
        .rename(columns={"demand": "zapotrzebowanie", "wi": "wiatr", "pv": "pv"})
        .set_index("ts_utc")
        .sort_index()[["doba", "zapotrzebowanie", "wiatr", "pv", "publikacja_utc"]]
    )
