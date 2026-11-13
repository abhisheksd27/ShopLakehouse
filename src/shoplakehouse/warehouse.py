"""Candidate loading and atomic PostgreSQL publication."""

from __future__ import annotations

import json
import logging
import os
import shutil
import subprocess
import sys
import tempfile
import uuid
from pathlib import Path

from psycopg import sql

from .contracts import load
from .database import connect, invalidate_gold, require_running, table_records
from .errors import DataQualityError
from .settings import ROOT, Settings
from .storage import Lake

GOLD_MODELS = (
    "fact_orders",
    "fact_order_items",
    "fact_payments",
    "dim_customer",
    "dim_product",
    "dim_date",
    "daily_revenue",
    "customer_ltv",
    "cohort_retention",
    "marketing_performance",
)
PG_TYPES = {
    "long": "bigint",
    "integer": "integer",
    "string": "text",
    "timestamp": "timestamptz",
    "date": "date",
    "decimal(18,2)": "numeric(18,2)",
}


def load_candidates(settings: Settings, run_id: str) -> None:
    run = require_running(settings, run_id)
    invalidate_gold(settings, run_id)
    records = table_records(settings, run_id)
    tables = load(settings.contracts)
    if len(records) != len(tables) or any(not row["silver_key"] for row in records):
        raise DataQualityError("Candidate Silver data is incomplete")
    if settings.warehouse == "athena":
        from .cloud import load_glue

        load_glue(settings, run_id)
        return
    lake = Lake(settings)
    silver_schema = "s_" + run_id[:20]
    candidate = run["candidate_schema"]
    with connect(settings) as conn:
        conn.execute(
            sql.SQL("CREATE SCHEMA IF NOT EXISTS {}").format(sql.Identifier(silver_schema))
        )
        conn.execute(sql.SQL("CREATE SCHEMA IF NOT EXISTS {}").format(sql.Identifier(candidate)))
        for record in records:
            table = tables[record["entity"]]
            arrow = lake.parquet(record["silver_key"])
            columns = dict(table.silver_columns, _loaded_at="timestamp")
            definition = sql.SQL(",").join(
                sql.SQL("{} {}").format(sql.Identifier(name), sql.SQL(PG_TYPES[kind]))
                for name, kind in columns.items()
            )
            target = sql.Identifier(silver_schema, table.name)
            conn.execute(sql.SQL("CREATE TABLE IF NOT EXISTS {} ({})").format(target, definition))
            conn.execute(sql.SQL("TRUNCATE {}").format(target))
            with conn.cursor().copy(
                sql.SQL("COPY {} ({}) FROM STDIN").format(
                    target, sql.SQL(",").join(map(sql.Identifier, columns))
                )
            ) as copy:
                for row in arrow.select(list(columns)).to_pylist():
                    copy.write_row(tuple(row[name] for name in columns))
            count = conn.execute(sql.SQL("SELECT count(*) AS n FROM {}").format(target)).fetchone()[
                "n"
            ]
            if count != len(arrow):
                raise DataQualityError(f"Loader row count mismatch for {table.name}")
        # Copy prior observed customer history into this isolated candidate.
        previous = conn.execute(
            """SELECT r.candidate_schema FROM control.publications p
                                   JOIN control.runs r USING(run_id)"""
        ).fetchone()
        if previous:
            source = sql.Identifier(previous["candidate_schema"], "customer_history")
            conn.execute(
                sql.SQL("CREATE TABLE IF NOT EXISTS {} AS TABLE {}").format(
                    sql.Identifier(candidate, "customer_history"), source
                )
            )


