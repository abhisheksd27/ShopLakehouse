select 'orders' as entity
where (select count(*) from {{ source('silver','orders') }}) <> (select count(*) from {{ ref('fact_orders') }})
union all
select 'order_items' where (select count(*) from {{ source('silver','order_items') }}) <> (select count(*) from {{ ref('fact_order_items') }})
