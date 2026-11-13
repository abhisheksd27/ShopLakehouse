-- Net successful cash movement and refunds by processing date; distinct from merchandise revenue.
SELECT business_date,net_cash_collected,refunded_amount FROM gold.daily_revenue ORDER BY business_date;
