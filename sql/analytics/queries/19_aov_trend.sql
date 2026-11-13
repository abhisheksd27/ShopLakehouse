-- Daily delivered merchandise revenue per delivered order.
SELECT business_date,average_order_value FROM gold.daily_revenue WHERE delivered_orders>0 ORDER BY business_date;
