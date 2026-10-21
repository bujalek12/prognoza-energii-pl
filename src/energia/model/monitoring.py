"""Monitoring prognoz na zywo: czy model w produkcji dziala tak, jak w backteście.

Uruchomienie: uv run python -m energia.model.monitoring
Wypisuje podsumowanie (Markdown) i zapisuje alarmy do data/alarmy.md. Workflow codziennie
zaklada z nich zgloszenie (issue) na GitHubie, wiec o problemie przychodzi mail.
"""

import json
from datetime import date, timedelta

import duckdb
import pandas as pd

MNOZNIK_BLEDU = 2.0     # alarm, gdy blad z 7 dni > 2 x blad z backtestu
MIN_POKRYCIE = 0.6      # alarm, gdy przedzial 80% obejmuje mniej niz 60% godzin
MIN_DOB = 5             # ponizej tylu dob nie oceniamy jakosci (za duzy przypadek)
NAZWY = {"zapotrzebowanie": "zapotrzebowanie", "wiatr": "wiatr", "pv": "fotowoltaika"}


def ocen_ostatnie_dni(ocena: pd.DataFrame, dzis: date, dni: int = 7) -> dict[str, dict]:
    """nMAE modelu i planu PSE (oba sprzed doby) oraz pokrycie przedzialu z ostatnich `dni` dob.

    `ocena` to wiersze z marts.fct_ocena_prognoz (tylko godziny, ktore juz sie wydarzyly).
    """
    okno = ocena[(ocena["doba"] >= dzis - timedelta(days=dni)) & (ocena["doba"] < dzis)].dropna(subset=["faktyczne"])
    wynik = {}
    for cel, g in okno.groupby("cel"):
        srednia = g["faktyczne"].mean()
        z_planem = g.dropna(subset=["plan_pse"])
        wynik[cel] = {
            "dob": int(g["doba"].nunique()),
            "nmae_model": float((g["p50"] - g["faktyczne"]).abs().mean() / srednia),
            # porownanie z PSE tylko na godzinach, dla ktorych mamy plan sprzed doby
            "dob_z_planem": int(z_planem["doba"].nunique()),
            "nmae_model_wspolne": float((z_planem["p50"] - z_planem["faktyczne"]).abs().mean() / z_planem["faktyczne"].mean())
            if len(z_planem) else None,
            "nmae_pse": float((z_planem["plan_pse"] - z_planem["faktyczne"]).abs().mean() / z_planem["faktyczne"].mean())
            if len(z_planem) else None,
            "pokrycie": float(g["w_przedziale_80"].mean()),
        }
    return wynik


def alarmy(ocena: dict[str, dict], backtest: dict[str, float], prognoza_na_jutro: bool) -> list[str]:
    """Lista problemow do zgloszenia (pusta = wszystko w porzadku)."""
    problemy = []
    if not prognoza_na_jutro:
        problemy.append("Brak prognozy na jutro: pipeline albo trening nie zadziałał.")
    for cel, o in ocena.items():
        if o["dob"] < MIN_DOB:
            continue
        nazwa = NAZWY.get(cel, cel)
        if o["nmae_model"] > MNOZNIK_BLEDU * backtest[cel]:
            problemy.append(
                f"{nazwa}: błąd z ostatnich {o['dob']} dób {o['nmae_model']:.1%} "
                f"wobec {backtest[cel]:.1%} w backteście (ponad {MNOZNIK_BLEDU:.0f} razy więcej)."
            )
        if o["pokrycie"] < MIN_POKRYCIE:
            problemy.append(
                f"{nazwa}: przedział 80% objął tylko {o['pokrycie']:.0%} godzin (próg {MIN_POKRYCIE:.0%})."
            )
    return problemy


def podsumowanie(ocena: dict[str, dict], problemy: list[str]) -> str:
    wiersze = ["| cel | dób | model | w przedziale 80% | dób z planem PSE | model vs PSE (te same godziny) |",
               "|---|---|---|---|---|---|"]
    for cel, o in sorted(ocena.items()):
        porownanie = (f"{o['nmae_model_wspolne']:.1%} vs {o['nmae_pse']:.1%}" if o["nmae_pse"] is not None else "—")
        wiersze.append(f"| {NAZWY.get(cel, cel)} | {o['dob']} | {o['nmae_model']:.1%} | {o['pokrycie']:.0%} | "
                       f"{o['dob_z_planem']} | {porownanie} |")
    status = "\n".join(f"- {p}" for p in problemy) if problemy else "Bez uwag."
    return "### Prognozy z ostatnich 7 dób (oba sprzed doby)\n\n" + "\n".join(wiersze) + f"\n\n**Status:** {status}\n"


def main() -> None:
    from energia.model.trening import KATALOG
    from energia.pipeline import BAZA, PROJEKT

    dzis = date.today()
    with duckdb.connect(str(BAZA), read_only=True) as con:
        con.execute("set TimeZone = 'UTC'")
        dane = con.sql("select doba, cel, faktyczne, p50, plan_pse, w_przedziale_80 from marts.fct_ocena_prognoz").df()
        dane["doba"] = pd.to_datetime(dane["doba"]).dt.date
        jutro = con.execute(
            "select count(*) from prognozy_modelu p join marts.dim_czas c using (godzina_utc) where c.data = ?",
            [dzis + timedelta(days=1)],
        ).fetchone()[0]
    metryki = json.loads((KATALOG / "metryki.json").read_text())
    backtest = {"zapotrzebowanie": metryki["zapotrzebowanie_mw"]["model"]["nmae"],
                "wiatr": metryki["wiatr_mw"]["model"]["nmae"], "pv": metryki["pv_mw"]["model"]["nmae"]}

    ocena = ocen_ostatnie_dni(dane, dzis)
    problemy = alarmy(ocena, backtest, prognoza_na_jutro=jutro > 0)
    print(podsumowanie(ocena, problemy))
    (PROJEKT / "data" / "alarmy.md").write_text("\n".join(f"- {p}" for p in problemy))


if __name__ == "__main__":
    main()
