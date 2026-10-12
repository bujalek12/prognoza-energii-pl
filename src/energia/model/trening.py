"""Trening i backtest modeli LightGBM: zapotrzebowanie, wiatr i PV na dobe naprzod.

Uruchomienie: uv run python -m energia.model.trening
Wyniki: data/model/backtest.parquet (prognozy z backtestu), data/model/metryki.json,
        data/model/<cel>_<kwantyl>.txt (modele uczone na calej historii, do prognoz na jutro).
"""

import json
import logging
from dataclasses import dataclass

import duckdb
import lightgbm as lgb
import numpy as np
import pandas as pd

from energia.model.backtest import kalibracja_przedzialu, metryki, podzialy_miesieczne, poszerz
from energia.model.cechy import dodaj_opoznienia, wysokosc_slonca
from energia.pipeline import BAZA, PROJEKT

KATALOG = PROJEKT / "data" / "model"
KWANTYLE = (0.1, 0.5, 0.9)  # mediana + przedzial 80%

KALENDARZ = ["godzina", "dzien_tygodnia", "miesiac", "dzien_roku", "czy_swieto", "czy_dzien_roboczy", "wysokosc_slonca"]
POGODA = [
    "temperatura_c", "wiatr_100m_sredni_kmh", "promieniowanie_srednie_wm2", "zachmurzenie_srednie_proc",
    "wiatr_pomorze_kmh", "wiatr_wielkopolska_kmh", "wiatr_lubelskie_kmh",
    "promieniowanie_lubelskie_wm2", "promieniowanie_slask_wm2", "promieniowanie_wielkopolska_wm2",
]
PARAMETRY = dict(
    n_estimators=600, learning_rate=0.03, num_leaves=63, min_child_samples=30,
    subsample=0.8, subsample_freq=1, colsample_bytree=0.8, verbose=-1,
)

log = logging.getLogger("energia.model")


@dataclass(frozen=True)
class Cel:
    nazwa: str           # kolumna w fct_energia_godzinowa
    wzgledny: bool       # True: model uczy sie ulamka maksimum z 30 dni (pv, wiatr), nie MW
    plan_pse: str        # kolumna planu PSE do porownania
    naiwna: str          # prognoza naiwna (baseline) do porownania

    @property
    def cechy(self) -> list[str]:
        return KALENDARZ + POGODA + [f"{self.nazwa}_{s}" for s in ("lag48", "lag168", "srednia_d2", "max30")]


CELE = {
    # zapotrzebowanie: naiwnie "jak tydzien temu o tej godzinie" (tydzien, bo dzien tygodnia ma znaczenie)
    "zapotrzebowanie": Cel("zapotrzebowanie_mw", False, "plan_zapotrzebowanie_ostatni_mw", "zapotrzebowanie_mw_lag168"),
    # wiatr i PV: naiwnie "jak przedwczoraj o tej godzinie" (najswiezsza znana wartosc)
    "wiatr": Cel("wiatr_mw", True, "plan_wiatr_ostatni_mw", "wiatr_mw_lag48"),
    "pv": Cel("pv_mw", True, "plan_pv_ostatni_mw", "pv_mw_lag48"),
}


def przygotuj_dane(con: duckdb.DuckDBPyConnection) -> pd.DataFrame:
    """fct_energia_godzinowa + cechy kalendarza, slonca i opoznien dla wszystkich celow."""
    df = con.sql("select * from marts.fct_energia_godzinowa order by godzina_utc").df()
    df["godzina_utc"] = pd.to_datetime(df["godzina_utc"], utc=True)
    df = dodaj_cechy_czasu(df.set_index("godzina_utc"))
    for cel in CELE.values():
        df = dodaj_opoznienia(df, cel.nazwa)
    return df


def dodaj_cechy_czasu(df: pd.DataFrame) -> pd.DataFrame:
    """Cechy kalendarza i slonca. Wspolne dla treningu i prognozy: obie sciezki MUSZA liczyc
    cechy tak samo, inaczej model w produkcji dostaje co innego niz w treningu."""
    df = df.copy()
    df["dzien_roku"] = pd.to_datetime(df["data"]).dt.dayofyear
    df["wysokosc_slonca"] = wysokosc_slonca(df.index)
    for kolumna in ("czy_swieto", "czy_dzien_roboczy"):
        df[kolumna] = df[kolumna].astype(int)
    return df


