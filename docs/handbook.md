---
title: "ShopLakehouse — Engineering Handbook"
subtitle: "Local development, validated publication, and an AWS deployment path"
author: "Abhishek Shankar"
date: "2026-11-13"
---

# Contents

1. Overview and requirements
2. Architecture and tool choices
3. Data model and business meaning
4. Local setup
5. Pipeline internals
6. dbt modeling
7. Orchestration
8. Data quality
9. Infrastructure and deployment
10. CI/CD
11. Observability
12. Security
13. Cost and scaling
14. Operations and backfill
15. Testing and benchmarks
16. Limitations and readiness
17. Glossary and command reference

# 1. Overview and requirements

An online shop stores customer/order/payment transactions separately from product enrichment and marketing feeds. ShopLakehouse creates consistent analytical tables, with evidence that rejected or incomplete runs cannot silently replace good results.

Functional requirements: simulate nine relational entities and three external feeds; load incrementally; retain raw data; validate and pseudonymize; model orders and customer history; schedule daily; publish dashboards. Non-functional requirements: configuration outside code, explicit failure states, repeatable batches, money precision, auditable lineage, isolated publication and a documented cloud path.

This is a learning/portfolio platform. Operational targets must be measured, not inferred from architecture. No production SLA, AWS acceptance, legal compliance or zero-cost guarantee is implied.

# 2. Architecture and tool choices

See [architecture](architecture.md) for Mermaid logical/physical diagrams and alternatives. Bronze is the receipt; Silver is the checked inventory; Gold is the report. Keeping the receipt makes investigation possible after transformations change.

Local development uses the same package and contracts as AWS, but different warehouse adapters. Industry teams commonly use local tests plus an isolated cloud integration environment. A local success is necessary evidence, not proof that IAM, networking and Athena will work.

# 3. Data model and business meaning

See [data dictionary](data-dictionary.md) for every configured column and model grain. Source tables are normalized to enforce ownership and avoid repeated business attributes. Gold uses a star: facts reference descriptive dimensions. A snowflake would normalize categories again; an OBT would flatten dimensions into each fact and make changing customer history harder to explain.

An order fact has one row per order. An item fact has one row per item line. Joining the two and summing order total repeats that total per item: aggregate item amounts or first return to order grain. Payment fact grain is one transaction, including refunds.

Delivered merchandise revenue is not accounting-recognized revenue and is not net cash. Shipping and tax are outside this model. Historical item prices protect past sales when the catalog price changes.

# 4. Local setup

Follow [local setup](local-setup.md). Verify Docker before debugging Python. Preserve the original source volume and adopt lesson migrations explicitly. Container service names are different from hostnames used by a terminal on the Mac.

The clean-context image builder is intentional: AppleDouble files on external drives can break Docker context checksums and Python/SQL scanners. Configuration setup preserves existing secrets.

# 5. Pipeline internals

The run ledger captures a unique run, cutoff, logical day and contract hash. Extractors read a seven-day lookback before the published watermark and stop at cutoff. A successful object write precedes the extraction ledger entry. A crash between them may leave an orphan object, but cannot advance the watermark.

Bronze holds a canonical JSON payload in Snappy Parquet plus source, batch, ingestion time and payload hash. Keeping decimals as strings in the raw JSON avoids floating-point changes. Contract drift is detected before PostgreSQL extraction. CSV headers are validated and API pages are retried with backoff.

Spark casts declared fields, adds rejection reasons and uses a deterministic window ordering. Invalid keys are not collapsed into a single null group. Duplicate rows are counted separately. Candidate snapshots merge with the previous publication; business keys retain the latest update.

Silver HMACs normalized customer name/email, drops street/postal/free-text fields, runs GX checks and writes an immutable snapshot. Bronze/quarantine still contain restricted raw identity. Metadata and row counts link the layers.

# 6. dbt modeling

Staging views expose Silver; marts implement dimensions, facts and business aggregates. The customer snapshot tracks observed updated_at changes. Type 1 overwrites an attribute; Type 2 adds validity intervals; Type 3 keeps a limited previous value. We use Type 2 for customer history and Type 1 for the current product catalog.

The item model uses PostgreSQL delete+insert or Athena merge. Runs use isolated schemas, so normal first builds are full candidate builds; incremental materialization primarily helps retries within a candidate. This is not a claim of fully incremental warehouse cost.

