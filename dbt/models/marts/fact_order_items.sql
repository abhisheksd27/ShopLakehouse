{{ config(materialized='incremental', unique_key='order_item_id',
          incremental_strategy='merge' if target.type == 'athena' else 'delete+insert') }}
select id as order_item_id, order_id, product_id, line_number, quantity,
       unit_price, discount_amount,
       cast(quantity * unit_price - discount_amount as decimal(18,2)) as line_amount,
       created_at, updated_at
from {{ ref('stg_order_items') }}
