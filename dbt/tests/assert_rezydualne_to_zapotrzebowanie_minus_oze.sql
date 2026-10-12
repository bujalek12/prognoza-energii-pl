-- Kontrola spojnosci: rezydualne = zapotrzebowanie - wiatr - PV (z tolerancja na zaokraglenia).
select godzina_utc, zapotrzebowanie_mw, wiatr_mw, pv_mw, rezydualne_mw
from {{ ref('fct_energia_godzinowa') }}
where abs(rezydualne_mw - (zapotrzebowanie_mw - wiatr_mw - pv_mw)) > 0.01
