# Portfolio and interview guide

## Resume entry

**ShopLakehouse — E-commerce analytics platform**
Python, PostgreSQL, PySpark, dbt, Airflow, MinIO/S3, Terraform, Athena/Glue, Metabase.

Use only measurements you can reproduce:

- Integrated **12 configured feeds** across PostgreSQL, API and CSV into a layered analytics pipeline.
- Modeled **nine relational source entities** and **ten published business marts**, with observed customer SCD2 history.
- Processed **[replace: measured row count]** in **[replace: measured duration]**, preserving exact decimal totals.
- Demonstrated failure isolation across **[replace: number of executed recovery scenarios]**; record the evidence before claiming this result.
- Built **three local dashboard designs** and AWS infrastructure code; state “deployed to AWS” only after a real deployment and acceptance test.

Do not replace bracketed measurements with estimates or describe synthetic sales as business revenue you generated.

## LinkedIn draft

I’m building ShopLakehouse, a local-first e-commerce data engineering project.

The flow combines PostgreSQL transactions, a product API and daily CSV feeds. Python preserves raw Parquet, PySpark validates and protects sensitive fields, and dbt builds facts, dimensions and customer history for Metabase.

The most useful lesson so far: a pipeline is not finished when transformations run. Publication, watermarks, reconciliation and recovery need to agree—otherwise a retry can quietly damage reporting.

I’ve also prepared Terraform for an AWS path using S3, Glue/Athena, RDS and ECS. I’m keeping local verification and cloud deployment claims separate.

Next I’m documenting the measured results and the tradeoffs behind the implementation.

#DataEngineering #Python #SQL #PySpark #dbt #Airflow #AWS

## Thirty-second pitch

ShopLakehouse combines a shop’s database, product API and marketing files into reliable daily reporting. I built raw, clean and business layers with Python, Spark and dbt. Its key design is publication safety: a failed quality check keeps the previous report and its watermarks intact. The project runs locally and includes an AWS deployment path that must be validated separately.

## Two-minute pitch

The business problem is fragmented reporting. Orders and payments live in PostgreSQL, product attributes come from an API, and marketing teams deliver CSV files. I defined the grain of orders, items and payment transactions before writing revenue metrics.

The pipeline preserves raw inputs, checks schema, deduplicates by business key, validates types and rules, and pseudonymizes customer identity. dbt builds the analytical layer and observed customer history. Airflow coordinates bounded parallel ingestion and serial validation/publication.

I chose isolated candidate schemas so partially successful models never become the current report. In PostgreSQL the Gold views and checkpoints change together. For Athena I use a committed pointer to a concrete schema instead of claiming multi-view atomicity.

The main tradeoff is simplicity versus scale: current snapshots and GX checks fit a portfolio dataset. At larger scale I would use distributed writes, incremental affected-key processing and CDC for deletes. My evidence is the tests and runs in the progress log; the cloud implementation is not a production deployment claim.

## Thirty project-specific questions

### 1. Why three layers?

Bronze preserves source evidence, Silver enforces typed clean records, and Gold defines business metrics. Each has a different recovery and consumer contract.

### 2. When does the watermark advance?

Only when a complete validated version publishes. An object write alone does not authorize a checkpoint change.

### 3. What happens after an S3 write but before the ledger commit?

The object may be orphaned. A retry uses a new attempt path; no checkpoint moved, so data is re-extracted safely.

### 4. Why a lookback window?

updated_at may become visible after an earlier extraction. Rereading seven days and deduplicating tolerates bounded lateness; CDC is required for stronger guarantees.

### 5. Do you capture deletes?

No. The current extractor handles inserts/updates. Hard deletes require tombstones or transaction-log CDC and propagation through snapshots.

### 6. What is idempotent here?

Generator batch keys prevent duplicate source orders; latest-key merge prevents duplicate Silver rows; failed candidates do not replace Gold. Runs still create distinct audit versions.

### 7. How is deduplication deterministic?

Partition by business key, order by updated_at, ingestion timestamp and record hash. Invalid keys receive distinct groups so rejected rows remain countable.

### 8. How is money preserved?

PostgreSQL numeric and Spark decimal(18,2), canonical raw JSON strings and exact reconciliation avoid floating-point summation error.

### 9. How do you protect PII?

Keyed HMAC of normalized names/emails and removal of address/free-text fields in Silver. Raw layers remain sensitive and require separate access/retention.

### 10. Is hashing anonymization?

No. Stable pseudonyms can still link a person's records. Erasure and access controls must include raw data, historical versions and backups.

### 11. What does an order row mean?

One order. Joining items increases row count; summing order totals after that join overcounts. Use item line amounts at item grain.

