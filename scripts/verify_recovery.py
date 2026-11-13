"""Exercise rerun idempotency, quarantine failure and successful recovery locally.

Requires an already published synthetic initial batch. Temporarily injects bad
CSV/fixture rows, restores clean generated CSVs in finally, never truncates SQL.
"""

import json
import subprocess
from datetime import datetime, timezone

from shoplakehouse.database import connect
from shoplakehouse.settings import ROOT, Settings


def snapshot(settings):
    with connect(settings) as conn:
        return {
            "publication": conn.execute("SELECT run_id FROM control.publications").fetchone(),
            "checkpoints": list(conn.execute("SELECT * FROM control.checkpoints ORDER BY entity")),
            "orders": conn.execute(
                "SELECT count(*) AS n,sum(total_amount) AS total FROM gold.fact_orders"
            ).fetchone(),
        }


def main():
    settings = Settings()
    with connect(settings, True) as conn:
        batch = conn.execute(
            "SELECT * FROM public.simulation_batches WHERE batch_key LIKE 'initial:%' ORDER BY created_at LIMIT 1"
        ).fetchone()
    if not batch:
        raise ValueError("Generate and publish an initial batch first")
    day = str(batch["batch_date"])
    root = ROOT / "artifacts" / ("recovery-" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S"))
    root.mkdir(parents=True)

    def command(name, args, expected=0, inject=False):
        prefix = ["docker", "compose", "run", "--rm"]
        if inject:
            prefix += ["-e", "INJECT_DQ_FIXTURES=true"]
        with (root / (name + ".log")).open("w") as log:
            result = subprocess.run(prefix + ["pipeline", *args], cwd=ROOT, stdout=log, stderr=log)
        if expected == 0 and result.returncode != 0:
            raise RuntimeError(f"{name} failed; inspect {root / (name + '.log')}")
        if expected != 0 and result.returncode == 0:
            raise AssertionError("Injected quality error unexpectedly published")

    generator = [
        "generate",
        "--day",
        day,
        "--seed",
        str(batch["seed"]),
        "--orders",
        str(batch["order_count"]),
    ]
    before = snapshot(settings)
    command("generate-replay", generator)
    command("rerun", ["run", "--day", day])
    rerun = snapshot(settings)
    assert rerun["orders"] == before["orders"], "Rerun changed business totals"
    try:
        command("inject", generator + ["--inject-quality"])
        command("expected-failure", ["run", "--day", day], expected=1, inject=True)
        failed = snapshot(settings)
        assert failed == rerun, "Failure changed published data or checkpoint state"
        with connect(settings) as conn:
            bad = conn.execute(
                "SELECT * FROM control.runs ORDER BY started_at DESC LIMIT 1"
            ).fetchone()
            assert bad["status"] == "failed" and bad["error_type"] == "DataQualityError"
            rejected = conn.execute(
                "SELECT sum(rejected) AS n FROM control.table_runs WHERE run_id=%s",
                (bad["run_id"],),
            ).fetchone()["n"]
            assert rejected > 0
    finally:
        command("restore-clean-csv", generator)
    command("recover", ["run", "--day", day])
    recovered = snapshot(settings)
    assert recovered["orders"] == before["orders"]
    report = {
        "rerun_totals_unchanged": True,
        "failed_run_preserved_publication_and_checkpoints": True,
        "quarantine_rejections": rejected,
        "recovery_published": True,
        "final_publication": recovered["publication"],
    }
    (root / "report.json").write_text(json.dumps(report, indent=2, default=str))
    print(json.dumps(report, default=str))


if __name__ == "__main__":
    main()