def _skala(df: pd.DataFrame, cel: Cel) -> np.ndarray:
    """Mnoznik celu: maksimum z 30 dni (dla celow wzglednych) albo 1."""
    if not cel.wzgledny:
        return np.ones(len(df))
    return np.maximum(df[f"{cel.nazwa}_max30"].to_numpy(), 1.0)


def trenuj(df: pd.DataFrame, cel: Cel, kwantyl: float) -> lgb.LGBMRegressor:
    dane = df.dropna(subset=[cel.nazwa, f"{cel.nazwa}_lag168", f"{cel.nazwa}_max30"])
    y = dane[cel.nazwa].to_numpy() / _skala(dane, cel)
    model = lgb.LGBMRegressor(objective="quantile", alpha=kwantyl, **PARAMETRY)
    # regresja kwantylowa takze dla mediany: odporna na pojedyncze skrajne godziny
    return model.fit(dane[cel.cechy], y)


def przewiduj(model: lgb.LGBMRegressor, df: pd.DataFrame, cel: Cel) -> np.ndarray:
    p = model.predict(df[cel.cechy]) * _skala(df, cel)
    return np.maximum(p, 0.0)  # generacja i zapotrzebowanie nie moga byc ujemne


def backtest(df: pd.DataFrame, cel: Cel, ostatnie: int = 12) -> pd.DataFrame:
    """Prognozy z rosnacym oknem dla ostatnich `ostatnie` miesiecy."""
    wyniki = []
    for miesiac, uczenie, test in podzialy_miesieczne(df.index, ostatnie):
        dane_testu = df[test].dropna(subset=[cel.nazwa, f"{cel.nazwa}_lag168", f"{cel.nazwa}_max30"])
        wynik = pd.DataFrame(
            {"cel": cel.nazwa, "miesiac": str(miesiac), "faktyczne": dane_testu[cel.nazwa],
             "naiwna": dane_testu[cel.naiwna], "plan_pse": dane_testu[cel.plan_pse]},
            index=dane_testu.index,
        )
        for q in KWANTYLE:
            wynik[f"p{int(q * 100)}"] = przewiduj(trenuj(df[uczenie], cel, q), dane_testu, cel)
        wyniki.append(wynik)
        log.info("%s %s: nMAE model %.3f, naiwna %.3f", cel.nazwa, miesiac,
                 metryki(wynik["faktyczne"], wynik["p50"])["nmae"], metryki(wynik["faktyczne"], wynik["naiwna"])["nmae"])
    return pd.concat(wyniki)


def waznosc_cech(model: lgb.LGBMRegressor, X: pd.DataFrame) -> pd.Series:
    """Srednia bezwzgledna wartosc SHAP kazdej cechy (malejaco).

    LightGBM liczy SHAP sam (pred_contrib=True), bez biblioteki shap. Wartosc SHAP mowi, o ile
    dana cecha przesunela konkretna prognoze wzgledem sredniej; srednia z |SHAP| = ogolna waznosc.
    """
    wklady = model.predict(X, pred_contrib=True)[:, :-1]  # ostatnia kolumna to wartosc bazowa
    return pd.Series(np.abs(wklady).mean(axis=0), index=X.columns).sort_values(ascending=False)


