with sales as (
    select order_date as business_date,
           sum(case when status = 'delivered' then total_amount else 0 end) as delivered_merchandise_revenue,
           sum(case when status = 'delivered' then 1 else 0 end) as delivered_orders,
           sum(case when status = 'cancelled' then 1 else 0 end) as cancelled_orders
    from {{ ref('fact_orders') }} group by order_date
), cash as (
    select payment_date as business_date, sum(net_cash) as net_cash_collected,
           sum(case when status='succeeded' and transaction_type='refund' then amount else 0 end) as refunded_amount
    from {{ ref('fact_payments') }} where payment_date is not null group by payment_date
)
select coalesce(s.business_date,c.business_date) as business_date,
       coalesce(s.delivered_merchandise_revenue,0) as delivered_merchandise_revenue,
       coalesce(s.delivered_orders,0) as delivered_orders,
       coalesce(s.cancelled_orders,0) as cancelled_orders,
       coalesce(c.net_cash_collected,0) as net_cash_collected,
       coalesce(c.refunded_amount,0) as refunded_amount,
       case when s.delivered_orders>0 then s.delivered_merchandise_revenue/s.delivered_orders else 0 end as average_order_value
from sales s full outer join cash c on s.business_date=c.business_date