### 12. Why separate payments from orders?

A purchase can have charges, pending attempts and refunds. Successful signed cash movement differs from delivered merchandise value.

### 13. How does SCD2 work?

dbt snapshots observe changed customer updated_at, close prior validity and add a version. Prior history is copied into each isolated candidate.

### 14. Why an unknown dimension row?

An order may precede the first observed customer version. Assigning current attributes retrospectively would invent history.

### 15. Is the dbt pipeline fully incremental?

No. Candidate isolation builds fresh marts for ordinary runs; the item incremental strategy supports retries. This trades compute for simple publication safety.

### 16. How is Gold published atomically?

Local stable views and checkpoints change in one PostgreSQL transaction. AWS consumers instead resolve and pin a versioned schema from the control pointer.

### 17. Why not replace every Athena view?

Those changes do not form one transaction. A consumer could see mixed versions. A pinned release schema makes the version boundary explicit.

### 18. What happens when dbt fails?

The validation flag stays false, publication fails, checkpoints remain unchanged, and the previous Gold version remains available.

### 19. What does freshness measure?

Candidate load time, not the last business edit. Otherwise an unchanged dimension would be incorrectly labeled stale.

### 20. Why both GX and dbt tests?

GX checks typed Silver snapshots; dbt checks analytical relationships and money reconciliation. Source constraints and schema checks cover earlier boundaries.

### 21. What are Airflow scheduler and executor?

The scheduler evaluates dependencies and schedules tasks; LocalExecutor launches task processes. A shared pool limits expensive concurrent work.

### 22. What goes into XCom?

Run IDs and small statistics only. Parquet objects hold row data; large XComs would overload the metadata database.

### 23. How do retries differ from reruns?

Task retries operate on an active run and immutable inputs. A new run gets a new cutoff and candidate. Source corrections need a new extraction/run.

### 24. Can a 30-day backfill recreate history?

Only if historical input versions were retained. Repeating logical dates against current PostgreSQL is not time travel; the runbook explains CSV correction versus historical replay.

### 25. Why Athena rather than Redshift?

The demonstration benefits from querying S3 without keeping a warehouse running. Sustained BI concurrency and tighter warehouse SLAs may favor Redshift.

### 26. What does Terraform state do?

It maps declared resources to their cloud identities. Encrypted versioned remote state and locking protect coordinated updates; state is sensitive.

### 27. Why OIDC?

GitHub obtains short-lived role credentials scoped to repository/environment. Long-lived AWS access keys are unnecessary.

### 28. What limits scale today?

Extractors accumulate batches, snapshots use one file and GX converts a whole snapshot to Pandas. Distributed IO, partitioning and incremental validation are required at larger scale.

### 29. How would you prove disaster recovery?

Restore source, control state, published objects and secrets in isolation; reconcile data and execute a new run. Measure loss interval and restoration time.

### 30. What did the runtime checks teach you?

Contracts, container filesystems and orchestrator reserved names can fail despite unit tests. Report only the verification recorded in progress.md and distinguish prepared cloud code from deployed behavior.

## Ten system-design follow-ups

### 1. One hundred times more orders

Chunk extraction, distributed Parquet writes, partition pruning, compaction, incremental affected-key transforms and separate Spark compute. Benchmark before choosing partition counts.

### 2. One-minute latency

Add CDC, ordered event keys, tombstones, schema evolution and checkpointed streaming; retain replayable events and reconcile against source snapshots.

### 3. Multiple merchants

Add tenant keys to every business identity, enforce tenant authorization and choose physical isolation for strict regulatory boundaries.

### 4. Cross-region disaster

Replicate approved object data and backup metadata/keys; design promotion and pointer recovery, then drill both failover and failback.

### 5. Schema evolution without outages

Classify additive versus breaking changes, version contracts, dual-read/write during migration and gate consumer compatibility.

### 6. GDPR-style erasure request

Locate subject mappings, remove or irreversibly de-identify all required versions, handle backups under approved retention, and audit completion without exposing the erased identity.

### 7. High BI concurrency

Benchmark Athena concurrency/cost; consider cached extracts or a serving warehouse. Keep semantic definitions and publication version consistent.

### 8. Late corrections after a month

Use explicit full/key-scoped backfills with manifests, recompute affected facts/aggregates and validate history rather than silently expanding every daily scan.

### 9. Compromised API token

Rotate the secret, revoke/redeploy API and workers, inspect access logs, limit token scope and avoid including credentials in exception traces.

### 10. Publication interrupted between cloud manifest and DB commit

The unreferenced manifest is not public. Retry or abandon; consumers continue using the last committed pointer and its immutable schema.
