"""Testy pomocniczych funkcji treningu."""

import lightgbm as lgb
import numpy as np
import pandas as pd

from energia.model.trening import waznosc_cech


def test_waznosc_cech_wskazuje_ceche_od_ktorej_zalezy_wynik():
    # y zalezy tylko od x1; x2 to szum. SHAP musi wskazac x1 jako najwazniejsza.
    rng = np.random.default_rng(0)
    X = pd.DataFrame({"x1": rng.normal(size=2000), "x2": rng.normal(size=2000)})
    y = 3 * X["x1"] + rng.normal(scale=0.01, size=2000)
    model = lgb.LGBMRegressor(n_estimators=50, verbose=-1).fit(X, y)

    wynik = waznosc_cech(model, X)

    assert list(wynik.index) == ["x1", "x2"]  # posortowane malejaco
    assert wynik["x1"] > 10 * wynik["x2"]


def test_skrot_metryk_pomija_sekcje_bez_nmae():
    from energia.model.trening import skrot_metryk

    podsumowanie = {"pv_mw": {"model": {"nmae": 0.11789}, "naiwna": {"nmae": 0.2675}, "plan_pse_ostatni": {"nmae": 0.06},
                              "kalibracja": {"k": 0.137}, "pokrycie_80": 0.7, "godzin": 100}}

    assert skrot_metryk(podsumowanie) == {"pv_mw": {"model": 0.1179, "naiwna": 0.2675, "plan_pse_ostatni": 0.06}}
