-- Archiwum prognoz modelu. Flaga znana_przed_doba: prognoza policzona przed polnoca (czasu
-- polskiego) rozpoczynajaca dobe, ktorej dotyczy, czyli prawdziwa prognoza "na jutro".

select
    p.godzina_utc,
    p.cel,
    p.wygenerowano_utc,
    p.p10, p.p50, p.p90,
    c.data                                                          as doba,
    p.wygenerowano_utc < timezone('Europe/Warsaw', c.data::timestamp) as znana_przed_doba
from {{ source('surowe', 'prognozy_modelu') }} p
join {{ ref('dim_czas') }} c using (godzina_utc)
