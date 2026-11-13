# ShopLakehouse — Execution Steps

**Date:** 13 November 2026
**Run commands from the repository root.** Use section A for this already configured
workspace, or section B for a fresh clone. Do not repeat initial data generation
with a new date against an existing initial batch.

## A. Resume the existing project on this Mac

### A1. Open the project and start Docker

```sh
cd "/Volumes/Abhishek/Data Engineering project/SHOPLAKEHOUSE"
source .venv/bin/activate
docker desktop start
docker info
```

If `docker desktop start` is unavailable, open Docker Desktop normally. Continue
when `docker info` reports the server. Python should be 3.11 and use this project's
virtual environment.

### A2. Start the core services and check the existing publication

```sh
docker compose up -d --no-build --wait source-postgres analytics-postgres minio product-api
make status
```

Expected: healthy core services and a previously published run. Existing named
volumes retain the 120-order demonstration dataset. No data insertion is needed
to inspect or rerun this project.

If an image is missing or source code changed, run `make up` to rebuild images
and initialize the bucket. Run `make migrate` when new migrations are added.

### A3. Execute a new pipeline run over the existing data

```sh
make run DAY=$(date +%F)
make status
make test-integration
```

Expected: a new published run and passing integration checks. With unchanged
source data, business counts and amounts remain unchanged. Do not start a manual
run while Airflow already owns an active pipeline run.

### A4. Open the reporting services

```sh
make metabase
.venv/bin/python scripts/setup_metabase.py
make airflow
```

Open Metabase at <http://localhost:3000> and Airflow at <http://localhost:8080>.
The Metabase setup script prints dashboard links and can be rerun without
duplicating managed questions. Credentials are in the private `.env`; consult
the credential-variable table in section D without copying secrets into logs.

## B. Fresh installation

### B1. Clone and enter the repository

```sh
git clone https://github.com/abhisheksd27/ShopLakehouse.git
cd ShopLakehouse
```

Prerequisites: Git, Docker with Compose, Python 3.11 and `make`. Allow roughly
8 GB Docker memory for the core setup; optional Airflow/BI increase usage. Host
Spark tests need a compatible JVM; Java 17 is included in the application image.

### B2. Create the environment and local configuration

```sh
python3.11 -m venv .venv
source .venv/bin/activate
python -m pip install -e '.[dev]'
python scripts/setup_env.py
python --version
python -c "import sys; print(sys.executable)"
```

Expected: Python 3.11 from `.venv`, and a configuration-ready message. Setup
generates missing local secrets and preserves existing nonempty values.

### B3. Build and start the core services

```sh
make up
docker compose ps
```

This builds the application and pinned official MinIO source, starts two
PostgreSQL services, MinIO and the API, waits for health checks and creates the
local lake bucket. The first build takes longer because it downloads dependencies.
Use the provided build helper on external drives to exclude macOS metadata.

### B4. Apply the source and control schema

```sh
make migrate
```

Expected: `Migrations applied`. For a legacy lesson database with migrations
001–004 installed but no migration ledger, use this command **once** instead:

```sh
docker compose run --rm pipeline migrate --adopt-legacy
```

Do not rerun the old SQL manually. Adoption validates the known schema and records
checksums; normal future migration commands apply only new migrations.

### B5. Generate initial data once

```sh
make generate-data DAY=2026-11-13 ORDERS=100
```

The fixed date reproduces the documented initial sample. On a genuinely new
installation you may choose a different date, then retain it for replays.
Expected first result: `orders_inserted: 100`, `replayed: false`.
Repeating the exact batch reports zero new orders and `replayed: true`.

Initial generation also creates 30 days of marketing/traffic CSVs. It does not
truncate existing database tables. The initial batch is keyed by seed; changing
its original date/count is rejected rather than silently duplicating it.

### B6. Execute and verify the pipeline

```sh
make run DAY=2026-11-13
make status
make test-integration
```

Expected: a JSON result with `status: published`; dbt reports no failed tests;
integration checks pass. Reports appear under `artifacts/<run-id>/dbt/` and in
lake audit objects. The published dataset is available through `gold` views.

### B7. Create dashboards

```sh
make metabase
python scripts/setup_metabase.py
```

Expected: Executive, Sales and Customer dashboard URLs, plus 24 saved questions.
The setup creates a Gold-only reader and configures the Metabase connection.
Dashboard IDs can differ across fresh installations; use the printed URLs.

## C. Daily use and orchestration

### C1. Add a daily simulation batch when you want new source data

