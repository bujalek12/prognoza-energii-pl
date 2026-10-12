-- Uczciwe porownanie na dobe naprzod: najnowsza prognoza modelu policzona PRZED doba
-- vs plan PSE opublikowany PRZED doba vs to, co sie stalo. Jeden wiersz = godzina x cel.
-- Tabela rosnie o jedna dobe dziennie, od kiedy dziala codzienna prognoza.

with prognozy as (
    select
        godzina_utc, cel, doba,
        arg_max(p10, wygenerowano_utc) as p10,
        arg_max(p50, wygenerowano_utc) as p50,
        arg_max(p90, wygenerowano_utc) as p90,
        max(wygenerowano_utc)          as wygenerowano_utc
    from {{ ref('stg_prognozy_modelu') }}
    where znana_przed_doba
    group by 1, 2, 3
),

fakty as (
    select godzina_utc, 'zapotrzebowanie' as cel, zapotrzebowanie_mw as faktyczne,
           plan_zapotrzebowanie_dzien_przed_mw as plan_pse
    from {{ ref('fct_energia_godzinowa') }}
    union all
    select godzina_utc, 'wiatr', wiatr_mw, plan_wiatr_dzien_przed_mw from {{ ref('fct_energia_godzinowa') }}
    union all
    select godzina_utc, 'pv', pv_mw, plan_pv_dzien_przed_mw from {{ ref('fct_energia_godzinowa') }}
)

select
    p.godzina_utc,
    p.doba,
    p.cel,
    p.wygenerowano_utc,
    p.p10, p.p50, p.p90,
    f.faktyczne,                                     -- null, dopoki godzina sie nie wydarzyla
    f.plan_pse,
    abs(p.p50 - f.faktyczne)                         as blad_modelu_mw,
    abs(f.plan_pse - f.faktyczne)                    as blad_pse_mw,
    f.faktyczne between p.p10 and p.p90              as w_przedziale_80
from prognozy p
left join fakty f using (godzina_utc, cel)
