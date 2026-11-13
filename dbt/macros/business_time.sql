{% macro business_date(column) -%}
  {% if target.type == 'athena' %}
    cast(at_timezone(with_timezone({{ column }}, 'UTC'), 'Asia/Kolkata') as date)
  {% else %}
    cast({{ column }} at time zone 'Asia/Kolkata' as date)
  {% endif %}
{%- endmacro %}

{% macro month_index(column) -%}
  (extract(year from {{ column }}) * 12 + extract(month from {{ column }}))
{%- endmacro %}

{% test nonnegative(model, column_name) %}
select * from {{ model }} where {{ column_name }} < 0
{% endtest %}
