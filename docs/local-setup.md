# Local setup

## 1. Configuration and containers

From the repository root, run the README commands. `scripts/setup_env.py` fills missing configuration with random secrets while retaining existing nonempty values. It prints no secret values. Keep `.env` out of Git.

`make up` builds the application and official MinIO source in a clean temporary context, starts core services, checks their health and creates the local bucket. The first build downloads Python, Java and Go dependencies and can take several minutes.

| Service | Local endpoint | Login/configuration |
|---|---|---|
| Source PostgreSQL | localhost:5433 | SOURCE_DB_USER / SOURCE_DB_PASSWORD |
| Analytics PostgreSQL | localhost:5434 | ANALYTICS_DB_USER / ANALYTICS_DB_PASSWORD |
| MinIO S3 / console | localhost:9000 / http://localhost:9001 | MINIO_ROOT_USER / MINIO_ROOT_PASSWORD |
| Product API | http://localhost:8000/docs | API_TOKEN bearer token |
| Airflow (optional) | http://localhost:8080 | admin / AIRFLOW_ADMIN_PASSWORD |
| Metabase (optional) | http://localhost:3000 | METABASE_ADMIN_EMAIL / METABASE_ADMIN_PASSWORD |

All published ports bind to loopback. Containers use service names and internal ports. Optional metadata databases are not published. Do not paste passwords into Git, screenshots or tickets.

## 2. Schema and data

```sh
make migrate
make generate-data DAY=2026-11-13 ORDERS=100
make run DAY=2026-11-13
make test-integration
```

Existing lesson databases need explicit `migrate --adopt-legacy` once. Adoption checks tables and catalog corrections and records their checksums, avoiding re-execution of earlier lesson SQL. The generator adds synthetic rows without truncating tables. Initial mode uses one batch per seed; daily mode includes date and seed. A replay must use the original date/count.

Initial mode creates customers, categories, products, addresses, orders/items, payments/refunds, shipments, reviews and 30 daily CSV files per feed. Daily mode modifies selected customers/products and adds orders:
```sh
docker compose run --rm pipeline generate --mode daily --day 2026-11-14 --orders 20
docker compose run --rm pipeline run --day 2026-11-14
```

Use actual dates when working later. A logical day labels a run; it does not reconstruct historical database state.

## 3. BI

```sh
make metabase
.venv/bin/python scripts/setup_metabase.py
```

The script creates a Gold-only `shop_bi` reader, initial Metabase admin if needed, database connection, saved questions and dashboards. It can be rerun without duplicating managed questions. Admin credentials are read from the private environment. Dashboard IDs are written to `artifacts/metabase.json`. It sends no emails and creates no public links.

## 4. Scheduling

```sh
make airflow
docker compose exec airflow-scheduler airflow dags list-import-errors
docker compose exec airflow-scheduler airflow dags unpause master_pipeline
docker compose exec airflow-scheduler airflow dags trigger master_pipeline
```

DAGs start paused. The scheduled master performs one run at a time; its ingestion tasks share a two-slot pool. Recovery DAGs require an active run ID. They do not create a new source snapshot.

## 5. Checks and shutdown

```sh
make lint typecheck test
make test-spark
make test-integration
docker compose ps
docker compose down
```

Expected: healthy core containers, published run, matching source/Gold order count and delivered revenue, no rejected records in a clean run. Shutdown retains named volumes. Local generated data, reports and credentials remain ignored by Git.

Troubleshooting: start Docker Desktop for socket errors; use the build helper for external-drive metadata errors; stop optional services for memory pressure. Java is included in the application image; host Spark tests also need a compatible JVM.
