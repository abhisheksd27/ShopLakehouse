-- Discounts are per line, not per unit.
SELECT p.category_name,sum(i.quantity*i.unit_price) AS gross_inr,sum(i.discount_amount) AS discounts_inr,sum(i.line_amount) AS net_inr FROM gold.fact_order_items i JOIN gold.fact_orders o USING(order_id) JOIN gold.dim_product p USING(product_id) WHERE o.status='delivered' GROUP BY p.category_name ORDER BY discounts_inr DESC;
