-- Test generyczny: kombinacja kolumn jest unikalna (odpowiednik dbt_utils.unique_combination_of_columns,
-- bez dodatkowego pakietu).
{% test unikalna_kombinacja(model, kolumny) %}
select {{ kolumny | join(', ') }}, count(*) as wystapien
from {{ model }}
group by {{ kolumny | join(', ') }}
having count(*) > 1
{% endtest %}