def kalibracje(bt: pd.DataFrame) -> dict:
    """Dla kazdego celu: wspolczynnik poszerzenia przedzialu 80% z calego backtestu (do produkcji)
    oraz uczciwa ocena metody: kalibracja na pierwszej polowie miesiecy, pokrycie na drugiej."""
    wynik = {}
    for cel, g in bt.groupby("cel"):
        miesiace = sorted(g["miesiac"].unique())
        kal, test = g[g["miesiac"].isin(miesiace[: len(miesiace) // 2])], g[g["miesiac"].isin(miesiace[len(miesiace) // 2 :])]
        k_pol = kalibracja_przedzialu(kal["faktyczne"], kal["p10"], kal["p90"])
        dol, gora = poszerz(test["p10"], test["p90"], k_pol)
        wynik[cel] = {
            "k": kalibracja_przedzialu(g["faktyczne"], g["p10"], g["p90"]),
            "pokrycie_przed_poza_proba": float(((test["faktyczne"] >= test["p10"]) & (test["faktyczne"] <= test["p90"])).mean()),
            "pokrycie_po_poza_proba": float(((test["faktyczne"] >= np.maximum(dol, 0)) & (test["faktyczne"] <= gora)).mean()),
        }
    return wynik


def podsumuj(bt: pd.DataFrame) -> dict:
    """Metryki modelu, prognozy naiwnej i planu PSE + pokrycie przedzialu 80%."""
    wynik = {}
    for cel, grupa in bt.groupby("cel"):
        z_planem = grupa.dropna(subset=["plan_pse"])
        wynik[cel] = {
            "model": metryki(grupa["faktyczne"], grupa["p50"]),
            "naiwna": metryki(grupa["faktyczne"], grupa["naiwna"]),
            "plan_pse_ostatni": metryki(z_planem["faktyczne"], z_planem["plan_pse"]),
            "pokrycie_80": float(((grupa["faktyczne"] >= grupa["p10"]) & (grupa["faktyczne"] <= grupa["p90"])).mean()),
            "godzin": int(len(grupa)),
            "od": str(grupa.index.min()), "do": str(grupa.index.max()),
        }
    return wynik


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    KATALOG.mkdir(parents=True, exist_ok=True)
    with duckdb.connect(str(BAZA), read_only=True) as con:
        con.execute("set TimeZone = 'UTC'")
        df = przygotuj_dane(con)

    bt = pd.concat([backtest(df, cel) for cel in CELE.values()])
    bt.to_parquet(KATALOG / "backtest.parquet")
    podsumowanie = podsumuj(bt)
    for cel, kal in kalibracje(bt).items():
        podsumowanie[cel]["kalibracja"] = kal
    (KATALOG / "metryki.json").write_text(json.dumps(podsumowanie, indent=2, ensure_ascii=False))
    log.info("metryki: %s", json.dumps({c: {k: round(v["nmae"], 4) for k, v in m.items() if isinstance(v, dict)}
                                         for c, m in podsumowanie.items()}))

    # modele koncowe: cala historia, do prognoz na jutro
    waznosci = {}
    for klucz, cel in CELE.items():
        for q in KWANTYLE:
            model = trenuj(df, cel, q)
            model.booster_.save_model(str(KATALOG / f"{klucz}_p{int(q * 100)}.txt"))
            if q == 0.5:
                ostatnie = df.dropna(subset=[cel.nazwa]).loc[lambda d: d.index >= d.index.max() - pd.Timedelta(days=60)]
                waznosci[klucz] = waznosc_cech(model, ostatnie[cel.cechy]).round(5).to_dict()
    (KATALOG / "waznosc_cech.json").write_text(json.dumps(waznosci, indent=2, ensure_ascii=False))
    log.info("zapisano modele i waznosc cech w %s", KATALOG)
    zapisz_w_mlflow(podsumowanie)


def zapisz_w_mlflow(podsumowanie: dict) -> None:
    """Jeden przebieg MLflow na cel: parametry, metryki backtestu i pliki wynikow.

    Baza MLflow w data/mlflow.db; przegladanie: uv run mlflow ui --backend-store-uri sqlite:///data/mlflow.db
    """
    import mlflow

    mlflow.set_tracking_uri(f"sqlite:///{PROJEKT / 'data' / 'mlflow.db'}")
    mlflow.set_experiment("prognoza-na-dobe-naprzod")
    for cel, m in podsumowanie.items():
        with mlflow.start_run(run_name=cel):
            mlflow.log_params({**PARAMETRY, "cel": cel, "wzgledny": CELE[_klucz(cel)].wzgledny,
                               "kwantyle": str(KWANTYLE), "okres_testu": f"{m['od']} .. {m['do']}"})
            mlflow.log_metrics({
                "nmae_model": m["model"]["nmae"], "nmae_naiwna": m["naiwna"]["nmae"],
                "nmae_plan_pse_ostatni": m["plan_pse_ostatni"]["nmae"], "mae_model_mw": m["model"]["mae"],
                "obciazenie_mw": m["model"]["obciazenie"], "pokrycie_80": m["pokrycie_80"],
            })
            for plik in ("metryki.json", "waznosc_cech.json"):
                mlflow.log_artifact(str(KATALOG / plik))


def _klucz(nazwa_kolumny: str) -> str:
    return next(k for k, c in CELE.items() if c.nazwa == nazwa_kolumny)


if __name__ == "__main__":
    main()
