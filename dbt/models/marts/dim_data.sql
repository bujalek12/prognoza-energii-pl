-- Wymiar dat (jeden wiersz na dzien) dla Power BI: tabela dat musi miec ciagly zakres
-- i unikalna kolumne typu data, inaczej nie dziala analiza w czasie (DATEADD, SAMEPERIODLASTYEAR).

with dni as (
    select distinct data from {{ ref('dim_czas') }}
)

select
    d.data,
    year(d.data)                                                         as rok,
    quarter(d.data)                                                      as kwartal,
    month(d.data)                                                        as miesiac,
    -- nazwy po polsku na sztywno: nie zalezymy od ustawien jezykowych serwera
    ['styczeń','luty','marzec','kwiecień','maj','czerwiec','lipiec','sierpień',
     'wrzesień','październik','listopad','grudzień'][month(d.data)]       as nazwa_miesiaca,
    strftime(d.data, '%Y-%m')                                            as rok_miesiac,
    isodow(d.data)                                                       as dzien_tygodnia,
    ['pon','wt','śr','czw','pt','sob','nd'][isodow(d.data)]               as nazwa_dnia,
    case
        when s.data is not null or isodow(d.data) = 7 then 'niedziela i święto'
        when isodow(d.data) = 6 then 'sobota'
        else 'dzień roboczy'
    end                                                                  as typ_dnia,
    s.nazwa                                                              as nazwa_swieta
from dni d
left join {{ ref('swieta') }} s using (data)
