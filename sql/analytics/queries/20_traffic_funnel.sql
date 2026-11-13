-- Channel funnel totals; simulated aggregate feeds are not user-level attribution.
SELECT channel,sum(impressions) AS impressions,sum(clicks) AS clicks,sum(sessions) AS sessions,sum(conversions) AS conversions,round(100.0*sum(conversions)/nullif(sum(sessions),0),2) AS conversion_percent FROM gold.marketing_performance GROUP BY channel ORDER BY conversions DESC;
