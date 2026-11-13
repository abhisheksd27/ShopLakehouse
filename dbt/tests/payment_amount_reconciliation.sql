select o.order_id from {{ ref('fact_orders') }} o
left join {{ ref('fact_payments') }} p
  on o.order_id=p.order_id and p.status='succeeded' and p.transaction_type='payment'
where o.status in ('confirmed','shipped','delivered','cancelled')
group by o.order_id,o.total_amount
having coalesce(sum(p.amount),0) <> o.total_amount
