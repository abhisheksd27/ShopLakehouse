-- Delivered revenue by observed historical city; unknown captures pre-observation orders.
SELECT c.city,sum(o.total_amount) AS revenue_inr FROM gold.fact_orders o JOIN gold.dim_customer c USING(customer_key) WHERE o.status='delivered' GROUP BY c.city ORDER BY revenue_inr DESC;
