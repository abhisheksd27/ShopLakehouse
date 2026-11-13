-- Successful charges and refunds by payment method.
SELECT payment_method,sum(net_cash) AS net_cash_inr FROM gold.fact_payments GROUP BY payment_method ORDER BY net_cash_inr DESC;
