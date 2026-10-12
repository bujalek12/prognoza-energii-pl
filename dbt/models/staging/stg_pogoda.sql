-- Prognozy pogody przypisane do godziny, ktorej dotycza.
--
-- Uwaga na promieniowanie: Open-Meteo podaje je jako SREDNIA Z GODZINY POPRZEDZAJACEJ
-- znacznik czasu (wartosc o 13:00 opisuje 12:00-13:00). Temperatura, wiatr i zachmurzenie
-- to wartosci chwilowe. Sprawdzone na danych: korelacja PV z promieniowaniem rosnie z 0,919
-- do 0,964 po przesunieciu. To bylo zrodlo "dwoch galezi" na wykresie z etapu 1.

with surowe as (
    select * from {{ source('surowe', 'pogoda') }}
)

select
    s.ts_utc                     as godzina_utc,       -- poczatek godziny
    s.punkt,
    s.temperatura                as temperatura_c,
    s.wiatr_100m                 as wiatr_100m_kmh,
    s.zachmurzenie               as zachmurzenie_proc,
    nast.promieniowanie          as promieniowanie_wm2 -- srednia z godziny [godzina_utc, +1h)
from surowe s
left join surowe nast
    on nast.punkt = s.punkt
   and nast.ts_utc = s.ts_utc + interval 1 hour