def dbt(settings: Settings, run_id: str, command: list[str]) -> None:
    run = require_running(settings, run_id)
    environment = dict(
        os.environ,
        DBT_SCHEMA=run["candidate_schema"],
        SILVER_SCHEMA="s_" + run_id[:20],
        DBT_PROFILES_DIR=str(ROOT / "dbt"),
        DBT_SEND_ANONYMOUS_USAGE_STATS="false",
        DO_NOT_TRACK="1",
        DBT_TARGET=settings.warehouse,
    )
    # Explicit env defaults are needed when only .env supplied the values.
    for key, default in {
        "ANALYTICS_DB_HOST": "localhost",
        "ANALYTICS_DB_PORT": "5434",
        "ANALYTICS_DB_NAME": "shoplakehouse_analytics",
        "ANALYTICS_DB_USER": "analytics_admin",
    }.items():
        environment.setdefault(key, default)
    # dbt rewrites artifacts concurrently; use a native filesystem, not an
    # external-drive bind mount. Persist the completed evidence to the lake.
    target = Path(tempfile.gettempdir()) / "shoplakehouse-dbt" / run_id
    target.mkdir(parents=True, exist_ok=True)
    binary = str(Path(sys.executable).parent / "dbt")
    args = [
        binary,
        *command,
        "--project-dir",
        str(ROOT / "dbt"),
        "--profiles-dir",
        str(ROOT / "dbt"),
        "--target",
        settings.warehouse,
        "--target-path",
        str(target),
        "--log-path",
        str(target / "logs"),
    ]
    try:
        subprocess.run(args, env=environment, check=True, cwd=ROOT)
    finally:
        attempt = "_".join(command) + "_" + uuid.uuid4().hex[:8]
        report = ROOT / "artifacts" / run_id / "dbt" / attempt
        lake = Lake(settings)
        for path in target.rglob("*"):
            if not path.is_file() or path.suffix not in {".json", ".html", ".sql", ".log"}:
                continue
            relative = path.relative_to(target)
            lake.put(f"audit/{run_id}/dbt/{attempt}/{relative}", path.read_bytes())
            try:
                destination = report / relative
                destination.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(path, destination)
            except OSError:
                logging.getLogger(__name__).warning(
                    "Local report copy failed; audit retained in lake"
                )


def build_gold(settings: Settings, run_id: str) -> None:
    invalidate_gold(settings, run_id)
    dbt(settings, run_id, ["source", "freshness"])
    dbt(settings, run_id, ["build"])
    dbt(settings, run_id, ["docs", "generate"])
    with connect(settings) as conn:
        conn.execute("UPDATE control.runs SET gold_validated=true WHERE run_id=%s", (run_id,))


def reconcile(settings: Settings, run_id: str) -> dict:
    run = require_running(settings, run_id)
    if settings.warehouse == "athena":
        from .cloud import reconcile_athena

        return reconcile_athena(settings, run_id)
    with connect(settings) as conn:
        result = conn.execute(
            sql.SQL(
                """SELECT count(*) AS orders,
            coalesce(sum(CASE WHEN status='delivered' THEN total_amount ELSE 0 END),0) AS revenue
            FROM {}"""
            ).format(sql.Identifier(run["candidate_schema"], "fact_orders"))
        ).fetchone()
    if result["orders"] != run["source_orders"] or result["revenue"] != run["source_revenue"]:
        raise DataQualityError("Source-to-Gold totals differ; candidate will not be published")
    report = {
        "run_id": run_id,
        "source_orders": run["source_orders"],
        "gold_orders": result["orders"],
        "source_revenue": str(run["source_revenue"]),
        "gold_revenue": str(result["revenue"]),
        "passed": True,
    }
    Lake(settings).put(f"audit/{run_id}/reconciliation.json", json.dumps(report).encode())
    return report


def commit_checkpoints(conn, settings: Settings, run_id: str) -> None:
    # Called in the same PostgreSQL transaction as stable view replacement.
    conn.execute(
        """INSERT INTO control.checkpoints(entity,watermark,silver_key,run_id)
        SELECT t.entity,r.cutoff,t.silver_key,r.run_id FROM control.table_runs t
        JOIN control.runs r USING(run_id) WHERE r.run_id=%s
        ON CONFLICT(entity) DO UPDATE SET watermark=excluded.watermark,
        silver_key=excluded.silver_key,run_id=excluded.run_id""",
        (run_id,),
    )
    conn.execute(
        """INSERT INTO control.publications(singleton,run_id) VALUES(true,%s)
        ON CONFLICT(singleton) DO UPDATE SET run_id=excluded.run_id,published_at=now()""",
        (run_id,),
    )
    conn.execute(
        "UPDATE control.runs SET status='published',finished_at=now() WHERE run_id=%s", (run_id,)
    )


def publish(settings: Settings, run_id: str) -> None:
    run = require_running(settings, run_id)
    if not run["gold_validated"]:
        raise DataQualityError("dbt build/test success is required before publication")
    reconcile(settings, run_id)
    if settings.warehouse == "athena":
        from .cloud import publish_athena

        publish_athena(settings, run_id)
        return
    with connect(settings) as conn:
        for name in (*GOLD_MODELS, "customer_history"):
            conn.execute(
                sql.SQL("CREATE OR REPLACE VIEW {} AS SELECT * FROM {}").format(
                    sql.Identifier("gold", name), sql.Identifier(run["candidate_schema"], name)
                )
            )
        commit_checkpoints(conn, settings, run_id)
