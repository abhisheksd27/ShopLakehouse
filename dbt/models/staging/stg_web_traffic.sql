select * from {{ source('silver', 'web_traffic') }}
