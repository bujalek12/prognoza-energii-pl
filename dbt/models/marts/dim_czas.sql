-- Wymiar czasu: jeden wiersz na godzine UTC, z atrybutami w czasie polskim.
-- Klucz w UTC, wiec przy zmianie czasu nic sie nie dubluje ani nie znika:
-- jesienia dwie rozne godziny UTC maja te sama godzine lokalna (2:00), wiosna 2:00 nie wystepuje.

with godziny as (
    select unnest(generate_series(
        (select min(godzina_utc) from {{ ref('int_energia_godzinowa') }}),
        (select max(godzina_utc) from {{ ref('int_energia_godzinowa') }}) + interval 2 day,  -- zapas na prognozy
        interval 1 hour
    )) as godzina_utc
),

lokalnie as (
    select godzina_utc, timezone('Europe/Warsaw', godzina_utc) as czas_lokalny
    from godziny
)

select
    l.godzina_utc,
    l.czas_lokalny,
    l.czas_lokalny::date                                              as data,
    hour(l.czas_lokalny)                                              as godzina,
    isodow(l.czas_lokalny)                                            as dzien_tygodnia,  -- 1 = poniedzialek
    year(l.czas_lokalny)                                              as rok,
    month(l.czas_lokalny)                                             as miesiac,
    case
        when month(l.czas_lokalny) in (12, 1, 2) then 'zima'
        when month(l.czas_lokalny) in (3, 4, 5)  then 'wiosna'
        when month(l.czas_lokalny) in (6, 7, 8)  then 'lato'
        else 'jesień'
    end                                                               as pora_roku,
    isodow(l.czas_lokalny) >= 6                                       as czy_weekend,
    s.data is not null                                                as czy_swieto,
    s.nazwa                                                           as nazwa_swieta,
    isodow(l.czas_lokalny) < 6 and s.data is null                     as czy_dzien_roboczy
from lokalnie l
left join {{ ref('swieta') }} s on s.data = l.czas_lokalny::date
