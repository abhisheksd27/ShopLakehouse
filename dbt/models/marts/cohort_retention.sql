with first_purchase as (
 select customer_id, min(order_date) as first_date
 from {{ ref('fact_orders') }} where status='delivered' group by customer_id
), active as (
 select distinct o.customer_id, cast(date_trunc('month', f.first_date) as date) as cohort_month,
        cast({{ month_index('o.order_date') }} - {{ month_index('f.first_date') }} as integer) as months_since_first
 from {{ ref('fact_orders') }} o join first_purchase f on o.customer_id=f.customer_id
 where o.status='delivered'
), sizes as (
 select cohort_month,count(*) as cohort_size from active where months_since_first=0 group by cohort_month
)
select a.cohort_month,a.months_since_first,count(*) as active_customers,s.cohort_size,
       cast(count(*) as decimal(18,6))/s.cohort_size as retention_rate
from active a join sizes s on a.cohort_month=s.cohort_month
group by a.cohort_month,a.months_since_first,s.cohort_size
