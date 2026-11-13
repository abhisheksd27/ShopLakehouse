-- Top ten products by delivered merchandise revenue.
SELECT p.product_name, sum(i.line_amount) AS revenue_inr FROM gold.fact_order_items i JOIN gold.fact_orders o USING(order_id) JOIN gold.dim_product p USING(product_id) WHERE o.status='delivered' GROUP BY p.product_id,p.product_name ORDER BY revenue_inr DESC LIMIT 10;
