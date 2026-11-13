-- Share of observed buyers with at least two delivered orders.
SELECT count(*) AS buyers,count(*) FILTER (WHERE delivered_orders>1) AS repeat_buyers,round(100.0*count(*) FILTER (WHERE delivered_orders>1)/nullif(count(*),0),2) AS repeat_percent FROM gold.customer_ltv;
