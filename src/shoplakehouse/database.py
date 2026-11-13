"""Database access, migrations and an auditable run/checkpoint ledger."""

from __future__ import annotations

import hashlib
import re
import uuid
from datetime import date
from pathlib import Path

import psycopg
from psycopg import sql
from psycopg.rows import dict_row

from .contracts import fingerprint
from .errors import ConcurrentRunError
from .settings import ROOT, Settings


def connect(settings: Settings, source: bool = False, **kwargs):
    return psycopg.connect(settings.dsn(source), row_factory=dict_row, **kwargs)


def _body(path: Path) -> str:
    text = path.read_text()
    # Existing lessons have comments before BEGIN. Keep comments, remove only
    # standalone transaction boundaries; ledger and DDL commit together below.
    return re.sub(r"(?im)^\s*(BEGIN|COMMIT);", "", text)


def migrate(settings: Settings, adopt_legacy: bool = False) -> None:
    """Adopt the known lesson schema only when explicitly requested."""
    with connect(settings, True) as conn:
        conn.execute("SELECT pg_advisory_xact_lock(739201)")
        conn.execute(
            """CREATE TABLE IF NOT EXISTS public.schema_migrations
                        (filename text PRIMARY KEY, checksum text NOT NULL,
                         adopted boolean NOT NULL DEFAULT false,
                         applied_at timestamptz NOT NULL DEFAULT now())"""
        )
        applied = {r["filename"]: r for r in conn.execute("SELECT * FROM public.schema_migrations")}
        existing = conn.execute("SELECT to_regclass('public.customers') AS name").fetchone()["name"]
        legacy = set()
        if existing and not applied:
            if not adopt_legacy:
                raise ValueError("Existing lesson tables: run migrate --adopt-legacy once")
            expected = {
                "customers": {"id", "name", "email", "city", "country", "created_at", "updated_at"},
                "categories": {"id", "name", "created_at", "updated_at"},
                "products": {
                    "id",
                    "category_id",
                    "sku",
                    "name",
                    "price",
                    "stock_quantity",
                    "created_at",
                    "updated_at",
                },
                "orders": {
                    "id",
                    "customer_id",
                    "ordered_at",
                    "status",
                    "currency",
                    "total_amount",
                    "created_at",
                    "updated_at",
                },
                "order_items": {
                    "id",
                    "order_id",
                    "product_id",
                    "line_number",
                    "quantity",
                    "unit_price",
                    "discount_amount",
                    "created_at",
                    "updated_at",
                },
            }
            for table, columns in expected.items():
                rows = conn.execute(
                    "SELECT column_name FROM information_schema.columns WHERE table_schema='public' AND table_name=%s",
                    (table,),
                )
                if {r["column_name"] for r in rows} != columns:
                    raise ValueError(f"Legacy schema differs at {table}; inspect before adoption")
            timestamps = conn.execute(
                """SELECT count(*) AS n FROM information_schema.columns
              WHERE table_schema='public' AND table_name IN ('categories','products')
              AND column_name IN ('created_at','updated_at') AND data_type='timestamp with time zone'"""
            ).fetchone()["n"]
            constraints = {
                r["conname"]
                for r in conn.execute(
                    "SELECT conname FROM pg_constraint WHERE conrelid='public.products'::regclass"
                )
            }
            restrict = conn.execute(
                "SELECT confdeltype FROM pg_constraint WHERE conname='products_category_id_fk'"
            ).fetchone()
            if (
                timestamps != 4
                or not {"products_price_valid", "products_stock_nonnegative"} <= constraints
                or restrict["confdeltype"] != "r"
            ):
                raise ValueError(
                    "Legacy catalog corrections are missing; apply migration 003 first"
                )
            legacy = {p.name for p in (ROOT / "sql/source").glob("00[1-4]_*.sql")}
        for path in sorted((ROOT / "sql/source").glob("[0-9]*.sql")):
            checksum = hashlib.sha256(path.read_bytes()).hexdigest()
            if path.name in applied:
                if applied[path.name]["checksum"] != checksum:
                    raise ValueError(f"Applied migration changed: {path.name}")
                continue
            if path.name not in legacy:
                conn.execute(_body(path))
            conn.execute(
                "INSERT INTO public.schema_migrations(filename,checksum,adopted) VALUES (%s,%s,%s)",
                (path.name, checksum, path.name in legacy),
            )
    with connect(settings) as conn:
        conn.execute((ROOT / "sql/analytics/001_control.sql").read_text())
        conn.execute(
            "CREATE UNIQUE INDEX IF NOT EXISTS one_running_pipeline ON control.runs(status) WHERE status='running'"
        )