The snapshot is copied from the last publication before building the candidate. Facts join customer validity intervals. Unknown is explicit when an order predates the observed customer state. Snapshot history cannot invent changes that happened before collection began.

Freshness uses candidate _loaded_at, not business updated_at: a stable category is not stale simply because nobody changed it. Checks include unique/not-null keys, relationships, nonnegative money, overlapping customer intervals, order/line totals, refund limits and source totals. dbt artifacts and generated docs are retained per run.

# 7. Orchestration

| DAG | Trigger | Work |
|---|---|---|
| master_pipeline | 02:00 Asia/Kolkata | Begin → mapped ingestion → Silver → load → dbt → publish |
| ingest_bronze_daily | Manual recovery | Ingest missing entities for active run |
| transform_silver_daily | Manual recovery | Transform and load active run |
| build_gold_dbt | Manual recovery | Validate and publish active run |
| maintenance | Weekly | List obsolete schemas; no automatic deletion |

The scheduler decides which tasks can run; LocalExecutor runs them as processes in the scheduler container. XCom carries IDs/statistics, not data frames. A pool limits source/Spark concurrency; max_active_runs prevents overlapping scheduled masters. The database independently rejects a second active pipeline run.

Dataset outlets describe completed layer events. They are not a second competing coordinator. Retry delays and execution timeouts bound transient failures. Recovery uses the existing immutable run inputs. TaskFlow functions serve as the project-specific operator boundary; there is no unnecessary custom operator framework.

DAG code is packaged into immutable images. Configure alert endpoints explicitly before using failure notifications. No outbound alert has been sent by implementation tests. See the runbook for why a logical-date backfill is not source time travel.

# 8. Data quality

Validation layers have different jobs: SQL constraints prevent impossible source values; ingestion checks schema; Spark quarantines malformed fields and business-rule failures; GX validates Silver keys/nulls; dbt validates analytical relationships and amounts; reconciliation compares source/Gold totals before publication.

Quality policy defaults to zero rejected rows. Raising that tolerance is a business decision; reconciliation can still block a run if dropping an order changes totals. Count identity is extracted = accepted + rejected + duplicates. Hash checks validate object reads.

GX is used on Silver rather than duplicating the same suites at every layer. Bronze integrity and Gold dbt checks provide the other gates. This concentrates evidence where each engine is strongest.

# 9. Infrastructure and deployment

Follow [AWS deployment](aws-deployment.md). Modules group network, data services, compute/IAM/monitoring and GitHub federation. Dev/prod have separate state and CIDRs. Terraform plan describes change; apply executes it; state maps configuration to cloud resources. Native S3 locking prevents concurrent state writers.

Services default off until images and secrets exist. Bootstrap supplies schema/secret initialization; application workers run afterward. Production configuration enables stronger availability, but production readiness still requires the explicit acceptance checks in the cloud guide.

# 10. CI/CD

CI lints/types/tests Python, validates Terraform and runs the local pipeline. A dedicated image check imports Airflow DAGs. The image workflow builds ARM64, scans, then pushes immutable tags using OIDC. Cloud deployment is manual and environment-gated to prevent accidental paid changes.

Use feature branches and pull requests, require successful CI, and protect main. Configure GitHub production environment reviewers; YAML cannot create repository protection rules. Never run privileged cloud workflows for untrusted fork code.

The repository uses full dbt candidate validation. Slim CI is a later optimization requiring a trusted baseline manifest and isolated target; skipping this baseline would give misleading assurance. DAG deployment follows the application image release, rather than mutable file synchronization.

# 11. Observability

Track five data-health dimensions: freshness (when a valid version appeared), volume (count changes), quality (rejections/tests), schema (contract drift), and lineage (run/object/model identity). Logs, metrics and traces are telemetry techniques supporting those dimensions.

Local audit tables and per-run JSON/dbt artifacts answer what ran and what passed. Cloud logs emit structured error events; Terraform creates a metric filter, alarm and dashboard. Alarm notification actions are intentionally unconfigured until an operator chooses a destination. OpenTelemetry tracing and business-SLA alerting are future enhancements.

# 12. Security

Secrets stay in ignored .env locally and Secrets Manager in AWS. ECS uses role credentials, not static AWS keys. S3 public access is blocked, encrypted and TLS-only. CloudTrail captures management and lake object events. Metabase reads only Gold through a dedicated reader.