```sh
docker compose run --rm pipeline generate --mode daily --day 2026-11-14 --orders 20
make run DAY=2026-11-14
```

Choose the intended simulation date. An exact daily replay adds no duplicate
orders. Daily mode also updates a customer and product so history and incremental
behavior can be observed. Airflow runs ingestion/transformation; it does **not**
automatically generate new business data.

### C2. Validate Airflow without enabling recurring runs

```sh
make airflow
docker compose exec airflow-scheduler airflow dags list-import-errors
docker compose exec airflow-scheduler airflow dags test master_pipeline 2026-11-14
```

Use a new test logical date for a new test run. Expected: no import errors and a
successful master DAG through `publish`. Only one pipeline may be active.

### C3. Enable or pause the daily schedule

```sh
docker compose exec airflow-scheduler airflow dags unpause master_pipeline
```

The schedule is 02:00 Asia/Kolkata, with catchup disabled. Unpausing can make the
latest eligible scheduled interval run immediately. Leave recovery DAGs paused
unless operating a known active run. To stop future scheduled runs:

```sh
docker compose exec airflow-scheduler airflow dags pause master_pipeline
```

Pausing does not cancel tasks that are already running.

## D. Service addresses and credentials

| Service | Address | Credential variables in `.env` |
|---|---|---|
| Source PostgreSQL | localhost:5433 | SOURCE_DB_USER, SOURCE_DB_PASSWORD, SOURCE_DB_NAME |
| Analytics PostgreSQL | localhost:5434 | ANALYTICS_DB_USER, ANALYTICS_DB_PASSWORD, ANALYTICS_DB_NAME |
| MinIO console | http://localhost:9001 | MINIO_ROOT_USER, MINIO_ROOT_PASSWORD |
| Product API documentation | http://localhost:8000/docs | API_TOKEN for product requests |
| Airflow | http://localhost:8080 | Username admin; AIRFLOW_ADMIN_PASSWORD |
| Metabase | http://localhost:3000 | METABASE_ADMIN_EMAIL, METABASE_ADMIN_PASSWORD |

Published ports bind only to loopback. Never commit `.env`, generated records,
Terraform state or credentials.

## E. Testing and quality recovery

```sh
make lint typecheck test
make test-spark
make test-integration
```

Spark host tests require Java and permission to bind local sockets. The host DAG
test skips when Airflow is absent; use the packaged check instead:

```sh
docker run --rm --entrypoint python shoplakehouse-airflow:dev /opt/shoplakehouse/scripts/check_dags.py
```

After a successful synthetic publication, the controlled recovery exercise is:

```sh
python scripts/verify_recovery.py
```

It verifies unchanged totals on rerun, temporarily injects bad inputs, confirms
the previous publication/checkpoints survive, restores clean CSVs and runs recovery.
It writes a report under `artifacts/recovery-<timestamp>/`. Keep Airflow paused
and avoid concurrent source changes during this exercise.

## F. Shutdown and next startup

```sh
docker compose --profile orchestration --profile bi down
```

Named volumes remain intact. Do not add `-v` unless intentionally deleting all
project database/object-store data. Next time, follow section A. Initial generation
and legacy adoption are not daily startup steps.

## G. Common errors

| Error | Next action |
|---|---|
| Cannot connect to Docker daemon | Start Docker Desktop and verify `docker info` |
| Missing local image | Run `make up`; use `make airflow` for its image |
| Existing lesson tables | Use explicit one-time legacy adoption in B4 |
| Batch generated with different parameters | Replay its original date/count; use daily mode for a new day |
| Active pipeline run exists | Inspect status/workers; do not launch a second run |
| DataQualityError | Inspect quarantine and audit; repair inputs and start a new run |
| dbt error | Inspect `artifacts/<run-id>/dbt/<command-attempt>/logs/` |
| Memory pressure | Stop optional services during Spark processing |
| API unauthorized | Ensure API and worker use the same API_TOKEN |

For stale-run handling and backfill semantics, follow [Operations runbook](runbook.md).

## H. AWS execution is a separate phase

Follow [AWS deployment](aws-deployment.md) only after reviewing account, region,
credentials, costs and the Terraform plan. Static validation can be run without
provisioning resources:

```sh
terraform fmt -check -recursive infra
terraform -chdir=infra/environments/dev init -backend=false
terraform -chdir=infra/environments/dev validate
```

Do not treat successful validation as a completed AWS deployment. This project's
verified results are local; cloud execution and production acceptance remain pending.
