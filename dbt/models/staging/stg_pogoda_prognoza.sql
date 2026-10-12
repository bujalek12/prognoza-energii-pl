-- Najnowsza prognoza pogody dla kazdej godziny i punktu (z archiwum wszystkich pobran).
-- Promieniowanie przesuniete o godzine, jak w stg_pogoda (Open-Meteo: srednia z godziny poprzedzajacej).

with najnowsze as (
    select *
    from {{ source('surowe', 'pogoda_prognoza') }}
    qualify row_number() over (partition by ts_utc, punkt order by pobrano_utc desc) = 1
)

select
    n.ts_utc                     as godzina_utc,
    n.punkt,
    n.temperatura                as temperatura_c,
    n.wiatr_100m                 as wiatr_100m_kmh,
    n.zachmurzenie               as zachmurzenie_proc,
    nast.promieniowanie          as promieniowanie_wm2,
    n.pobrano_utc
from najnowsze n
left join najnowsze nast
    on nast.punkt = n.punkt
   and nast.ts_utc = n.ts_utc + interval 1 hour
