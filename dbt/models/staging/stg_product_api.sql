select * from {{ source('silver', 'product_api') }}
