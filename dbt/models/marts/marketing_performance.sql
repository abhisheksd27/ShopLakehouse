select m.event_date,m.channel,m.spend,m.impressions,m.clicks,w.sessions,w.conversions,
       case when m.impressions>0 then cast(m.clicks as decimal(18,6))/m.impressions else 0 end as click_through_rate,
       case when w.sessions>0 then cast(w.conversions as decimal(18,6))/w.sessions else 0 end as conversion_rate
from {{ ref('stg_marketing') }} m
left join {{ ref('stg_web_traffic') }} w on m.event_date=w.event_date and m.channel=w.channel
