"""Formatowanie tekstow po polsku."""


def odmiana(n: int, jeden: str, kilka: str, wiele: str) -> str:
    """Forma rzeczownika po liczbie: 1 doba, 2-4 doby, 5-21 dob, 22-24 doby, 112 dob.

    Regula: "kilka" gdy ostatnia cyfra to 2-4, ale nie dla 12-14 (nastki zawsze "wiele").
    """
    if n == 1:
        return jeden
    if n % 10 in (2, 3, 4) and n % 100 not in (12, 13, 14):
        return kilka
    return wiele
