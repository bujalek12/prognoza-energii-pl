"""Testy monitoringu jakosci prognoz na zywo."""

from datetime import date, timedelta

import numpy as np
import pandas as pd

from energia.model.monitoring import alarmy, ocen_ostatnie_dni

DZIS = date(2026, 10, 21)
BACKTEST = {"zapotrzebowanie": 0.03, "wiatr": 0.16, "pv": 0.10}


def ocena(cel: str, doby: int, blad: float, pokrycie: float = 0.8, faktyczne: float = 1000.0) -> pd.DataFrame:
    """Sztuczna fct_ocena_prognoz: `doby` pelnych dob przed DZIS, staly wzgledny blad modelu."""
    wiersze = []
    for d in range(1, doby + 1):
        doba = DZIS - timedelta(days=d)
        for h in range(24):
            w_przedziale = h < round(24 * pokrycie)
            wiersze.append({"doba": doba, "cel": cel, "faktyczne": faktyczne, "p50": faktyczne * (1 + blad),
                            "plan_pse": faktyczne * 1.05, "w_przedziale_80": w_przedziale})
    return pd.DataFrame(wiersze)


def test_ocena_liczy_nmae_modelu_i_pse_z_ostatnich_7_dni():
    dane = pd.concat([ocena("wiatr", doby=10, blad=0.2)])

    wynik = ocen_ostatnie_dni(dane, dzis=DZIS, dni=7)

    assert wynik["wiatr"]["dob"] == 7
    assert abs(wynik["wiatr"]["nmae_model"] - 0.2) < 1e-9
    assert abs(wynik["wiatr"]["nmae_pse"] - 0.05) < 1e-9


def test_brak_alarmu_gdy_model_dziala_jak_w_backtescie():
    dane = pd.concat([ocena("wiatr", 7, 0.17), ocena("pv", 7, 0.11), ocena("zapotrzebowanie", 7, 0.03)])

    assert alarmy(ocen_ostatnie_dni(dane, DZIS), BACKTEST, prognoza_na_jutro=True) == []


def test_alarm_gdy_blad_ponad_dwa_razy_wiekszy_niz_w_backtescie():
    dane = pd.concat([ocena("wiatr", 7, 0.40), ocena("pv", 7, 0.11), ocena("zapotrzebowanie", 7, 0.03)])

    wynik = alarmy(ocen_ostatnie_dni(dane, DZIS), BACKTEST, prognoza_na_jutro=True)

    assert len(wynik) == 1 and "wiatr" in wynik[0]


def test_alarm_gdy_przedzial_80_obejmuje_za_malo_godzin():
    dane = ocena("pv", 7, 0.10, pokrycie=0.5)

    wynik = alarmy(ocen_ostatnie_dni(dane, DZIS), BACKTEST, prognoza_na_jutro=True)

    assert any("fotowoltaika" in a and "przedział" in a for a in wynik)


def test_alarm_gdy_brak_prognozy_na_jutro():
    dane = ocena("wiatr", 7, 0.16)

    wynik = alarmy(ocen_ostatnie_dni(dane, DZIS), BACKTEST, prognoza_na_jutro=False)

    assert any("jutro" in a for a in wynik)


def test_za_malo_dob_nie_daje_alarmu_o_bledzie():
    # 2 doby to za malo, zeby wyrokowac o jakosci (wiatr potrafi miec jeden bardzo zly dzien)
    dane = ocena("wiatr", 2, 0.60)

    assert alarmy(ocen_ostatnie_dni(dane, DZIS), BACKTEST, prognoza_na_jutro=True) == []


def test_porownanie_z_pse_tylko_na_godzinach_gdzie_jest_plan():
    # 7 dob prognoz modelu, ale plan PSE tylko z 2 dob: porownanie musi uzyc tych samych 2 dob,
    # inaczej zestawiamy bledy z roznych okresow (tak bylo w aplikacji do 21.10)
    dane = ocena("wiatr", 7, 0.20)
    dane.loc[dane["doba"] < DZIS - timedelta(days=2), "plan_pse"] = None
    dane.loc[dane["doba"] >= DZIS - timedelta(days=2), "p50"] = 1000.0 * 1.10  # w tych 2 dobach model lepszy

    wynik = ocen_ostatnie_dni(dane, DZIS)["wiatr"]

    assert wynik["dob_z_planem"] == 2
    assert abs(wynik["nmae_model_wspolne"] - 0.10) < 1e-9
    assert abs(wynik["nmae_pse"] - 0.05) < 1e-9
