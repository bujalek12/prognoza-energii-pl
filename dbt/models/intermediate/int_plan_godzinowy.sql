-- Dwie wersje planu PSE na kazda godzine:
--   *_ostatni      : najnowsza znana wersja (moze byc poprawiana w trakcie doby),
--   *_dzien_przed  : najnowsza wersja opublikowana PRZED poczatkiem doby = uczciwy benchmark.
-- Historyczne dane z API maja tylko wersje koncowe, wiec *_dzien_przed jest wypelniane
-- dopiero od momentu, gdy pipeline zaczal archiwizowac plany (11.10.2026).

with kwadranse as (
    select
        kwadrans_od_utc,
        arg_max(zapotrzebowanie_plan_mw, publikacja_utc)                          as zapotrzebowanie_ostatni,
        arg_max(wiatr_plan_mw, publikacja_utc)                                    as wiatr_ostatni,
        arg_max(pv_plan_mw, publikacja_utc)                                       as pv_ostatni,
        arg_max(zapotrzebowanie_plan_mw, publikacja_utc) filter (znany_przed_doba) as zapotrzebowanie_dzien_przed,
        arg_max(wiatr_plan_mw, publikacja_utc) filter (znany_przed_doba)           as wiatr_dzien_przed,
        arg_max(pv_plan_mw, publikacja_utc) filter (znany_przed_doba)              as pv_dzien_przed,
        count(*)                                                                    as liczba_wersji
    from {{ ref('stg_plan_pse') }}
    group by 1
)

select
    date_trunc('hour', kwadrans_od_utc)   as godzina_utc,
    avg(zapotrzebowanie_ostatni)          as plan_zapotrzebowanie_ostatni_mw,
    avg(wiatr_ostatni)                    as plan_wiatr_ostatni_mw,
    avg(pv_ostatni)                       as plan_pv_ostatni_mw,
    avg(zapotrzebowanie_dzien_przed)      as plan_zapotrzebowanie_dzien_przed_mw,
    avg(wiatr_dzien_przed)                as plan_wiatr_dzien_przed_mw,
    avg(pv_dzien_przed)                   as plan_pv_dzien_przed_mw,
    max(liczba_wersji)                    as liczba_wersji_planu
from kwadranse
group by 1
