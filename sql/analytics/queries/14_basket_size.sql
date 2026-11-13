-- Average units and distinct products in delivered orders.
WITH baskets AS (SELECT i.order_id,sum(i.quantity) AS units,count(DISTINCT i.product_id) AS products FROM gold.fact_order_items i JOIN gold.fact_orders o USING(order_id) WHERE o.status='delivered' GROUP BY i.order_id) SELECT round(avg(units),2) AS average_units,round(avg(products),2) AS average_products FROM baskets;
