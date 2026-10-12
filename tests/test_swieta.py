"""Testy kalendarza polskich swiat ustawowo wolnych od pracy."""

from datetime import date

from energia.swieta import swieta


def test_wielkanoc_i_poniedzialek_wielkanocny_w_znanych_latach():
    # daty Wielkanocy sprawdzone w kalendarzu: 2024-03-31, 2025-04-20, 2026-04-05
    for niedziela, poniedzialek in [
        (date(2024, 3, 31), date(2024, 4, 1)),
        (date(2025, 4, 20), date(2025, 4, 21)),
        (date(2026, 4, 5), date(2026, 4, 6)),
    ]:
        rok = swieta(niedziela.year)
        assert rok[niedziela] == "Wielkanoc"
        assert rok[poniedzialek] == "Poniedziałek Wielkanocny"


def test_boze_cialo_to_60_dni_po_wielkanocy():
    assert swieta(2026)[date(2026, 6, 4)] == "Boże Ciało"


def test_zielone_swiatki_to_49_dni_po_wielkanocy():
    assert swieta(2025)[date(2025, 6, 8)] == "Zielone Świątki"


def test_wigilia_jest_wolna_od_2025_roku():
    assert date(2024, 12, 24) not in swieta(2024)
    assert swieta(2025)[date(2025, 12, 24)] == "Wigilia"


def test_rok_ma_13_swiat_do_2024_i_14_od_2025():
    assert len(swieta(2024)) == 13
    assert len(swieta(2026)) == 14


def test_swieta_stale():
    rok = swieta(2026)
    for dzien in [date(2026, 1, 1), date(2026, 1, 6), date(2026, 5, 1), date(2026, 5, 3),
                  date(2026, 8, 15), date(2026, 11, 1), date(2026, 11, 11), date(2026, 12, 25), date(2026, 12, 26)]:
        assert dzien in rok
