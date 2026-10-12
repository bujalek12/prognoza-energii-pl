-- Pogoda historyczna (prognozy z archiwum Open-Meteo) -> godziny. Logika w makrze pogoda_godzinowa.
-- Wiatr i promieniowanie osobno dla punktow (model oceni, ktory region tlumaczy generacje),
-- temperatura jako srednia, bo popyt zalezy od calego kraju.
{{ pogoda_godzinowa(ref('stg_pogoda')) }}
