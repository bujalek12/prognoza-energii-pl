-- Domyslnie dbt sklada nazwe schematu jako <schemat_profilu>_<schemat_modelu> (np. main_marts).
-- Chcemy krotkie nazwy: staging, intermediate, marts.
{% macro generate_schema_name(custom_schema_name, node) -%}
    {{ custom_schema_name if custom_schema_name else target.schema }}
{%- endmacro %}
