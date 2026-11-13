"""Run after make up/migrate/generate-data/run; never modifies the source."""

import pytest

from shoplakehouse.contracts import load
from shoplakehouse.database import connect
from shoplakehouse.settings import ROOT, Settings

pytestmark = pytest.mark.integration


def test_source_schema_matches_contracts():
    settings = Settings()
    with connect(settings, True) as conn:
        for table in load(settings.contracts).values():
            if table.source != "postgres":
                continue
            columns = {
                row["column_name"]
                for row in conn.execute(
                    "SELECT column_name FROM information_schema.columns WHERE table_schema='public' AND table_name=%s",
                    (table.name,),
                )
            }
            assert columns == set(table.columns)


def test_published_reconciliation_and_row_accounting():
    settings = Settings()
    with connect(settings) as conn:
        run = conn.execute(
            "SELECT r.* FROM control.publications p JOIN control.runs r USING(run_id)"
        ).fetchone()
        assert run and run["status"] == "published" and run["gold_validated"]
        for row in conn.execute(
            "SELECT * FROM control.table_runs WHERE run_id=%s", (run["run_id"],)
        ):
            assert row["extracted"] == row["accepted"] + row["rejected"] + row["duplicates"]
        fact = conn.execute("SELECT count(*) AS n FROM gold.fact_orders").fetchone()
        assert fact["n"] == run["source_orders"]


def test_gold_only_exposes_hashed_customer_identity():
    with connect(Settings()) as conn:
        row = conn.execute(
            "SELECT email_hash FROM gold.dim_customer WHERE customer_id<>-1 LIMIT 1"
        ).fetchone()
        assert row and len(row["email_hash"]) == 64 and "@" not in row["email_hash"]


def test_order_totals_match_lines():
    with connect(Settings()) as conn:
        count = conn.execute(
            """SELECT count(*) AS n FROM (
          SELECT o.order_id FROM gold.fact_orders o JOIN gold.fact_order_items i USING(order_id)
          GROUP BY o.order_id,o.total_amount HAVING o.total_amount<>sum(i.line_amount)
        ) failures"""
        ).fetchone()["n"]
        assert count == 0


def test_business_queries_execute_without_error():
    queries = sorted((ROOT / "sql/analytics/queries").glob("[0-9]*.sql"))
    assert len(queries) >= 15
    with connect(Settings()) as conn:
        for query in queries:
            conn.execute(query.read_text()).fetchall()
