"""Testy podzialu na okna backtestu i metryk."""

import numpy as np
import pandas as pd
import pytest

from energia.model.backtest import metryki, podzialy_miesieczne


def indeks(od: str, do: str) -> pd.DatetimeIndex:
    return pd.date_range(od, do, freq="1h", tz="UTC", name="godzina_utc")


def test_kazde_okno_uczy_sie_tylko_na_przeszlosci():
    idx = indeks("2025-01-01", "2025-12-31 23:00")

    for miesiac, uczenie, test in podzialy_miesieczne(idx, ostatnie=3):
        assert idx[uczenie].max() < idx[test].min()


def test_okna_to_ostatnie_pelne_miesiace_po_kolei():
    idx = indeks("2025-01-01", "2025-12-31 23:00")

    miesiace = [m for m, _, _ in podzialy_miesieczne(idx, ostatnie=3)]

    assert miesiace == [pd.Period("2025-10"), pd.Period("2025-11"), pd.Period("2025-12")]


def test_okno_testowe_obejmuje_caly_miesiac_i_tylko_jego():
    idx = indeks("2025-01-01", "2025-12-31 23:00")

    _, _, test = next(iter(podzialy_miesieczne(idx, ostatnie=1)))

    assert idx[test].min() == pd.Timestamp("2025-12-01", tz="UTC")
    assert idx[test].max() == pd.Timestamp("2025-12-31 23:00", tz="UTC")


def test_niepelny_biezacy_miesiac_tez_jest_testowany():
    # dane koncza sie 12 pazdziernika: pazdziernik to ostatnie okno, mimo ze niepelne
    idx = indeks("2025-01-01", "2025-10-12 18:00")

    miesiace = [m for m, _, _ in podzialy_miesieczne(idx, ostatnie=2)]

    assert miesiace == [pd.Period("2025-09"), pd.Period("2025-10")]


def test_metryki_na_recznie_policzonym_przykladzie():
    y = np.array([100.0, 200.0, 300.0, 400.0])
    p = np.array([110.0, 190.0, 330.0, 400.0])

    m = metryki(y, p)

    assert m["mae"] == pytest.approx(12.5)  # (10 + 10 + 30 + 0) / 4
    assert m["nmae"] == pytest.approx(12.5 / 250)  # MAE / srednia faktyczna
    assert m["obciazenie"] == pytest.approx(7.5)  # srednia (p - y): prognoza zawyzona


def test_kalibracja_poszerza_za_waski_przedzial_do_zadanego_pokrycia():
    from energia.model.backtest import kalibracja_przedzialu, poszerz

    rng = np.random.default_rng(1)
    y = rng.normal(100, 10, size=5000)
    p10, p90 = np.full(5000, 95.0), np.full(5000, 105.0)  # za waski: obejmuje ok. 38%

    k = kalibracja_przedzialu(y, p10, p90, poziom=0.8)
    nowe10, nowe90 = poszerz(p10, p90, k)

    pokrycie = np.mean((y >= nowe10) & (y <= nowe90))
    assert 0.79 <= pokrycie <= 0.82


def test_kalibracja_nie_poszerza_przedzialu_o_zerowej_szerokosci():
    # PV w nocy: p10 = p90 = 0 i tak ma zostac (poszerzenie proporcjonalne do szerokosci)
    from energia.model.backtest import poszerz

    nowe10, nowe90 = poszerz(np.array([0.0, 90.0]), np.array([0.0, 110.0]), k=0.5)

    assert nowe10.tolist() == [0.0, 80.0]
    assert nowe90.tolist() == [0.0, 120.0]
