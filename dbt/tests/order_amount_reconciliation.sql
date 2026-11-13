select o.order_id
from {{ ref('fact_orders') }} o
left join {{ ref('fact_order_items') }} i on o.order_id=i.order_id
group by o.order_id,o.total_amount
having count(i.order_item_id)=0 or o.total_amount <> coalesce(sum(i.line_amount),0)
