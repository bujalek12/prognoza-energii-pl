"""Backtest z rosnacym oknem (expanding window): model testowany na miesiacu M uczy sie na
wszystkim sprzed M. Tak wygladaloby to w rzeczywistosci: co miesiac douczamy model na nowych
danych i prognozujemy kolejne dni. Losowy podzial train/test (jak w klasycznym ML) bylby tu
bledem: model "widzialby przyszlosc" (np. sasiednie godziny tego samego dnia).
"""

from collections.abc import Iterator

import numpy as np
import pandas as pd


def podzialy_miesieczne(
    idx: pd.DatetimeIndex, ostatnie: int
) -> Iterator[tuple[pd.Period, np.ndarray, np.ndarray]]:
    """Dla kazdego z `ostatnie` miesiecy danych: (miesiac, maska uczenia, maska testu)."""
    miesiace = idx.tz_convert(None).to_period("M")
    for miesiac in sorted(miesiace.unique())[-ostatnie:]:
        test = miesiace == miesiac
        uczenie = idx < idx[test].min()
        yield miesiac, uczenie, test


def metryki(y: np.ndarray, p: np.ndarray) -> dict[str, float]:
    """MAE (MW), nMAE (MAE / srednia faktyczna) i obciazenie (srednio p - y; > 0 = zawyzanie)."""
    y, p = np.asarray(y, dtype=float), np.asarray(p, dtype=float)
    mae = float(np.mean(np.abs(p - y)))
    return {"mae": mae, "nmae": mae / float(np.mean(y)), "obciazenie": float(np.mean(p - y))}


def kalibracja_przedzialu(y: np.ndarray, p10: np.ndarray, p90: np.ndarray, poziom: float = 0.8) -> float:
    """Kalibracja konformalna (CQR z normalizacja szerokoscia): o jaki ulamek szerokosci poszerzyc
    przedzial [p10, p90], zeby na danych kalibracyjnych obejmowal `poziom` obserwacji.

    Wynik dla obserwacji: o ile (w szerokosciach przedzialu) wypadla poza przedzial; ujemny = w srodku.
    Bierzemy kwantyl tych wynikow z poprawka na skonczona probe ((n + 1) * poziom / n).
    """
    y, p10, p90 = (np.asarray(a, dtype=float) for a in (y, p10, p90))
    szerokosc = np.maximum(p90 - p10, 1e-9)
    wynik = np.maximum(p10 - y, y - p90) / szerokosc
    n = len(wynik)
    return float(np.quantile(wynik, min(1.0, np.ceil((n + 1) * poziom) / n)))


def poszerz(p10: np.ndarray, p90: np.ndarray, k: float) -> tuple[np.ndarray, np.ndarray]:
    """Poszerza przedzial o k szerokosci z kazdej strony (zerowa szerokosc zostaje zerowa)."""
    szerokosc = np.asarray(p90, dtype=float) - np.asarray(p10, dtype=float)
    return np.asarray(p10) - k * szerokosc, np.asarray(p90) + k * szerokosc
