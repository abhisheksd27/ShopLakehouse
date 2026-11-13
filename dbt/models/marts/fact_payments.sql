select id as payment_id, order_id, payment_reference, transaction_type,
       payment_method, status, amount, currency, processed_at,
       {{ business_date('processed_at') }} as payment_date,
       case when status <> 'succeeded' then cast(0 as decimal(18,2))
            when transaction_type = 'refund' then -amount else amount end as net_cash,
       created_at, updated_at
from {{ ref('stg_payments') }}
