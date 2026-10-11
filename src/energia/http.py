"""Wspolne pobieranie JSON-a z ponawianiem: uzywaja go klienci PSE i Open-Meteo."""

import time
from collections.abc import Callable

import httpx

PROBY = 4


class BladPobierania(Exception):
    """API nie zwrocilo danych mimo ponowien albo odrzucilo zapytanie."""


def pobierz_json(
    klient: httpx.Client,
    url: str,
    params: dict | None = None,
    czekaj: Callable[[float], None] = time.sleep,
) -> dict:
    """GET z ponawianiem bledow sieci i serwera: 4 proby, przerwy 1 s, 2 s, 4 s."""
    for proba in range(PROBY):
        try:
            odp = klient.get(url, params=params)
        except httpx.TransportError as e:
            blad = f"blad polaczenia: {e}"
        else:
            if odp.is_success:
                return odp.json()
            # 4xx to blad zapytania (zla nazwa raportu, zly filtr): ponawianie nic nie zmieni.
            # Wyjatek: 429 "za duzo zapytan" mija, jesli chwile odczekac.
            if odp.is_client_error and odp.status_code != 429:
                raise BladPobierania(f"{url}: HTTP {odp.status_code}")
            blad = f"HTTP {odp.status_code}"
        if proba < PROBY - 1:
            czekaj(2**proba)
    raise BladPobierania(f"{url}: {blad} (po {PROBY} probach)")
