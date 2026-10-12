"""Cechy modelu prognozy na dobe naprzod.

Scenariusz: prognoze na dobe D robimy w D-1 okolo 10:00. Znamy wtedy pomiary do ~9:00 dnia D-1,
prognozy pogody na D i kalendarz. Dlatego:
- opoznienia (lagi) siegaja minimum 48 h wstecz: ta sama godzina w D-2 jest zawsze znana,
- agregaty (srednia doby, maksimum 30 dni) koncza sie na dobie D-2.
Wszystko, co blizsze niz 48 h, byloby wyciekiem danych z przyszlosci.
"""

import numpy as np
import pandas as pd

# Srodek Polski (okolice Lodzi): do przyblizonej wysokosci slonca dla calego kraju
SZEROKOSC, DLUGOSC = 52.0, 19.4


def dodaj_opoznienia(df: pd.DataFrame, kolumna: str) -> pd.DataFrame:
    """Dodaje cechy z przeszlosci kolumny: lag 48 h, lag 168 h, srednia doby D-2, maksimum 30 dni.

    Indeks: godziny UTC. Przesuniecia liczone po CZASIE (reindex), a nie po numerze wiersza,
    wiec brakujaca godzina w danych nie przesuwa calej reszty.
    """
    s = df[kolumna]
    wynik = df.copy()
    for godzin in (48, 168):
        wynik[f"{kolumna}_lag{godzin}"] = s.reindex(df.index - pd.Timedelta(hours=godzin)).to_numpy()

    doba = df.index.floor("D")
    d2 = doba - pd.Timedelta(days=2)
    dzienne = s.groupby(s.index.floor("D"))
    wynik[f"{kolumna}_srednia_d2"] = dzienne.mean().reindex(d2).to_numpy()
    # maksimum z 30 dni konczacych sie na D-2: przyblizenie mocy zainstalowanej (rosnie z czasem)
    max30 = dzienne.max().rolling("30D").max()
    wynik[f"{kolumna}_max30"] = max30.reindex(d2).to_numpy()
    return wynik


def wysokosc_slonca(czas: pd.DatetimeIndex) -> np.ndarray:
    """Przyblizona wysokosc slonca nad horyzontem (stopnie) w srodku Polski, dla czasu UTC.

    Wzor astronomiczny (deklinacja + rownanie czasu), dokladnosc ~1 stopnia: w zupelnosci
    wystarcza jako cecha dla PV. Daje modelowi "ile slonca moze byc" niezaleznie od pogody.
    """
    n = czas.dayofyear.to_numpy()
    godzina_utc = czas.hour.to_numpy() + czas.minute.to_numpy() / 60
    deklinacja = np.radians(23.44) * np.sin(2 * np.pi * (284 + n) / 365)
    b = 2 * np.pi * (n - 81) / 364
    rownanie_czasu = 9.87 * np.sin(2 * b) - 7.53 * np.cos(b) - 1.5 * np.sin(b)  # minuty
    czas_sloneczny = godzina_utc + DLUGOSC / 15 + rownanie_czasu / 60
    kat_godzinny = np.radians(15 * (czas_sloneczny - 12))
    fi = np.radians(SZEROKOSC)
    sin_h = np.sin(fi) * np.sin(deklinacja) + np.cos(fi) * np.cos(deklinacja) * np.cos(kat_godzinny)
    return np.degrees(np.arcsin(np.clip(sin_h, -1, 1)))
