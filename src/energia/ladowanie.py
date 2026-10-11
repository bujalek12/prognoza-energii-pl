"""Ladowanie inkrementalne: ktore doby pobrac przy kolejnym uruchomieniu."""

from datetime import date, timedelta


def okno_do_pobrania(
    ostatnia_doba: date | None,
    dzis: date,
    poczatek_historii: date,
    korekta_dni: int = 3,
) -> tuple[date, date]:
    """Zwraca (od, do): zakres dob handlowych do pobrania, wlacznie z obiema granicami.

    - ostatnia_doba: najpozniejsza doba, ktora juz jest w bazie (None = baza pusta)
    - dzis: dzisiejsza data (parametr, a nie date.today(), zeby dalo sie to testowac)
    - poczatek_historii: od kiedy API ma dane; nigdy nie pobieramy wczesniej
    - korekta_dni: ile dni przed ostatnia doba pobrac ponownie, bo PSE poprawia dane wstecz
    """
    if ostatnia_doba is None:
        return poczatek_historii, dzis
    if ostatnia_doba > dzis:
        raise ValueError(f"w bazie jest doba z przyszlosci: {ostatnia_doba} > {dzis}")
    od = max(poczatek_historii, ostatnia_doba - timedelta(days=korekta_dni))
    return od, dzis
