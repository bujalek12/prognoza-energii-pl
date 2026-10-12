-- Glowna tabela projektu: jedna godzina = jeden wiersz z pomiarami, planem PSE, pogoda
-- i kalendarzem. Na niej uczy sie model (etap 5) i z niej czyta Power BI (etap 4).
-- Tylko pelne godziny (4 kwadranse), zeby biezaca, niedokonczona godzina nie zanizala srednich.

select
    c.godzina_utc,
    c.czas_lokalny,
    c.data,
    c.godzina,
    c.dzien_tygodnia,
    c.miesiac,
    c.pora_roku,
    c.czy_dzien_roboczy,
    c.czy_swieto,

    e.zapotrzebowanie_mw,
    e.wiatr_mw,
    e.pv_mw,
    e.rezydualne_mw,
    (e.wiatr_mw + e.pv_mw) / e.zapotrzebowanie_mw                   as udzial_oze,

    p.plan_zapotrzebowanie_ostatni_mw,
    p.plan_wiatr_ostatni_mw,
    p.plan_pv_ostatni_mw,
    p.plan_zapotrzebowanie_dzien_przed_mw,
    p.plan_wiatr_dzien_przed_mw,
    p.plan_pv_dzien_przed_mw,

    w.temperatura_c,
    w.wiatr_100m_sredni_kmh,
    w.promieniowanie_srednie_wm2,
    w.zachmurzenie_srednie_proc,
    w.wiatr_pomorze_kmh,
    w.wiatr_wielkopolska_kmh,
    w.wiatr_lubelskie_kmh,
    w.promieniowanie_lubelskie_wm2,
    w.promieniowanie_slask_wm2,
    w.promieniowanie_wielkopolska_wm2
from {{ ref('int_energia_godzinowa') }} e
join {{ ref('dim_czas') }} c using (godzina_utc)
left join {{ ref('int_plan_godzinowy') }} p using (godzina_utc)
left join {{ ref('int_pogoda_godzinowa') }} w using (godzina_utc)
where e.liczba_kwadransow = 4
