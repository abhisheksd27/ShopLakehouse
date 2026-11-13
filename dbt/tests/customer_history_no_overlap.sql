select a.customer_id from {{ ref('dim_customer') }} a
join {{ ref('dim_customer') }} b
  on a.customer_id=b.customer_id and a.customer_key<>b.customer_key
 and a.valid_from < coalesce(b.valid_to,cast('9999-12-31' as timestamp))
 and b.valid_from < coalesce(a.valid_to,cast('9999-12-31' as timestamp))
