select calendar_date as date_day,
       extract(year from calendar_date) as year_number,
       extract(month from calendar_date) as month_number,
       extract(day from calendar_date) as day_number
from {{ ref('calendar') }}
