select dbt_scd_id as customer_key, id as customer_id, name as name_hash,
       email as email_hash, city, country, dbt_valid_from as valid_from,
       dbt_valid_to as valid_to
from {{ ref('customer_history') }}
union all
select 'unknown', cast(-1 as bigint), 'unknown', 'unknown',
       'unknown', 'ZZ', cast('1900-01-01' as timestamp), cast(null as timestamp)
