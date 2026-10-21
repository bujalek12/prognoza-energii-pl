-- Pogoda z 5 punktow -> jeden wiersz na godzine. Makro, bo te sama logike stosujemy do pogody
-- historycznej (trening modelu) i do aktualnej prognozy (prognoza na jutro): cechy musza byc
-- liczone identycznie w obu sciezkach.
{% macro pogoda_godzinowa(relacja) %}
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
    -- rozklad przestrzenny (dodane po eksperymencie z 16 wojewodztwami, notebooks/03):
    -- czy wieje rowno w calym kraju, czy tylko w czesci; i jak wieje na polnocy, gdzie sa farmy
    stddev_samp(wiatr_100m_kmh)                                          as wiatr_100m_odchylenie_kmh,
    max(wiatr_100m_kmh)                                                  as wiatr_100m_max_kmh,
    avg(wiatr_100m_kmh) filter (punkt in ('{{ var("punkty_polnocne") | join("', '") }}'))
                                                                         as wiatr_polnoc_kmh,
    stddev_samp(promieniowanie_wm2)                                      as promieniowanie_odchylenie_wm2,
    count(*)                                                             as liczba_punktow
from {{ relacja }}
group by 1
{% endmacro %}
