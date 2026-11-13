-- Monthly active buyers divided by original cohort buyers.
SELECT cohort_month,months_since_first,active_customers,cohort_size,round(retention_rate*100,2) AS retention_percent FROM gold.cohort_retention ORDER BY cohort_month,months_since_first;
