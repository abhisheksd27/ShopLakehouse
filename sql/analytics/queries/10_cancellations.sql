-- Cancelled orders divided by all orders by placement date.
SELECT order_date,count(*) AS all_orders,count(*) FILTER (WHERE status='cancelled') AS cancelled_orders,round(100.0*count(*) FILTER (WHERE status='cancelled')/nullif(count(*),0),2) AS cancellation_percent FROM gold.fact_orders GROUP BY order_date ORDER BY order_date;
