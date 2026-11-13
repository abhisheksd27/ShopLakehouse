CREATE SCHEMA IF NOT EXISTS control;
CREATE TABLE IF NOT EXISTS control.runs (
    run_id text PRIMARY KEY,
    logical_date date NOT NULL,
    started_at timestamptz NOT NULL DEFAULT now(),
    cutoff timestamptz NOT NULL,
    status text NOT NULL CHECK(status IN ('running','failed','published')),
    finished_at timestamptz,
    error_type text,
    candidate_schema text NOT NULL,
    source_revenue numeric(24,2),
    source_orders bigint,
    contract_hash text NOT NULL,
    gold_validated boolean NOT NULL DEFAULT false
);
CREATE TABLE IF NOT EXISTS control.table_runs (
    run_id text NOT NULL REFERENCES control.runs(run_id),
    entity text NOT NULL,
    bronze_key text NOT NULL,
    extracted bigint NOT NULL,
    accepted bigint,
    rejected bigint,
    duplicates bigint,
    silver_key text,
    quarantine_key text,
    PRIMARY KEY(run_id,entity)
);
CREATE TABLE IF NOT EXISTS control.checkpoints (
    entity text PRIMARY KEY,
    watermark timestamptz NOT NULL,
    silver_key text NOT NULL,
    run_id text NOT NULL REFERENCES control.runs(run_id)
);
CREATE TABLE IF NOT EXISTS control.publications (
    singleton boolean PRIMARY KEY DEFAULT true CHECK(singleton),
    run_id text NOT NULL REFERENCES control.runs(run_id),
    published_at timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE IF NOT EXISTS control.generator_batches (
    batch_date date PRIMARY KEY, seed integer NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now()
);
CREATE SCHEMA IF NOT EXISTS gold;
