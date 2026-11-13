# ShopLakehouse

A local-first e-commerce analytics platform: PostgreSQL, REST and CSV sources → immutable Bronze Parquet → validated PySpark Silver → dbt Gold → Metabase.

The repository includes the local implementation, Airflow orchestration, tests and AWS deployment code. See [progress](docs/progress.md) for measured verification; AWS infrastructure has **not** been deployed. This is a bounded portfolio implementation, not a production certification.

## Start locally

Requires Docker Desktop, Python 3.11 and approximately 8 GB Docker memory for the core stack. Run optional Airflow and BI services separately if memory is limited.

```sh
python3.11 -m venv .venv
.venv/bin/python -m pip install -e '.[dev]'
.venv/bin/python scripts/setup_env.py
make up
make migrate
make generate-data DAY=2026-11-13 ORDERS=100
make run DAY=2026-11-13
make status
```

For the existing lesson database, use `docker compose run --rm pipeline migrate --adopt-legacy` once instead of `make migrate`. Checksums prevent silently changing applied migrations. Never run `docker compose down -v` unless deliberately deleting local data.

`make up` builds MinIO from a pinned official source tag because its registry images were unavailable during verification. The clean build helper also excludes macOS external-drive metadata and secrets.

## Reliability

- A run writes immutable objects and isolated candidate schemas.
- Silver checks account for accepted, rejected and duplicate rows.
- HMAC protects customer identity; street addresses and review free text are removed from Silver.
- dbt tests, freshness checks and source-to-Gold totals gate publication.
- PostgreSQL swaps Gold views and advances watermarks in one transaction.
- Failed runs retain the previous publication. Repeating generation for the same recorded batch does not add duplicate orders.

## Services and documentation

`make airflow` enables the daily DAG at 02:00 Asia/Kolkata. `make metabase` starts BI; then run `.venv/bin/python scripts/setup_metabase.py` after the first successful pipeline.

| Document | Purpose |
|---|---|
| [Project document](docs/project-document.md) | Scope, architecture, data model and verified results |
| [Execution steps](docs/execution-steps.md) | Numbered instructions for a fresh setup, resume and daily operation |
| [Local setup](docs/local-setup.md) | Commands, ports, credentials and verification |
| [Architecture](docs/architecture.md) | Data flow and design decisions |
| [Data dictionary](docs/data-dictionary.md) | Contracts, keys, types and model grains |
| [Operations runbook](docs/runbook.md) | Failures, replay, backfill and recovery |
| [AWS deployment](docs/aws-deployment.md) | Reviewed deployment and teardown |
| [Project handbook](docs/handbook.md) | Design explanations, security and scaling |
| [Portfolio and interview guide](docs/portfolio.md) | Honest project presentation and questions |
| [Progress](docs/progress.md) | What has actually been checked |

## Repository map

```text
src/shoplakehouse/    API, generator, ingestion, Silver, publication, CLI
sql/source/          Ordered, checksummed source migrations
sql/analytics/       Control ledger and business queries
config/              Source contracts and saved dashboard definitions
dbt/                 Staging, marts, snapshots, tests, macros, calendar seed
dags/                Scheduled master and manual recovery DAGs
docker/              Airflow and MinIO images
scripts/             Setup, safe image builds, BI and cloud operations
infra/               Terraform bootstrap, dev/prod and shared modules
tests/               Unit, Spark, DAG and integration checks
docs/                Architecture, instructions, runbooks and evidence
.github/workflows/   Validation, image scan/push and reviewed deployment
```

Run `make test`, `make lint`, `make typecheck`, `make test-spark` (Java required), and `make test-integration` after publication. Money is INR decimal; reporting dates use Asia/Kolkata. Merchandise revenue and payment cash flow are separate measures.
