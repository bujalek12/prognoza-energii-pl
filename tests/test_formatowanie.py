"""Testy polskiej odmiany rzeczownikow po liczebnikach."""

import pytest

from energia.formatowanie import odmiana


@pytest.mark.parametrize(
    ("n", "oczekiwane"),
    [(0, "dób"), (1, "doba"), (2, "doby"), (4, "doby"), (5, "dób"), (11, "dób"), (12, "dób"),
     (14, "dób"), (21, "dób"), (22, "doby"), (24, "doby"), (25, "dób"), (102, "doby"), (112, "dób")],
)
def test_odmiana_doby(n, oczekiwane):
    assert odmiana(n, "doba", "doby", "dób") == oczekiwane
