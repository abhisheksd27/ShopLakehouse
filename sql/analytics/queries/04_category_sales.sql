-- Delivered order items grouped by product category.
SELECT p.category_name, sum(i.line_amount) AS revenue_inr FROM gold.fact_order_items i JOIN gold.fact_orders o USING(order_id) JOIN gold.dim_product p USING(product_id) WHERE o.status='delivered' GROUP BY p.category_name ORDER BY revenue_inr DESC;
