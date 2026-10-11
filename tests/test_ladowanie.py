"""Testy wyboru okna dat do pobrania przy ladowaniu inkrementalnym.

Zadanie: zaimplementuj `okno_do_pobrania` w src/energia/ladowanie.py tak, zeby
wszystkie testy ponizej przeszly. Uruchomienie: uv run pytest tests/test_ladowanie.py
"""

from datetime import date

import pytest

from energia.ladowanie import okno_do_pobrania

POCZATEK = date(2024, 6, 14)  # pierwsza doba dostepna w API PSE
DZIS = date(2026, 10, 11)


def test_pusta_baza_pobiera_cala_historie():
    assert okno_do_pobrania(None, DZIS, POCZATEK) == (POCZATEK, DZIS)


def test_pobiera_od_ostatniej_doby_cofajac_sie_o_okno_korekt():
    # PSE poprawia dane wstecz, wiec ostatnie dni pobieramy jeszcze raz
    assert okno_do_pobrania(date(2026, 10, 10), DZIS, POCZATEK, korekta_dni=3) == (date(2026, 10, 7), DZIS)


def test_okno_korekt_nie_wychodzi_przed_poczatek_historii():
    assert okno_do_pobrania(date(2024, 6, 15), DZIS, POCZATEK, korekta_dni=3) == (POCZATEK, DZIS)


def test_domyslne_okno_korekt_to_trzy_dni():
    assert okno_do_pobrania(date(2026, 10, 10), DZIS, POCZATEK) == (date(2026, 10, 7), DZIS)


def test_dane_aktualne_na_dzis_i_tak_odswieza_okno_korekt():
    assert okno_do_pobrania(DZIS, DZIS, POCZATEK, korekta_dni=2) == (date(2026, 10, 9), DZIS)


def test_doba_z_przyszlosci_w_bazie_to_blad():
    # Jesli w bazie jest doba pozniejsza niz dzis, cos jest nie tak (strefa czasowa? zly zegar?)
    with pytest.raises(ValueError):
        okno_do_pobrania(date(2026, 10, 12), DZIS, POCZATEK)
