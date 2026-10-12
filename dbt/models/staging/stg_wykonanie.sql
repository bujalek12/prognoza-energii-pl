-- Pomiary PSE w ujednoliconej postaci: MW, czas UTC i lokalny, zapotrzebowanie rezydualne.
-- ts_utc w PSE to KONIEC kwadransa, wiec poczatek = ts_utc - 15 min.

select
    ts_utc - interval 15 minute                               as kwadrans_od_utc,
    ts_utc                                                    as kwadrans_do_utc,
    doba,
    zapotrzebowanie                                           as zapotrzebowanie_mw,
    wiatr                                                     as wiatr_mw,
    pv                                                        as pv_mw,
    zapotrzebowanie - wiatr - pv                              as rezydualne_mw,
    publikacja_utc,
    pobrano_utc
from {{ source('surowe', 'wykonanie') }}
