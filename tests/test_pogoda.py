"""Testy klienta historycznych prognoz pogody z Open-Meteo."""

from datetime import date

import httpx
import pandas as pd

from energia.pogoda import PUNKTY, pobierz_pogode, pobierz_prognoze_pogody


def odpowiedz_open_meteo(czasy: list[str], wiatr: list[float]) -> dict:
    n = len(czasy)
    return {
        "hourly": {
            "time": czasy,
            "temperature_2m": [10.0] * n,
            "wind_speed_100m": wiatr,
            "shortwave_radiation": [0.0] * n,
            "cloud_cover": [50] * n,
        }
    }


def test_pobiera_kazdy_punkt_i_laczy_w_jedna_ramke():
    zapytania = []

    def obsluga(zadanie: httpx.Request) -> httpx.Response:
        zapytania.append((zadanie.url.params["latitude"], zadanie.url.params["longitude"]))
        return httpx.Response(200, json=odpowiedz_open_meteo(["2026-03-01T00:00", "2026-03-01T01:00"], [20.0, 25.0]))

    punkty = {"Pomorze": (54.5, 17.0), "Warszawa": (52.23, 21.01)}
    df = pobierz_pogode(
        date(2026, 3, 1), date(2026, 3, 1), punkty=punkty, klient=httpx.Client(transport=httpx.MockTransport(obsluga))
    )

    assert zapytania == [("54.5", "17.0"), ("52.23", "21.01")]
    assert len(df) == 4
    assert sorted(df["punkt"].unique()) == ["Pomorze", "Warszawa"]


def test_czas_jest_w_utc_a_kolumny_maja_polskie_nazwy():
    def obsluga(zadanie: httpx.Request) -> httpx.Response:
        assert zadanie.url.params["timezone"] == "UTC"
        return httpx.Response(200, json=odpowiedz_open_meteo(["2026-03-01T13:00"], [31.5]))

    df = pobierz_pogode(
        date(2026, 3, 1), date(2026, 3, 1), punkty={"Pomorze": (54.5, 17.0)},
        klient=httpx.Client(transport=httpx.MockTransport(obsluga)),
    )

    assert df.to_dict("records") == [
        {
            "ts_utc": pd.Timestamp("2026-03-01 13:00", tz="UTC"),
            "punkt": "Pomorze",
            "temperatura": 10.0,
            "wiatr_100m": 31.5,
            "promieniowanie": 0.0,
            "zachmurzenie": 50,
        }
    ]


def test_domyslne_punkty_pokrywaja_rejony_wiatru_slonca_i_popytu():
    # Zmiana listy punktow zmienia cechy modelu: test pilnuje, zeby nie zniknal zaden rejon
    assert {"Pomorze", "Wielkopolska", "Warszawa", "Slask", "Lubelskie"} <= set(PUNKTY)


def test_dlugi_zakres_dzieli_na_kawalki_po_najwyzej_90_dniach():
    zakresy = []

    def obsluga(zadanie: httpx.Request) -> httpx.Response:
        zakresy.append((zadanie.url.params["start_date"], zadanie.url.params["end_date"]))
        return httpx.Response(200, json=odpowiedz_open_meteo(["2026-03-01T00:00"], [20.0]))

    pobierz_pogode(
        date(2026, 1, 1), date(2026, 5, 15), punkty={"Pomorze": (54.5, 17.0)},
        klient=httpx.Client(transport=httpx.MockTransport(obsluga)),
    )

    assert zakresy == [("2026-01-01", "2026-03-31"), ("2026-04-01", "2026-05-15")]


def test_prognoza_pogody_pyta_api_prognoz_o_kolejne_dni():
    zapytania = []

    def obsluga(zadanie: httpx.Request) -> httpx.Response:
        zapytania.append((zadanie.url.host, zadanie.url.params["forecast_days"], zadanie.url.params["timezone"]))
        return httpx.Response(200, json=odpowiedz_open_meteo(["2026-10-13T12:00"], [30.0]))

    df = pobierz_prognoze_pogody(punkty={"Pomorze": (54.5, 17.0)}, klient=httpx.Client(transport=httpx.MockTransport(obsluga)))

    assert zapytania == [("api.open-meteo.com", "3", "UTC")]
    assert df.iloc[0]["wiatr_100m"] == 30.0
    assert df.iloc[0]["ts_utc"] == pd.Timestamp("2026-10-13 12:00", tz="UTC")
