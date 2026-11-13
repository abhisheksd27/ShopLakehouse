-- Traffic and ad metrics by channel; no unmeasured attribution or ROI is claimed.
SELECT channel,sum(spend) AS spend_inr,sum(impressions) AS impressions,sum(clicks) AS clicks,sum(sessions) AS sessions,sum(conversions) AS conversions,round(100.0*sum(clicks)/nullif(sum(impressions),0),2) AS ctr_percent FROM gold.marketing_performance GROUP BY channel ORDER BY spend_inr DESC;