def begin_run(settings: Settings, logical_date: date) -> str:
    run_id = uuid.uuid4().hex
    with connect(settings, True) as source:
        cutoff = source.execute("SELECT clock_timestamp() AS cutoff").fetchone()["cutoff"]
    try:
        with connect(settings) as conn:
            conn.execute(
                """INSERT INTO control.runs(run_id,logical_date,cutoff,status,candidate_schema,contract_hash)
                         VALUES (%s,%s,%s,'running',%s,%s)""",
                (run_id, logical_date, cutoff, "b_" + run_id[:20], fingerprint(settings.contracts)),
            )
    except psycopg.errors.UniqueViolation as exc:
        raise ConcurrentRunError(
            "An active pipeline run exists; inspect runs before recovery"
        ) from exc
    return run_id


def run_record(settings: Settings, run_id: str) -> dict:
    with connect(settings) as conn:
        result = conn.execute("SELECT * FROM control.runs WHERE run_id=%s", (run_id,)).fetchone()
    if result is None:
        raise ValueError("Unknown run ID")
    return result


def require_running(settings: Settings, run_id: str) -> dict:
    record = run_record(settings, run_id)
    if record["status"] != "running":
        raise ValueError(f"Run is {record['status']}, not running")
    if record["contract_hash"] != fingerprint(settings.contracts):
        raise ValueError("Contract changed during run")
    return record


def fail_run(settings: Settings, run_id: str, error_type: str) -> None:
    with connect(settings) as conn:
        conn.execute(
            """UPDATE control.runs SET status='failed',finished_at=now(),error_type=%s
                         WHERE run_id=%s AND status='running'""",
            (error_type, run_id),
        )


def invalidate_gold(settings: Settings, run_id: str) -> None:
    """Any candidate mutation requires a new successful dbt validation."""
    require_running(settings, run_id)
    with connect(settings) as conn:
        conn.execute("UPDATE control.runs SET gold_validated=false WHERE run_id=%s", (run_id,))


def table_records(settings: Settings, run_id: str) -> list[dict]:
    with connect(settings) as conn:
        return list(
            conn.execute(
                "SELECT * FROM control.table_runs WHERE run_id=%s ORDER BY entity", (run_id,)
            )
        )


def checkpoint(settings: Settings, entity: str) -> dict | None:
    with connect(settings) as conn:
        return conn.execute(
            "SELECT * FROM control.checkpoints WHERE entity=%s", (entity,)
        ).fetchone()


def source_totals(settings: Settings) -> dict:
    # Measured at extraction time. Concurrent source changes can make this fail
    # reconciliation conservatively; re-run after writes settle.
    with connect(settings, True) as conn:
        return conn.execute(
            """SELECT count(*) AS orders,
          coalesce(sum(CASE WHEN status='delivered' THEN total_amount ELSE 0 END),0) AS revenue
          FROM public.orders"""
        ).fetchone()


def identifier(value: str) -> sql.Identifier:
    if not re.fullmatch("[a-z][a-z0-9_]*", value):
        raise ValueError("Invalid database identifier")
    return sql.Identifier(value)
