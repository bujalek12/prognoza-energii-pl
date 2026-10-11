"""Test calego przebiegu: PSE + Open-Meteo -> DuckDB, z podmienionymi serwerami."""

from datetime import date

import httpx
import pytest

from energia import magazyn
from energia.pipeline import aktualizuj

DZIS = date(2026, 10, 11)


class FalszywePSE:
    """Udaje API PSE: zapamietuje filtry zapytan i zwraca po jednym wierszu na raport."""

    def __init__(self):
        self.filtry: dict[str, list[str]] = {}

    def __call__(self, zadanie: httpx.Request) -> httpx.Response:
        raport = zadanie.url.path.rsplit("/", 1)[-1]
        self.filtry.setdefault(raport, []).append(zadanie.url.params["$filter"])
        if raport == "his-wlk-cal":
            wiersz = {"dtime_utc": "2026-10-11 08:00:00", "business_date": "2026-10-11", "demand": 18000.0,
                      "wi": 3000.0, "pv": 5000.0, "publication_ts_utc": "2026-10-11 08:05:00"}
        else:
            wiersz = {"dtime_utc": "2026-10-12 08:00:00", "business_date": "2026-10-12", "kse_pow_dem": 17500.0,
                      "gen_wi": 2500.0, "gen_fv": 4000.0, "publication_ts_utc": "2026-10-11 12:00:00"}
        return httpx.Response(200, json={"value": [wiersz]})


def falszywa_pogoda(zadanie: httpx.Request) -> httpx.Response:
    # Jak prawdziwe API: zwraca dane z zapytanego zakresu (tu jedna godzina, ostatniego dnia)
    koniec = zadanie.url.params["end_date"]
    godzina = [f"{koniec}T08:00"] if koniec == "2026-10-11" else []
    return httpx.Response(200, json={"hourly": {
        "time": godzina, "temperature_2m": [12.0] * len(godzina), "wind_speed_100m": [25.0] * len(godzina),
        "shortwave_radiation": [300.0] * len(godzina), "cloud_cover": [40] * len(godzina),
    }})


@pytest.fixture
def baza():
    con = magazyn.polacz(":memory:")
    yield con
    con.close()


def uruchom(baza, pse: FalszywePSE):
    return aktualizuj(
        baza,
        dzis=DZIS,
        klient_pse=httpx.Client(transport=httpx.MockTransport(pse), base_url="https://pse.test/api"),
        klient_pogoda=httpx.Client(transport=httpx.MockTransport(falszywa_pogoda)),
        czekaj=lambda s: None,
    )


def test_pierwsze_uruchomienie_pobiera_cala_historie(baza):
    pse = FalszywePSE()

    uruchom(baza, pse)

    assert pse.filtry["his-wlk-cal"] == ["business_date ge '2024-06-14' and business_date le '2026-10-11'"]


def test_plan_pse_pobierany_jest_tez_na_jutro(baza):
    # Plan na jutro publikowany jest dzis: to wersja, ktora posluzy jako uczciwy benchmark
    pse = FalszywePSE()

    uruchom(baza, pse)

    assert pse.filtry["pdgobpkd"][0].endswith("business_date le '2026-10-12'")


def test_kolejne_uruchomienie_pobiera_tylko_okno_korekt(baza):
    uruchom(baza, FalszywePSE())
    pse = FalszywePSE()

    uruchom(baza, pse)

    # ostatnia doba w bazie to 2026-10-11, okno korekt 3 dni -> od 2026-10-08
    assert pse.filtry["his-wlk-cal"] == ["business_date ge '2026-10-08' and business_date le '2026-10-11'"]


def test_dwukrotne_uruchomienie_nie_dubluje_danych(baza):
    uruchom(baza, FalszywePSE())
    uruchom(baza, FalszywePSE())

    liczby = {t: baza.sql(f"select count(*) from {t}").fetchone()[0] for t in ["wykonanie", "plan_pse", "pogoda"]}
    assert liczby == {"wykonanie": 1, "plan_pse": 1, "pogoda": 5}  # pogoda: 5 punktow x 1 godzina


def test_zwraca_podsumowanie_i_zapisuje_je_w_logu(baza):
    podsumowanie = uruchom(baza, FalszywePSE())

    assert podsumowanie == {"wykonanie": 1, "plan_pse": 1, "pogoda": 5}
    assert baza.sql("select count(*) from uruchomienia").fetchone()[0] == 3


def test_awaria_jednego_zrodla_nie_blokuje_pozostalych(baza):
    # PSE plan lezy (503), ale pogoda i wykonanie maja sie zapisac, a blad ma byc widoczny
    def pse_bez_planu(zadanie: httpx.Request) -> httpx.Response:
        if zadanie.url.path.endswith("pdgobpkd"):
            return httpx.Response(503)
        return FalszywePSE()(zadanie)

    with pytest.raises(RuntimeError, match="plan_pse"):
        aktualizuj(
            baza,
            dzis=DZIS,
            klient_pse=httpx.Client(transport=httpx.MockTransport(pse_bez_planu), base_url="https://pse.test/api"),
            klient_pogoda=httpx.Client(transport=httpx.MockTransport(falszywa_pogoda)),
            czekaj=lambda s: None,
        )

    assert baza.sql("select count(*) from pogoda").fetchone()[0] == 5
    assert baza.sql("select zrodlo, wierszy from uruchomienia order by zrodlo").fetchall() == [
        ("plan_pse", -1), ("pogoda", 5), ("wykonanie", 1)
    ]
