"""Stan projektu i notatki: aktualizowane na koniec kazdego etapu."""

ETAPY = [
    {"nr": 1, "nazwa": "Eksploracja danych, architektura", "status": "gotowe"},
    {"nr": 2, "nazwa": "Ingestia (retry, walidacja, archiwum prognoz)", "status": "w kolejce"},
    {"nr": 3, "nazwa": "Hurtownia: DuckDB + dbt", "status": "—"},
    {"nr": 4, "nazwa": "Dashboard Power BI", "status": "—"},
    {"nr": 5, "nazwa": "Model: LightGBM + prognozy pogody", "status": "—"},
    {"nr": 6, "nazwa": "Porównanie z planem PSE", "status": "—"},
    {"nr": 7, "nazwa": "Automatyzacja: GitHub Actions, MLflow", "status": "—"},
    {"nr": 8, "nazwa": "Prognoza na jutro w aplikacji", "status": "—"},
]

NOTATKI = [
    (
        "Zmiana czasu",
        "PSE zapisuje powtórzoną godzinę jako <code>02a:15</code>, a doba ma 92, 96 albo 100 "
        "kwadransów. Wszystko trzymam w UTC, czas polski liczę dopiero przy prezentacji.",
    ),
    (
        "Plan PSE jest nadpisywany",
        "Wersja planu dostępna w API ma znacznik publikacji średnio 22,5 h po początku doby. "
        "Do uczciwego porównania trzeba samemu archiwizować każdą publikację.",
    ),
    (
        "Pogoda: prognozy, nie pomiary",
        "Model ma dostęp tylko do prognozy pogody, więc uczę go na historycznych prognozach "
        "z Open-Meteo, a nie na reanalizie.",
    ),
    (
        "Wiatr i PV a pogoda",
        "Korelacja z prędkością wiatru na 100 m wynosi 0,81, z promieniowaniem 0,93 (mar–kwi 2026). "
        "Przy PV widać dwie gałęzie, prawdopodobnie przesunięcie czasowe. Do sprawdzenia.",
    ),
    (
        "Święta",
        "W Wielkanoc (5–6.04.2026) szczyt dobowy wyniósł 15–16 GW, w zwykły dzień roboczy "
        "21–23 GW. Model dostanie kalendarz świąt jako cechę.",
    ),
]
