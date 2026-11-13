select order_id from {{ ref('fact_payments') }}
where status='succeeded' group by order_id
having sum(case when transaction_type='refund' then amount else 0 end)
     > sum(case when transaction_type='payment' then amount else 0 end)
