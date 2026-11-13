-- Cumulative observed spend share by customer rank.
SELECT customer_id,historical_spend,round(100.0*sum(historical_spend) OVER (ORDER BY historical_spend DESC,customer_id ROWS UNBOUNDED PRECEDING)/nullif(sum(historical_spend) OVER (),0),2) AS cumulative_percent FROM gold.customer_ltv ORDER BY historical_spend DESC,customer_id;
