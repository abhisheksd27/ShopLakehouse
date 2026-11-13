"""Operational entry points. All data-changing steps are explicit commands."""

from __future__ import annotations

import json
import logging
from datetime import date
from typing import Optional

import typer

from .contracts import load
from .database import begin_run, connect, fail_run, source_totals
from .database import migrate as migrate_db
from .logging import configure
from .settings import Settings
from .storage import Lake

app = typer.Typer(no_args_is_help=True, pretty_exceptions_show_locals=False)
log = logging.getLogger(__name__)


@app.callback()
def main() -> None:
    configure()


@app.command()
def migrate(adopt_legacy: bool = False) -> None:
    """Apply checked migrations; optionally adopt the existing lesson schema."""
    migrate_db(Settings(), adopt_legacy)
    typer.echo("Migrations applied")


@app.command()
def init_lake() -> None:
    """Create the configured local bucket if absent."""
    Lake(Settings()).ensure_bucket()
    typer.echo("Lake bucket ready")


@app.command()
def generate(
    mode: str = "initial",
    day: str = str(date.today()),
    seed: int = 27,
    orders: int = 100,
    inject_quality: bool = False,
) -> None:
    """Generate reproducible synthetic data after implementation is ready."""
    from .simulator import generate as generate_data

    typer.echo(
        json.dumps(
            generate_data(Settings(), mode, date.fromisoformat(day), seed, orders, inject_quality)
        )
    )


def start(settings: Settings, day: date) -> str:
    run_id = begin_run(settings, day)
    try:
        totals = source_totals(settings)
        with connect(settings) as conn:
            conn.execute(
                "UPDATE control.runs SET source_orders=%s,source_revenue=%s WHERE run_id=%s",
                (totals["orders"], totals["revenue"], run_id),
            )
    except Exception as exc:
        fail_run(settings, run_id, type(exc).__name__)
        raise
    return run_id


@app.command()
def run(day: str = str(date.today()), full: bool = False) -> None:
    """Execute the complete local/cloud pipeline and publish only on success."""
    from .ingestion import ingest
    from .silver import transform
    from .warehouse import build_gold, load_candidates, publish

    settings = Settings()
    Lake(settings).ensure_bucket()
    run_id = start(settings, date.fromisoformat(day))
    log.info("Pipeline started", extra={"context": {"run_id": run_id}})
    try:
        ingest(settings, run_id, full)
        transform(settings, run_id)
        load_candidates(settings, run_id)
        build_gold(settings, run_id)
        publish(settings, run_id)
    except Exception as exc:
        fail_run(settings, run_id, type(exc).__name__)
        log.error(
            "Pipeline failed; previous Gold publication retained",
            extra={"context": {"run_id": run_id, "error_type": type(exc).__name__}},
        )
        raise
    typer.echo(json.dumps({"run_id": run_id, "status": "published"}))


@app.command()
def stage(
    name: str,
    run_id: Optional[str] = None,
    entity: Optional[str] = None,
    day: str = str(date.today()),
    full: bool = False,
) -> None:
    """Airflow/ECS stage boundary; return small metadata, never row data."""
    settings = Settings()
    if name == "begin":
        typer.echo(start(settings, date.fromisoformat(day)))
        return
    if name == "entities":
        typer.echo(json.dumps(list(load(settings.contracts))))
        return
    if name == "active":
        with connect(settings) as conn:
            row = conn.execute("SELECT run_id FROM control.runs WHERE status='running'").fetchone()
        if not row:
            raise ValueError("No active run")
        typer.echo(row["run_id"])
        return
    if not run_id:
        raise ValueError("--run-id is required")
    if name == "ingest":
        from .ingestion import ingest_table

        if not entity:
            raise ValueError("--entity is required")
        typer.echo(json.dumps(ingest_table(settings, run_id, entity, full)))
    elif name == "silver":
        from .silver import transform

        transform(settings, run_id)
    elif name == "load":
        from .warehouse import load_candidates

        load_candidates(settings, run_id)
    elif name == "gold":
        from .warehouse import build_gold

        build_gold(settings, run_id)
    elif name == "publish":
        from .warehouse import publish

        publish(settings, run_id)
    elif name == "fail":
        fail_run(settings, run_id, "OrchestratorFailure")
    else:
        raise ValueError("Unknown stage")


@app.command()
def status() -> None:
    """Print recent run metadata without secrets or record-level data."""
    with connect(Settings()) as conn:
        rows = list(
            conn.execute(
                """SELECT run_id,status,logical_date,started_at,finished_at,error_type
                                    FROM control.runs ORDER BY started_at DESC LIMIT 10"""
            )
        )
    typer.echo(json.dumps(rows, default=str, indent=2))


@app.command()
def release() -> None:
    """Resolve a single published schema for consistent AWS queries."""
    from .cloud import current_release

    typer.echo(json.dumps(current_release(Settings()), default=str, indent=2))


@app.command()
def abandon(run_id: str) -> None:
    """Release a stale run after the operator has stopped its workers."""
    fail_run(Settings(), run_id, "OperatorAbandoned")
    typer.echo("Run marked failed; checkpoints unchanged")


@app.command()
def maintenance(days: int = 14, apply: bool = False) -> None:
    """List obsolete local candidate schemas; deletion is explicitly opt-in."""
    from psycopg import sql

    with connect(Settings()) as conn:
        rows = list(
            conn.execute(
                """SELECT run_id,candidate_schema FROM control.runs
          WHERE status <> 'running' AND started_at < now() - make_interval(days => %s)
          AND run_id NOT IN (SELECT run_id FROM control.publications)""",
                (days,),
            )
        )
        for row in rows:
            typer.echo(row["candidate_schema"])
            if apply and Settings().warehouse == "postgres":
                for name in (row["candidate_schema"], "s_" + row["run_id"][:20]):
                    conn.execute(
                        sql.SQL("DROP SCHEMA IF EXISTS {} CASCADE").format(sql.Identifier(name))
                    )


if __name__ == "__main__":
    app()
