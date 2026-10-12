-- Kazda godzina miedzy pierwsza a ostatnia musi byc w fct_energia_godzinowa.
-- Zwraca brakujace godziny (test przechodzi, gdy wynik jest pusty).
with zakres as (
    select min(godzina_utc) as od, max(godzina_utc) as do_ from {{ ref('fct_energia_godzinowa') }}
),
oczekiwane as (
    select unnest(generate_series(od, do_, interval 1 hour)) as godzina_utc from zakres
)
select o.godzina_utc
from oczekiwane o
left join {{ ref('fct_energia_godzinowa') }} f using (godzina_utc)
where f.godzina_utc is null
