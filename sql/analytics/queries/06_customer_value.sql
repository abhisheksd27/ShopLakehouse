-- Observed delivered spend; this is not a predictive lifetime value.
SELECT customer_id,delivered_orders,historical_spend,first_order_date,last_order_date FROM gold.customer_ltv ORDER BY historical_spend DESC LIMIT 20;
