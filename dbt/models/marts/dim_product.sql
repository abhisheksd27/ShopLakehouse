select p.id as product_id, p.sku, p.name as product_name,
       c.name as category_name, p.price as current_catalog_price,
       a.brand, a.material, p.updated_at
from {{ ref('stg_products') }} p
join {{ ref('stg_categories') }} c on p.category_id = c.id
left join {{ ref('stg_product_api') }} a on p.id = a.id
