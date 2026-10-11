"""Testy klienta API PSE.

Serwer PSE podmieniamy przez httpx.MockTransport: klient HTTP dziala naprawde,
tylko odpowiedzi przychodza z funkcji w tescie zamiast z internetu.
"""

from datetime import date

import httpx
import pandas as pd
import pytest

from energia.pse import BladPobierania, plan_do_ramki, pobierz_raport, wykonanie_do_ramki


def klient_z(obsluga) -> httpx.Client:
    return httpx.Client(transport=httpx.MockTransport(obsluga), base_url="https://pse.test/api")


def wiersz(dtime_utc: str, business_date: str, demand=15000.0, wi=2000.0, pv=0.0) -> dict:
    return {
        "dtime_utc": dtime_utc,
        "business_date": business_date,
        "demand": demand,
        "wi": wi,
        "pv": pv,
        "publication_ts_utc": "2025-10-26 23:50:00.000",
    }


# --- Stronicowanie -------------------------------------------------------------------


def test_zbiera_wiersze_ze_wszystkich_stron_idac_za_nextlink():
    strony = {
        "/api/his-wlk-cal": {"value": [{"n": 1}, {"n": 2}], "nextLink": "https://pse.test/api/his-wlk-cal?strona=2"},
        "/api/his-wlk-cal?strona=2": {"value": [{"n": 3}]},
    }

    def obsluga(zadanie: httpx.Request) -> httpx.Response:
        klucz = zadanie.url.path + (f"?{zadanie.url.query.decode()}" if b"strona" in zadanie.url.query else "")
        return httpx.Response(200, json=strony[klucz])

    wiersze = pobierz_raport("his-wlk-cal", date(2025, 10, 1), date(2025, 10, 2), klient=klient_z(obsluga))

    assert [w["n"] for w in wiersze] == [1, 2, 3]


def test_filtruje_po_dobie_handlowej_w_skladni_odata():
    zapytania = []

    def obsluga(zadanie: httpx.Request) -> httpx.Response:
        zapytania.append(zadanie.url.params["$filter"])
        return httpx.Response(200, json={"value": []})

    pobierz_raport("his-wlk-cal", date(2025, 10, 1), date(2025, 10, 2), klient=klient_z(obsluga))

    assert zapytania == ["business_date ge '2025-10-01' and business_date le '2025-10-02'"]


# --- Ponawianie ------------------------------------------------------------------------


def test_ponawia_po_bledzie_serwera_i_zwraca_dane():
    proby = []

    def obsluga(zadanie: httpx.Request) -> httpx.Response:
        proby.append(1)
        if len(proby) < 3:
            return httpx.Response(503)
        return httpx.Response(200, json={"value": [{"n": 1}]})

    wiersze = pobierz_raport(
        "his-wlk-cal", date(2025, 10, 1), date(2025, 10, 1), klient=klient_z(obsluga), czekaj=lambda s: None
    )

    assert wiersze == [{"n": 1}]
    assert len(proby) == 3


def test_ponawia_po_zerwanym_polaczeniu():
    proby = []

    def obsluga(zadanie: httpx.Request) -> httpx.Response:
        proby.append(1)
        if len(proby) == 1:
            raise httpx.ConnectError("polaczenie zerwane", request=zadanie)
        return httpx.Response(200, json={"value": []})

    pobierz_raport("his-wlk-cal", date(2025, 10, 1), date(2025, 10, 1), klient=klient_z(obsluga), czekaj=lambda s: None)

    assert len(proby) == 2


def test_poddaje_sie_po_czterech_probach_z_rosnacym_odstepem():
    proby, przerwy = [], []

    def obsluga(zadanie: httpx.Request) -> httpx.Response:
        proby.append(1)
        return httpx.Response(503)

    with pytest.raises(BladPobierania):
        pobierz_raport(
            "his-wlk-cal", date(2025, 10, 1), date(2025, 10, 1), klient=klient_z(obsluga), czekaj=przerwy.append
        )

    assert len(proby) == 4
    assert przerwy == [1, 2, 4]


def test_nie_ponawia_bledu_klienta():
    # 404 oznacza zla nazwe raportu: ponawianie nic nie da, trzeba od razu przerwac
    proby = []

    def obsluga(zadanie: httpx.Request) -> httpx.Response:
        proby.append(1)
        return httpx.Response(404)

    with pytest.raises(BladPobierania):
        pobierz_raport("nie-ma-takiego", date(2025, 10, 1), date(2025, 10, 1), klient=klient_z(obsluga), czekaj=lambda s: None)

    assert len(proby) == 1


