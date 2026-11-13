-- Delivered merchandise revenue, orders, and weighted average order value.
SELECT sum(delivered_merchandise_revenue) AS revenue_inr, sum(delivered_orders) AS orders, round(sum(delivered_merchandise_revenue)/nullif(sum(delivered_orders),0),2) AS average_order_value_inr FROM gold.daily_revenue;
