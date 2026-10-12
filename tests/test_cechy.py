"""Testy cech modelu. Najwazniejsze: zadna cecha nie moze korzystac z danych,
ktorych w momencie prognozy (D-1, 10:00) jeszcze nie znamy."""

import numpy as np
import pandas as pd
import pytest

from energia.model.cechy import dodaj_opoznienia, wysokosc_slonca


def godziny(n: int, start: str = "2026-03-01 00:00") -> pd.DataFrame:
    idx = pd.date_range(start, periods=n, freq="1h", tz="UTC", name="godzina_utc")
    return pd.DataFrame({"pv_mw": np.arange(n, dtype=float)}, index=idx)


def test_opoznienie_48h_to_wartosc_sprzed_dokladnie_48_godzin():
    df = dodaj_opoznienia(godziny(24 * 10), "pv_mw")

    t = pd.Timestamp("2026-03-09 13:00", tz="UTC")  # 168 h wstecz musi miescic sie w danych
    assert df.loc[t, "pv_mw_lag48"] == df.loc[t - pd.Timedelta(hours=48), "pv_mw"]
    assert df.loc[t, "pv_mw_lag168"] == df.loc[t - pd.Timedelta(hours=168), "pv_mw"]


def test_opoznienie_liczone_po_czasie_a_nie_po_numerze_wiersza():
    # Gdy w danych brakuje godziny, przesuniecie o 48 wierszy wzieloby zla godzine
    df = godziny(24 * 5).drop(pd.Timestamp("2026-03-02 05:00", tz="UTC"))

    wynik = dodaj_opoznienia(df, "pv_mw")

    t = pd.Timestamp("2026-03-04 12:00", tz="UTC")
    assert wynik.loc[t, "pv_mw_lag48"] == df.loc[t - pd.Timedelta(hours=48), "pv_mw"]
    assert np.isnan(wynik.loc[pd.Timestamp("2026-03-04 05:00", tz="UTC"), "pv_mw_lag48"])


def test_srednia_z_doby_D_minus_2_nie_siega_poza_te_dobe():
    df = dodaj_opoznienia(godziny(24 * 10), "pv_mw")

    # cel: 2026-03-05 (UTC), doba D-2 to 2026-03-03 00:00..23:00 -> srednia z wartosci 48..71
    t = pd.Timestamp("2026-03-05 20:00", tz="UTC")
    assert df.loc[t, "pv_mw_srednia_d2"] == pytest.approx(np.mean(np.arange(48, 72)))


def test_maksimum_30_dni_konczy_sie_na_dobie_D_minus_2():
    df = dodaj_opoznienia(godziny(24 * 40), "pv_mw")

    t = pd.Timestamp("2026-04-05 10:00", tz="UTC")
    koniec_d2 = pd.Timestamp("2026-04-03 23:00", tz="UTC")
    assert df.loc[t, "pv_mw_max30"] == df.loc[koniec_d2 - pd.Timedelta(days=30) + pd.Timedelta(hours=1): koniec_d2, "pv_mw"].max()


def test_wysokosc_slonca_w_polsce():
    # Warszawa: 21 czerwca w poludnie slonce ~61 stopni, w nocy pod horyzontem, w grudniu nisko
    lato = wysokosc_slonca(pd.DatetimeIndex([pd.Timestamp("2026-06-21 10:45", tz="UTC")]))[0]
    noc = wysokosc_slonca(pd.DatetimeIndex([pd.Timestamp("2026-06-21 23:00", tz="UTC")]))[0]
    zima = wysokosc_slonca(pd.DatetimeIndex([pd.Timestamp("2026-12-21 10:45", tz="UTC")]))[0]

    assert 58 < lato < 64
    assert noc < 0
    assert 12 < zima < 17
