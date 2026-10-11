"""Postep projektu: aktualizowany na koniec kazdego etapu."""

ETAPY = [
    {"nr": 1, "nazwa": "Eksploracja danych i architektura", "rola": "DE / DA", "status": "zrobione"},
    {"nr": 2, "nazwa": "Ingestia: retry, walidacja, inkrementalnie, snapshot prognoz", "rola": "DE", "status": "nastepny"},
    {"nr": 3, "nazwa": "Hurtownia DuckDB + dbt, testy danych", "rola": "DE", "status": "czeka"},
    {"nr": 4, "nazwa": "Analiza i dashboard Power BI", "rola": "DA", "status": "czeka"},
    {"nr": 5, "nazwa": "Model: LightGBM + pogoda, backtesting", "rola": "DS", "status": "czeka"},
    {"nr": 6, "nazwa": "Porównanie z PSE, SHAP", "rola": "DS", "status": "czeka"},
    {"nr": 7, "nazwa": "Automatyzacja: GitHub Actions, MLflow", "rola": "MLOps", "status": "czeka"},
    {"nr": 8, "nazwa": "Aplikacja z prognozą na żywo", "rola": "MLOps", "status": "czeka"},
]

ODKRYCIA = {
    1: [
        (
            "Zmiana czasu psuje czas lokalny",
            "Doby mają 92, 96 albo 100 kwadransów, a powtórzona godzina ma zapis `02a:15`. "
            "Kluczem czasu w całym projekcie jest UTC.",
        ),
        (
            "Plan PSE w API jest nadpisywany",
            "Ostatnia wersja planu publikowana jest ~22,5 h po starcie doby, więc zna część przyszłości. "
            "Pipeline będzie archiwizował każdą publikację (snapshot), żeby mieć uczciwy benchmark.",
        ),
        (
            "Pogoda: tylko prognozy, nie fakty",
            "Model jutro zna tylko prognozę pogody. Trening na faktycznej pogodzie to wyciek danych.",
        ),
        (
            "Pogoda dobrze tłumaczy OZE",
            "Korelacja wiatr 100 m vs generacja wiatrowa: 0,81; promieniowanie vs PV: 0,93. "
            "Zależności są nieliniowe, więc lepszy będzie model drzewiasty.",
        ),
        (
            "Święta obniżają popyt",
            "Wyraźny dołek zapotrzebowania w Wielkanoc 2026. Model potrzebuje kalendarza świąt.",
        ),
    ],
}
