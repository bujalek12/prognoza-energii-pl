# Raport Power BI: Bilans KSE

Wszystko, czego potrzeba do zbudowania raportu w Power BI Desktop (Windows), w ok. godzinę.

| plik | co to |
|---|---|
| `dane/*.parquet` | tabele z hurtowni dbt (generowane, nie ma ich w repo) |
| `miary.dax` | wszystkie miary z komentarzami |
| `motyw_ciemny.json`, `motyw_jasny.json` | motywy kolorystyczne zgodne z aplikacją |

## 0. Dane

Na komputerze z projektem:

```bash
uv run python -m energia.pipeline   # świeże dane + dbt build
uv run python -m energia.eksport    # -> powerbi/dane/*.parquet
```

Skopiuj folder `powerbi/` na komputer z Power BI (np. przez OneDrive albo pendrive).

## 1. Import

1. **Pobierz dane → Więcej → Parquet**. Kolejno trzy pliki: `fct_bilans_dzienny`, `fct_energia_godzinowa`, `dim_data`.
2. W Power Query sprawdź typy: `data` = *Data*, `godzina_utc` i `czas_lokalny` = *Data/godzina*,
   kolumny `czy_*` = *Prawda/Fałsz*. Parquet zwykle ma je poprawnie od razu.
3. **Zamknij i zastosuj**.

> Ścieżki do plików trzymaj w parametrze (**Zarządzaj parametrami → Nowy**, np. `Folder`),
> a w każdym zapytaniu zamień ścieżkę na `Folder & "fct_bilans_dzienny.parquet"`.
> Po przeniesieniu raportu zmieniasz jedno miejsce zamiast trzech.

## 2. Model (gwiazda)

```
fct_bilans_dzienny  (*) ──── (1)  dim_data  (1) ──── (*)  fct_energia_godzinowa
            [data]                  [data]                 [data]
```

- Widok **Model** → przeciągnij `fct_bilans_dzienny[data]` na `dim_data[data]`, to samo dla `fct_energia_godzinowa[data]`.
- Kardynalność **wiele do jednego**, kierunek filtrowania **pojedynczy** (od wymiaru do faktu).
- Ukryj w widoku raportu kolumny kluczy w faktach (`data`), żeby filtrować zawsze przez `dim_data`.

## 3. Tabela dat

`dim_data` → **Narzędzia tabeli → Oznacz jako tabelę dat** → kolumna `data`.
Bez tego nie działają `SAMEPERIODLASTYEAR` i `TOTALYTD`.

Sortowanie: `nazwa_miesiaca` → **Sortuj według kolumny** → `miesiac`; `nazwa_dnia` → `dzien_tygodnia`.

## 4. Miary

**Wprowadź dane** → pusta tabela `_Miary` → wklej miary z `miary.dax` (każdą przez **Nowa miara**).
Formaty: miary `GWh` i `MW` jako liczba całkowita z separatorem, `Udział OZE` jako procent z 1 miejscem.

## 5. Motyw

**Widok → Motywy → Przeglądaj motywy** → `motyw_ciemny.json` (albo jasny).
Kolejność kolorów serii: Rezydualne (niebieski), Wiatr (zielony), PV (bursztynowy), Zapotrzebowanie (jasny/ciemny).
Jeśli Power BI przypisze kolory inaczej, ustaw je ręcznie w **Formatowanie → Kolory danych**. Ważne, żeby
wiatr był zawsze zielony, a PV bursztynowe na każdej stronie.

## 6. Strony raportu

### Strona 1: „Przegląd”
Pytanie: *jak szybko rośnie udział OZE?*

| wizualizacja | pola |
|---|---|
| Fragmentator (u góry) | `dim_data[rok]`, `dim_data[typ_dnia]` |
| 4 karty | `Udział OZE`, `Zmiana udziału OZE r/r (pp)`, `Szczyt zapotrzebowania MW`, `Minimum rezydualne MW` |
| Wykres warstwowy skumulowany | oś: `dim_data[rok_miesiac]`, wartości: `Wiatr GWh`, `PV GWh` |
| Wykres liniowy | oś: `dim_data[rok_miesiac]`, wartości: `Udział OZE`, `Udział OZE rok wcześniej` |

Tytuł strony jako wniosek, nie etykieta, np. *„Wiatr i słońce pokrywają już ponad jedną trzecią zapotrzebowania latem”*.

### Strona 2: „Profil dobowy”
Pytanie: *kiedy OZE dominują i co to znaczy dla elektrowni konwencjonalnych?*

| wizualizacja | pola |
|---|---|
| Macierz (mapa ciepła) | wiersze: `fct_energia_godzinowa[godzina]`, kolumny: `dim_data[nazwa_miesiaca]`, wartości: `Średni udział OZE godzinowy` + **formatowanie warunkowe → kolor tła → gradient** (od koloru tła do niebieskiego) |
| Wykres liniowy „kaczka” | oś: `fct_energia_godzinowa[godzina]`, wartości: `Rezydualne średnio MW`, legenda: `dim_data[rok]`; filtr strony: `dim_data[miesiac]` 6–8 i `fct_energia_godzinowa[czy_dzien_roboczy]` = Prawda |
| Karta | `Rampa wieczorna GW` |
| Karta | `Godziny z OZE ponad 50%` |

### Strona 3: „Pogoda i popyt”
Pytanie: *od czego zależy zapotrzebowanie?*

| wizualizacja | pola |
|---|---|
| Wykres punktowy | X: `fct_bilans_dzienny[temperatura_srednia_c]`, Y: `fct_bilans_dzienny[zapotrzebowanie_gwh]`, szczegóły: `dim_data[data]`, legenda: `dim_data[typ_dnia]` |
| Wykres kolumnowy | oś: `dim_data[typ_dnia]`, wartość: średnia `fct_bilans_dzienny[zapotrzebowanie_gwh]` |
| Tabela | `dim_data[nazwa_swieta]`, `Zapotrzebowanie GWh`, `Udział OZE` (filtr: `nazwa_swieta` nie jest puste) |

### Strona 4 (opcjonalnie): „Plan PSE”
`Błąd planu PSE % (wersja ostatnia)` i `Błąd planu PSE % (dzień przed)` w czasie. Na stronie notka, dlaczego
druga miara jest uczciwym benchmarkiem, a pierwsza nie (wersja ostatnia bywa poprawiana w trakcie doby).

## 7. Zasady, które odróżniają raport analityka od „ładnych wykresów”

- **Tytuł = wniosek.** Czytelnik ma wiedzieć, co zobaczy, zanim spojrzy na wykres.
- **Jedna oś Y na wykresie.** Nie łącz GWh i % na dwóch osiach. Zrób dwa wykresy.
- **Kolor = zjawisko, a nie numer serii.** Wiatr zawsze zielony, PV zawsze bursztynowe.
- **Porównania rok do roku tylko na tych samych miesiącach.** Dane zaczynają się w czerwcu 2024.
- **Notka o źródle** w stopce każdej strony: „Dane: PSE, Open-Meteo. Hurtownia: dbt + DuckDB.”

## 8. Do portfolio

- Zrzuty ekranu każdej strony → `powerbi/zrzuty/` i do README projektu.
- Plik `.pbix` dodaj do repo (z danymi to ok. 2–3 MB), żeby rekruter mógł go otworzyć.
- Opcjonalnie publikacja w Power BI Service przez **Opublikuj w sieci Web**. To publiczny link, a dane są publiczne, więc to bezpieczne.
