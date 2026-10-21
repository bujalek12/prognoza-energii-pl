"""Stan projektu i notatki: aktualizowane na koniec kazdego etapu."""

ETAPY = [
    {"nr": 1, "nazwa": "Eksploracja danych, architektura", "status": "gotowe"},
    {"nr": 2, "nazwa": "Ingestia (retry, walidacja, archiwum prognoz)", "status": "gotowe"},
    {"nr": 3, "nazwa": "Hurtownia: DuckDB + dbt", "status": "gotowe"},
    {"nr": 4, "nazwa": "Analiza i Power BI", "status": "gotowe"},
    {"nr": 5, "nazwa": "Model: LightGBM + prognozy pogody", "status": "gotowe"},
    {"nr": 6, "nazwa": "Porównanie z planem PSE", "status": "zbiera dane"},
    {"nr": 7, "nazwa": "Automatyzacja: GitHub Actions, MLflow", "status": "gotowe"},
    {"nr": 8, "nazwa": "Prognoza na jutro w aplikacji", "status": "gotowe"},
]

NOTATKI = [
    (
        "Model a prognoza naiwna",
        "W backteście z 12 miesięcy model ma błąd 2,8% dla zapotrzebowania, 15% dla wiatru i 11% dla PV, "
        "czyli 2–4,5 razy mniej niż prognoza naiwna. Przedziały 80% były za wąskie (51–71% trafień), "
        "więc są poszerzane kalibracją konformalną.",
    ),
    (
        "16 województw zamiast 5 punktów pogody",
        "Błąd prognozy wiatru spadł z 19,0% do 15,2%, a PV z 11,8% do 10,9%. Korelacja średniego wiatru "
        "prawie się nie zmieniła; zysk dał rozkład wiatru: rozrzut między regionami i wiatr na północy.",
    ),
    (
        "Promieniowanie przesunięte o godzinę",
        "Open-Meteo podaje promieniowanie jako średnią z godziny poprzedzającej znacznik czasu. "
        "Po przesunięciu korelacja z generacją PV rośnie z 0,919 do 0,964. To tłumaczy "
        "„dwie gałęzie” z wykresu w etapie 1.",
    ),
    (
        "PSE poprawia pomiary po miesiącach",
        "Dane za 26.10.2025 mają znacznik publikacji z 18.01.2026. Pipeline przy każdym "
        "uruchomieniu pobiera ponownie ostatnie 3 doby i nadpisuje je nowszymi wartościami.",
    ),
    (
        "Archiwum planów PSE",
        "Każda publikacja planu trafia do bazy jako osobna wersja z momentem pobrania. "
        "Za kilka tygodni będzie z tego uczciwy benchmark: plan znany dzień wcześniej.",
    ),
    (
        "Zmiana czasu",
        "PSE zapisuje powtórzoną godzinę jako „02a:15”, a doba ma 92, 96 albo 100 "
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
