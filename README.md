# ShopLakehouse

A local-first e-commerce analytics platform built with Python,
PostgreSQL, MinIO, PySpark, dbt, Airflow, and Metabase, with a
planned deployment to AWS.

## Business problem

An online retailer has transactional data in PostgreSQL,
additional product information behind an API, and marketing
data in CSV files.

ShopLakehouse will combine these sources into reliable
reporting tables for sales, products, and customer behavior.

## Current status

Foundation and documentation are being established.

The data pipeline, dashboards, and AWS infrastructure are
planned and have not yet been implemented.

## Planned local data flow

1. Generate synthetic transactional, API, and CSV data.
2. Extract source records with Python.
3. Preserve raw records as Bronze Parquet files in MinIO.
4. Clean and validate records with PySpark.
5. Store accepted records in Silver and rejected records in quarantine.
6. Load validated Silver records into analytics PostgreSQL.
7. Build and test Gold business models with dbt.
8. Publish validated results for Metabase dashboards.
9. Automate the pipeline with Airflow.

## Planned analytics

- Daily revenue and average order value.
- Product and category performance.
- Customer purchase history and repeat purchase rate.
- Cohort retention.
- Cancellation and refund trends.
- Marketing and website traffic trends.

## Planned AWS deployment

- S3 for object storage.
- Glue Data Catalog and Athena for lakehouse analytics.
- RDS PostgreSQL for source data.
- ECR and ECS Fargate for containers.
- IAM, KMS, and Secrets Manager for access and secrets.
- CloudWatch and CloudTrail for monitoring and auditing.
- Terraform for infrastructure.
- GitHub Actions for CI/CD.

Cloud-specific behavior will be tested separately from the local setup.

## Documentation

- [Architecture](docs/architecture.md)
- [Build progress](docs/progress.md)

## Development approach

Build a small working pipeline first, verify its business results,
then expand it.

Each implementation step includes testing and a documentation update.