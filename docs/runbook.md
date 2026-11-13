# Operations and incident runbook

## Daily procedure

Check `shoplakehouse status`, latest publication, freshness and the run's reconciliation JSON. Airflow's green task status alone is insufficient: a run must reach `published`. Inspect `control.table_runs` for extraction, acceptance, rejection and duplicate accounting. Logs contain run IDs and error types; raw records remain restricted in Bronze/quarantine.

## Failure response

| Symptom | Diagnose | Recovery |
|---|---|---|
| Docker daemon unavailable | Docker Desktop status | Start Docker; rerun health checks |
| Connection refused | Service health, hostname and port | Repair configuration, retry |
| API 401 | API_TOKEN consistent across API and worker | Correct secret, restart affected service |
| API 429/500 | Rate/fault configuration | Backoff already retries; reduce concurrency |
| Schema drift | Source columns versus config/tables.yml | Review migration/contract together, start new run |
| Rejected records | Quarantine path and reject_reason | Correct input; retain evidence; start new run |
| dbt failure | artifacts/<run>/dbt/<command-attempt>/logs and run_results.json | Correct SQL/data; rerun validation |
| Reconciliation mismatch | Source concurrent updates, item totals, refunds | Pause simulation/writers; investigate; new run |
| Active run blocks next run | control.runs and Airflow workers | Stop old workers, then abandon stale run |
| Memory pressure | Docker allocation and optional services | Stop BI/Airflow during Spark; reduce data |
| External-drive metadata | Binary ._ files | Use clean image helper; source scanners ignore ._ |

Never advance a checkpoint manually to suppress an error. A failing run retains the previous Gold version. A source correction must be re-extracted into a **new** run because old Bronze is immutable.

## Stage recovery

For a transient failure while a run is still active:
```sh
shoplakehouse stage active
shoplakehouse stage silver --run-id RUN_ID
shoplakehouse stage load --run-id RUN_ID
shoplakehouse stage gold --run-id RUN_ID
shoplakehouse stage publish --run-id RUN_ID
```

The standalone `run` command marks failed runs terminal. Airflow callbacks do likewise after exhausted retries. For these, repair the cause and start a new run. If a process died leaving status running, stop all its workers before `shoplakehouse abandon RUN_ID`. Recovery DAGs accept an active `run_id` in configuration; do not run them concurrently with the master.

## Reruns and backfill

`shoplakehouse run --day YYYY-MM-DD --full` bypasses extraction watermarks. It is a full current-state scan, not historical time travel. Daily CSV files are reread to pick up late corrections. Repeated source generation for the same batch key skips already committed inserts.

A 30-day CSV backfill: provide/correct all 30 files in each entity directory, then run one full pipeline. The generator's initial mode already produces 30 dates. Replaying 30 logical dates against current PostgreSQL will not recreate past snapshots. For historical reconstruction, retain dated Bronze and design a dedicated replay run with the original source-count manifest; do not edit the live control ledger.

## Deliberate quality exercise

```sh
shoplakehouse generate --day YYYY-MM-DD --inject-quality
INJECT_DQ_FIXTURES=true shoplakehouse run --day YYYY-MM-DD
```

Run from the host virtualenv with Java available, or pass the environment flag into the pipeline container. Fault fixtures bypass source constraints only in the ingestion simulation. Strict rejection threshold is zero. Expect a failed run, quarantine evidence and an unchanged publication/checkpoint. Regenerate the same batch **without** injection to restore CSV files; disable the flag for clean ingestion. Source constraints stay enabled.

## Retention and disaster recovery

`shoplakehouse maintenance --days 14` is a dry run. `--apply` deletes old local candidate schemas, excluding the current publication and active runs. It does not delete lake objects or AWS catalog versions. Establish retention with business/legal requirements before automation.

Back up source and control PostgreSQL together with the published object versions and HMAC key. On restore: stop scheduling, restore databases and objects, resolve the publication, verify checksums and totals, then resume. RPO equals the chosen backup interval; RTO must be measured in a restore drill. S3 versioning alone is not a tested backup strategy. Loss of the HMAC key changes identity hashes and SCD history.

## End-of-day Git review

```sh
git status --short
git diff --check
git add README.md .gitignore .env.example .dockerignore .pre-commit-config.yaml pyproject.toml Dockerfile Makefile docker-compose.yml src sql config dbt dags docker scripts tests infra docs .github
git diff --cached --stat
git diff --cached --check
git commit -m "feat: implement ShopLakehouse pipeline, orchestration, analytics and AWS infrastructure"
git push origin main
```

Review the staged files first. Never stage .env, raw data, Terraform state or generated reports containing records. Commands are supplied for the user; no commit or push is performed automatically.
