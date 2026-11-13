select o.id as order_id, o.customer_id,
       coalesce(c.customer_key, 'unknown') as customer_key, o.ordered_at,
       {{ business_date('o.ordered_at') }} as order_date,
       o.status, o.currency, o.total_amount, o.shipping_address_id,
       o.created_at, o.updated_at
from {{ ref('stg_orders') }} o
left join {{ ref('dim_customer') }} c
  on o.customer_id = c.customer_id and o.ordered_at >= c.valid_from
 and (o.ordered_at < c.valid_to or c.valid_to is null)