# --- Zamiana na ramke ------------------------------------------------------------------


def test_klucz_czasu_w_utc_przezywa_powtorzona_godzine_przy_zmianie_czasu():
    # 26.10.2025: godzina 2:00-3:00 czasu polskiego wystepuje dwa razy.
    # W czasie lokalnym PSE zapisuje ja jako "02a:15", w UTC to po prostu kolejne kwadranse.
    wiersze = [
        wiersz("2025-10-26 00:45:00", "2025-10-26"),  # 02:45 CEST
        wiersz("2025-10-26 01:00:00", "2025-10-26"),  # 03:00 CEST = koniec pierwszej 2:xx
        wiersz("2025-10-26 01:15:00", "2025-10-26"),  # "02a:15" CET
    ]

    df = wykonanie_do_ramki(wiersze)

    assert list(df.index) == [
        pd.Timestamp("2025-10-26 00:45", tz="UTC"),
        pd.Timestamp("2025-10-26 01:00", tz="UTC"),
        pd.Timestamp("2025-10-26 01:15", tz="UTC"),
    ]
    assert df.index.name == "ts_utc"


def test_pomija_kwadranse_bez_pomiaru():
    # API zwraca tez przyszle kwadranse biezacej doby z pustymi wartosciami
    wiersze = [
        wiersz("2025-10-26 10:00:00", "2025-10-26"),
        wiersz("2025-10-26 10:15:00", "2025-10-26", demand=None),
        wiersz("2025-10-26 10:30:00", "2025-10-26", pv=None),
    ]

    df = wykonanie_do_ramki(wiersze)

    assert list(df.index) == [pd.Timestamp("2025-10-26 10:00", tz="UTC")]


def test_zwraca_kolumny_z_czytelnymi_nazwami_i_doba_handlowa():
    df = wykonanie_do_ramki([wiersz("2025-10-26 10:00:00", "2025-10-26", demand=18000.5, wi=3000.0, pv=4500.25)])

    assert df.iloc[0].to_dict() == {
        "doba": date(2025, 10, 26),
        "zapotrzebowanie": 18000.5,
        "wiatr": 3000.0,
        "pv": 4500.25,
        "publikacja_utc": pd.Timestamp("2025-10-26 23:50", tz="UTC"),
    }


def test_odrzuca_zduplikowany_kwadrans():
    # Dwa wiersze z tym samym czasem UTC to blad danych, a nie cos do cichego scalenia
    wiersze = [wiersz("2025-10-26 10:00:00", "2025-10-26"), wiersz("2025-10-26 10:00:00", "2025-10-26")]

    with pytest.raises(ValueError, match="duplikat"):
        wykonanie_do_ramki(wiersze)


# --- Plan PSE (pdgobpkd) ------------------------------------------------------------------


def wiersz_planu(dtime_utc: str, publikacja: str, kse=17000.0, wi=1200.0, fv=900.0) -> dict:
    return {
        "dtime_utc": dtime_utc,
        "business_date": "2025-09-10",
        "kse_pow_dem": kse,
        "gen_wi": wi,
        "gen_fv": fv,
        "publication_ts_utc": publikacja,
    }


def test_plan_ma_klucz_kwadrans_i_moment_publikacji():
    df = plan_do_ramki([wiersz_planu("2025-09-10 08:15:00", "2025-09-11 01:31:50.716", kse=18550.0, wi=1277.0, fv=9283.0)])

    assert df.to_dict("records") == [
        {
            "ts_utc": pd.Timestamp("2025-09-10 08:15", tz="UTC"),
            "publikacja_utc": pd.Timestamp("2025-09-11 01:31:50.716", tz="UTC"),
            "doba": date(2025, 9, 10),
            "zapotrzebowanie_plan": 18550.0,
            "wiatr_plan": 1277.0,
            "pv_plan": 9283.0,
        }
    ]


def test_plan_pomija_wiersze_bez_prognozy_zapotrzebowania():
    df = plan_do_ramki(
        [
            wiersz_planu("2025-09-10 08:15:00", "2025-09-11 01:31:50"),
            wiersz_planu("2025-09-10 08:30:00", "2025-09-11 01:31:50", kse=None),
        ]
    )

    assert df["ts_utc"].tolist() == [pd.Timestamp("2025-09-10 08:15", tz="UTC")]
