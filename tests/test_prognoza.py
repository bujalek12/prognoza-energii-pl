"""Testy skladania cech i prognozy na jutro."""

import numpy as np
import pandas as pd

from energia.model.prognoza import posortuj_kwantyle, ramka_prognozy


def test_cechy_na_jutro_biora_opoznienia_z_historii():
    historia_idx = pd.date_range("2026-10-01", "2026-10-12 23:00", freq="1h", tz="UTC", name="godzina_utc")
    historia = pd.DataFrame({"pv_mw": np.arange(len(historia_idx), dtype=float),
                             "wiatr_mw": 1.0, "zapotrzebowanie_mw": 2.0}, index=historia_idx)
    jutro_idx = pd.date_range("2026-10-13", periods=24, freq="1h", tz="UTC", name="godzina_utc")
    przyszle = pd.DataFrame({"godzina": range(24)}, index=jutro_idx)

    ramka = ramka_prognozy(historia, przyszle)

    assert list(ramka.index) == list(jutro_idx)
    t = pd.Timestamp("2026-10-13 12:00", tz="UTC")
    assert ramka.loc[t, "pv_mw_lag48"] == historia.loc[t - pd.Timedelta(hours=48), "pv_mw"]
    assert ramka.loc[t, "pv_mw_lag168"] == historia.loc[t - pd.Timedelta(hours=168), "pv_mw"]
    assert ramka.loc[t, "godzina"] == 12


def test_kwantyle_nie_moga_sie_krzyzowac():
    # Osobne modele kwantylowe potrafia dac p10 > p50; sortujemy, zeby przedzial mial sens
    df = pd.DataFrame({"p10": [120.0, 10.0], "p50": [100.0, 20.0], "p90": [110.0, 30.0]})

    wynik = posortuj_kwantyle(df)

    assert wynik[["p10", "p50", "p90"]].values.tolist() == [[100.0, 110.0, 120.0], [10.0, 20.0, 30.0]]


def test_prognoza_na_dobe_czesciowo_zmierzona_nie_dubluje_godzin():
    # ponowna prognoza na dzis: czesc godzin jest juz w historii; pomiary maja pierwszenstwo
    historia_idx = pd.date_range("2026-10-01", "2026-10-13 09:00", freq="1h", tz="UTC", name="godzina_utc")
    historia = pd.DataFrame({"pv_mw": 1.0, "wiatr_mw": 1.0, "zapotrzebowanie_mw": 2.0}, index=historia_idx)
    dzis_idx = pd.date_range("2026-10-13", periods=24, freq="1h", tz="UTC", name="godzina_utc")
    przyszle = pd.DataFrame({"godzina": range(24)}, index=dzis_idx)

    ramka = ramka_prognozy(historia, przyszle)

    assert list(ramka.index) == list(dzis_idx)
    assert ramka.loc[pd.Timestamp("2026-10-13 05:00", tz="UTC"), "godzina"] == 5