HMAC is pseudonymization, not anonymization. Rotating its key changes identifiers: version the key and rebuild/migrate affected snapshots deliberately. Erasure must cover source, Bronze, quarantine, snapshots, S3 versions and backups according to approved retention rules. There is no automated legal erasure workflow in this demo.

Before production, split runtime/migration database privileges, narrow API IAM access, verify TLS certificates and add private API TLS. Restrict network access to the UI. Scan dependencies and update pinned versions; an old pin is reproducible, not automatically safe. The pinned upstream MinIO build is for local development, and includes its AGPL license.

# 13. Cost and scaling

Use measured AWS costs; see the deployment guide's cost drivers. The infrastructure does not promise Free Tier. Continuously running Airflow and NAT dominate a tiny demonstration more than the data itself.

At 100× scale, stream extraction to multiple files, partition by business/event date where useful, compact to sensible file sizes and replace whole-frame Pandas validation with distributed checks. Use Iceberg snapshots/merge, incremental dbt models with affected-key sets, separate Spark compute and orchestrator, and workload-specific IAM roles. For near-real-time needs use transaction-log CDC and tombstones, with ordering, schema evolution and replay design.

A single huge partition causes skew; one tiny file per row causes listing/scan overhead. Benchmark partition count, skew and Athena bytes scanned before tuning.

# 14. Operations and backfill

See [runbook](runbook.md). Stop workers before abandoning an active run. Preserve original failure evidence. A normal rerun creates new run/attempt paths; it does not overwrite prior Bronze. Failed candidates remain invisible.

RPO/RTO are objectives to establish and measure. Restore source, ledger, published objects and secrets as a consistent set. Test the restored publication and a new run before restarting scheduling.

# 15. Testing and benchmarks

Unit tests cover configuration, exact decimal serialization, S3 object round trips, write failures, API auth/pagination and publication gates. Spark tests exercise latest-record selection, invalid rows and PII protection. Integration tests check source contracts, published counts, business totals and hashed identity. DAG checks import all five workflows and verify critical dependencies.

Benchmark template:

| Metric | Value to measure | Method |
|---|---|---|
| Input rows / bytes | Record actual value | Source counts / object metadata |
| First full run duration | Record actual value | Run timestamps |
| Rerun duration | Record actual value | Same dataset, new run |
| Peak memory / CPU | Record actual value | Docker stats or CloudWatch |
| Rejected / duplicate rows | Record actual value | table_runs |
| Athena scanned bytes / cost | Only after AWS execution | Query statistics and billing |
| Recovery time | Record actual value | Controlled failure drill |

Do not present synthetic order counts as real commercial impact.

# 16. Limitations and readiness

| Area | Implemented evidence | Required before production |
|---|---|---|
| Local pipeline | See progress.md for run results | Larger load and restore tests |
| AWS code | Terraform validation | Real-account integration and IAM tests |
| Database access | Local BI reader | Separate runtime/migrator roles |
| Source history | Watermarks + lookback | CDC for hard deletes and transaction order |
| Transform scale | Bounded snapshots | Distributed IO/validation |
| Publication | Atomic local views; pinned cloud schema | Consumer consistency acceptance |
| Alerts | Callback and cloud alarm | Destination and tested escalation |
| Dependencies | Pinned direct requirements | Ongoing vulnerability remediation |
| BI | Scripted local questions/dashboards | Cloud hosting and access design |

# 17. Glossary and command reference

Watermark: last successfully published extraction cutoff. Lookback: reread earlier changes to tolerate late visibility. Idempotency: rerunning has the same business effect. Grain: what one row means. SCD2: descriptive history with validity intervals. Quarantine: rejected data plus explanation. Reconciliation: independent counts/amounts agree. Candidate: isolated unpublished output. OIDC: short-lived federated identity. RPO: tolerable data loss interval. RTO: target recovery duration.

`make up` starts core services; `make migrate` applies new schema; `make generate-data` inserts synthetic data; `make run` executes/publishes; `make status` inspects; `make airflow` enables orchestration; `make metabase` starts BI; `make test` runs unit checks; `make lint typecheck` checks code; `make down` stops containers while keeping volumes.

This Markdown is suitable for a document pipeline. Render Mermaid diagrams to images before Pandoc PDF export; verify layout separately. This repository does not claim a PDF artifact was rendered.
