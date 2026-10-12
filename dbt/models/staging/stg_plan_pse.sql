-- Kazda wersja planu PSE. Flaga znany_przed_doba mowi, czy ta wersja byla opublikowana
-- przed polnoca (czasu polskiego) rozpoczynajaca dobe, ktorej dotyczy. Tylko takie wersje
-- sa uczciwym benchmarkiem dla prognozy "na jutro".

select
    ts_utc - interval 15 minute                                            as kwadrans_od_utc,
    ts_utc                                                                 as kwadrans_do_utc,
    doba,
    publikacja_utc,
    pobrano_utc,
    zapotrzebowanie_plan                                                   as zapotrzebowanie_plan_mw,
    wiatr_plan                                                             as wiatr_plan_mw,
    pv_plan                                                                as pv_plan_mw,
    -- polnoc czasu polskiego jako moment w UTC (timezone() obsluguje zmiane czasu)
    timezone('Europe/Warsaw', doba::timestamp)                             as poczatek_doby_utc,
    publikacja_utc < timezone('Europe/Warsaw', doba::timestamp)            as znany_przed_doba
from {{ source('surowe', 'plan_pse') }}
