-- Pogoda z 5 punktow -> jeden wiersz na godzine.
-- Wiatr i promieniowanie zostaja osobno dla kazdego punktu (model sam oceni, ktory region
-- najlepiej tlumaczy generacje), temperatura jako srednia, bo popyt zalezy od calego kraju.

select
    godzina_utc,
    avg(temperatura_c)                                                   as temperatura_c,
    avg(wiatr_100m_kmh)                                                  as wiatr_100m_sredni_kmh,
    avg(promieniowanie_wm2)                                              as promieniowanie_srednie_wm2,
    avg(zachmurzenie_proc)                                               as zachmurzenie_srednie_proc,
    max(wiatr_100m_kmh) filter (punkt = 'Pomorze')                       as wiatr_pomorze_kmh,
    max(wiatr_100m_kmh) filter (punkt = 'Wielkopolska')                  as wiatr_wielkopolska_kmh,
    max(wiatr_100m_kmh) filter (punkt = 'Lubelskie')                     as wiatr_lubelskie_kmh,
    max(promieniowanie_wm2) filter (punkt = 'Lubelskie')                 as promieniowanie_lubelskie_wm2,
    max(promieniowanie_wm2) filter (punkt = 'Slask')                     as promieniowanie_slask_wm2,
    max(promieniowanie_wm2) filter (punkt = 'Wielkopolska')              as promieniowanie_wielkopolska_wm2,
    count(*)                                                             as liczba_punktow
from {{ ref('stg_pogoda') }}
group by 1
