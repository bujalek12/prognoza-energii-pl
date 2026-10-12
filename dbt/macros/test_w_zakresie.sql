-- Wlasny test generyczny: wartosci kolumny musza miescic sie w [min, max].
-- Lapie np. zapotrzebowanie w kW zamiast MW albo ujemna generacje.
{% test w_zakresie(model, column_name, min, max) %}
select {{ column_name }}
from {{ model }}
where {{ column_name }} < {{ min }} or {{ column_name }} > {{ max }}
{% endtest %}
