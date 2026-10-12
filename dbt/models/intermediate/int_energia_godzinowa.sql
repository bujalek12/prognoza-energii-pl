-- Kwadranse -> godziny. Srednia moc z 4 kwadransow w MW to jednoczesnie energia w MWh
-- w tej godzinie. Liczba kwadransow pozwala wykryc niepelne godziny (np. biezaca).

select
    date_trunc('hour', kwadrans_od_utc)   as godzina_utc,
    avg(zapotrzebowanie_mw)               as zapotrzebowanie_mw,
    avg(wiatr_mw)                         as wiatr_mw,
    avg(pv_mw)                            as pv_mw,
    avg(rezydualne_mw)                    as rezydualne_mw,
    count(*)                              as liczba_kwadransow
from {{ ref('stg_wykonanie') }}
group by 1
