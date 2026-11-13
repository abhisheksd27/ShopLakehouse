-- Cumulative delivered revenue over calendar dates.
SELECT business_date,delivered_merchandise_revenue,sum(delivered_merchandise_revenue) OVER (ORDER BY business_date ROWS UNBOUNDED PRECEDING) AS cumulative_revenue FROM gold.daily_revenue ORDER BY business_date;
