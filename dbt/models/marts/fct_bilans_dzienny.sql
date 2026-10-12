-- Bilans dobowy (doba wg czasu polskiego) pod raporty i Power BI.
-- Energia w GWh: suma godzinowych MWh / 1000.

with godzin_w_dobie as (
    -- ile godzin ma doba wg kalendarza: 23 (przejscie na czas letni), 25 (na zimowy), 24
    select data, count(*) as oczekiwane from {{ ref('dim_czas') }} group by data
)

select
    data,
    any_value(dzien_tygodnia)                                   as dzien_tygodnia,
    any_value(miesiac)                                          as miesiac,
    any_value(pora_roku)                                        as pora_roku,
    any_value(czy_dzien_roboczy)                                as czy_dzien_roboczy,
    any_value(czy_swieto)                                       as czy_swieto,
    sum(zapotrzebowanie_mw) / 1000                              as zapotrzebowanie_gwh,
    sum(wiatr_mw) / 1000                                        as wiatr_gwh,
    sum(pv_mw) / 1000                                           as pv_gwh,
    sum(rezydualne_mw) / 1000                                   as rezydualne_gwh,
    (sum(wiatr_mw) + sum(pv_mw)) / sum(zapotrzebowanie_mw)      as udzial_oze,
    max(zapotrzebowanie_mw)                                     as szczyt_zapotrzebowania_mw,
    min(rezydualne_mw)                                          as minimum_rezydualne_mw,
    max(udzial_oze)                                             as max_godzinowy_udzial_oze,
    avg(temperatura_c)                                          as temperatura_srednia_c,
    count(*)                                                    as liczba_godzin
from {{ ref('fct_energia_godzinowa') }}
join godzin_w_dobie using (data)
group by data
-- tylko pelne doby: tyle godzin, ile ma doba w kalendarzu (biezaca doba odpada sama)
having count(*) = any_value(oczekiwane)
