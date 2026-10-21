"""Historyczne prognozy pogody z Open-Meteo dla kilku punktow w Polsce.

Uzywamy *prognoz* (historical-forecast-api), a nie pomiarow (reanalizy): model bedzie
prognozowal jutro majac tylko prognoze pogody, wiec na takich samych danych musi sie uczyc.
"""

import time
from collections.abc import Callable
from datetime import date, timedelta

import httpx
import pandas as pd

from energia.http import pobierz_json

API = "https://historical-forecast-api.open-meteo.com/v1/forecast"
API_PROGNOZ = "https://api.open-meteo.com/v1/forecast"  # aktualna prognoza na najblizsze dni
KAWALEK_DNI = 90  # dlugie zakresy dzielimy, zeby jedna odpowiedz nie byla ogromna i nie lapala timeoutu

# Stolice 16 wojewodztw + Pomorze (rejon z najwieksza liczba farm wiatrowych). Pierwotnie bylo
# 5 punktow; eksperyment w notebooks/03 pokazal, ze 16 wojewodztw zmniejsza blad prognozy wiatru
# o 19%, a PV o 7%. Nazwy pierwszych 5 zostaja, bo uzywa ich hurtownia (Poznan = "Wielkopolska",
# Katowice = "Slask", Lublin = "Lubelskie").
PUNKTY: dict[str, tuple[float, float]] = {
    "Pomorze": (54.5, 17.0),
    "Wielkopolska": (52.4, 16.9),
    "Warszawa": (52.23, 21.01),
    "Slask": (50.26, 19.02),
    "Lubelskie": (51.25, 22.57),
    "Bialystok": (53.13, 23.16),
    "Bydgoszcz": (53.12, 18.01),
    "Gdansk": (54.35, 18.65),
    "Gorzow": (52.73, 15.24),
    "Kielce": (50.87, 20.63),
    "Krakow": (50.06, 19.94),
    "Lodz": (51.76, 19.46),
    "Olsztyn": (53.78, 20.48),
    "Opole": (50.67, 17.93),
    "Rzeszow": (50.04, 22.00),
    "Szczecin": (53.43, 14.55),
    "Wroclaw": (51.11, 17.03),
}
# Polnoc kraju: tu stoi wiekszosc farm wiatrowych, wiec osobna srednia wiatru dla tego rejonu
PUNKTY_POLNOCNE = {"Pomorze", "Gdansk", "Szczecin", "Olsztyn", "Bydgoszcz", "Bialystok", "Gorzow"}

# nazwa w Open-Meteo -> nazwa w naszej bazie
ZMIENNE = {
    "temperature_2m": "temperatura",
    "wind_speed_100m": "wiatr_100m",  # wysokosc piasty turbiny, lepsza niz wiatr przy ziemi
    "shortwave_radiation": "promieniowanie",
    "cloud_cover": "zachmurzenie",
}


def _do_ramki(dane: dict, punkt: str) -> pd.DataFrame:
    godz = pd.DataFrame(dane["hourly"])
    return pd.DataFrame(
        {
            "ts_utc": pd.to_datetime(godz["time"]).dt.tz_localize("UTC"),
            "punkt": punkt,
            **{nasza: godz[ich] for ich, nasza in ZMIENNE.items()},
        }
    )


def _kawalki(od: date, do: date) -> list[tuple[date, date]]:
    """Dzieli [od, do] na kolejne zakresy po najwyzej KAWALEK_DNI dni (obie granice wlacznie)."""
    kawalki = []
    while od <= do:
        koniec = min(do, od + timedelta(days=KAWALEK_DNI - 1))
        kawalki.append((od, koniec))
        od = koniec + timedelta(days=1)
    return kawalki


def pobierz_pogode(
    od: date,
    do: date,
    punkty: dict[str, tuple[float, float]] = PUNKTY,
    klient: httpx.Client | None = None,
    czekaj: Callable[[float], None] = time.sleep,
) -> pd.DataFrame:
    """Godzinowe prognozy pogody dla kazdego punktu; jedna ramka, kolumna `punkt` rozroznia miejsca."""
    wlasny_klient = klient is None
    klient = klient or httpx.Client(timeout=120)
    try:
        ramki = []
        for nazwa, (lat, lon) in punkty.items():
            for poczatek, koniec in _kawalki(od, do):
                dane = pobierz_json(
                    klient,
                    API,
                    params={
                        "latitude": lat,
                        "longitude": lon,
                        "start_date": str(poczatek),
                        "end_date": str(koniec),
                        "hourly": ",".join(ZMIENNE),
                        "timezone": "UTC",  # jak w calym projekcie: bez czasu lokalnego
                    },
                    czekaj=czekaj,
                )
                ramki.append(_do_ramki(dane, nazwa))
        return pd.concat(ramki, ignore_index=True)
    finally:
        if wlasny_klient:
            klient.close()



def pobierz_prognoze_pogody(
    punkty: dict[str, tuple[float, float]] = PUNKTY,
    klient: httpx.Client | None = None,
    czekaj: Callable[[float], None] = time.sleep,
) -> pd.DataFrame:
    """Aktualna prognoza pogody na dzis i 2 kolejne dni (do prognozy modelu na jutro).

    Te same zmienne i ten sam format co pobierz_pogode(), wiec model dostaje cechy takie jak w treningu.
    """
    wlasny_klient = klient is None
    klient = klient or httpx.Client(timeout=60)
    try:
        ramki = []
        for nazwa, (lat, lon) in punkty.items():
            dane = pobierz_json(
                klient,
                API_PROGNOZ,
                params={"latitude": lat, "longitude": lon, "forecast_days": 3,
                        "hourly": ",".join(ZMIENNE), "timezone": "UTC"},
                czekaj=czekaj,
            )
            ramki.append(_do_ramki(dane, nazwa))
        return pd.concat(ramki, ignore_index=True)
    finally:
        if wlasny_klient:
            klient.close()
