select customer_id, count(*) as delivered_orders, sum(total_amount) as historical_spend,
       min(order_date) as first_order_date, max(order_date) as last_order_date
from {{ ref('fact_orders') }} where status='delivered' group by customer_id
