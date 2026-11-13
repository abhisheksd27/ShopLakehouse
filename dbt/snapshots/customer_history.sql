{% snapshot customer_history %}
{{ config(unique_key='id', strategy='timestamp', updated_at='updated_at',
          invalidate_hard_deletes=False, table_type='iceberg') }}
select * from {{ source('silver', 'customers') }}
{% endsnapshot %}
