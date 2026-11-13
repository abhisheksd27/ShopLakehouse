"""Airflow 2 orchestration. XCom contains only IDs/statistics, never data frames."""

from __future__ import annotations

import json
import os
import subprocess
from datetime import timedelta

import pendulum
from airflow import DAG, Dataset
from airflow.decorators import task
from airflow.utils.task_group import TaskGroup

CLI = os.getenv("SHOPLAKEHOUSE_CLI", "/opt/pipeline/bin/shoplakehouse")
ENTITIES = [
    "customers",
    "categories",
    "products",
    "addresses",
    "orders",
    "order_items",
    "payments",
    "shipments",
    "reviews",
    "product_api",
    "marketing",
    "web_traffic",
]
BRONZE = Dataset("s3://shoplakehouse/bronze/committed")
SILVER = Dataset("s3://shoplakehouse/silver/candidate")
GOLD = Dataset("s3://shoplakehouse/gold/published")


def command(*args: str) -> str:
    result = subprocess.run([CLI, *args], capture_output=True, text=True, check=False)
    if result.returncode:
        # Avoid logging captured record content or credentials on worker errors.
        raise RuntimeError(f"Pipeline command failed: {args[0]} (exit {result.returncode})")
    return result.stdout.strip()


def failure(context) -> None:
    pipeline_run_id = context["ti"].xcom_pull(task_ids="begin")
    if pipeline_run_id:
        command("stage", "fail", "--run-id", pipeline_run_id)
    # Outbound notification is opt-in and requires a configured endpoint.
    webhook = os.getenv("ALERT_WEBHOOK_URL")
    if webhook:
        import requests

        requests.post(
            webhook,
            json={"text": f"ShopLakehouse failed: {context['dag'].dag_id}; run {pipeline_run_id}"},
            timeout=10,
        ).raise_for_status()


DEFAULT = {
    "owner": "shoplakehouse",
    "retries": 2,
    "retry_delay": timedelta(minutes=1),
    "execution_timeout": timedelta(hours=1),
    "on_failure_callback": failure,
}

with DAG(
    "master_pipeline",
    schedule="0 2 * * *",
    start_date=pendulum.datetime(2026, 1, 1, tz="Asia/Kolkata"),
    catchup=False,
    max_active_runs=1,
    default_args=DEFAULT,
    tags=["shoplakehouse", "production-flow"],
) as master_pipeline:

    @task(task_id="begin")
    def begin(**context):
        return command("stage", "begin", "--day", context["ds"])

    @task(pool="shoplakehouse")
    def extract(pipeline_run_id: str, entity: str):
        return json.loads(
            command("stage", "ingest", "--run-id", pipeline_run_id, "--entity", entity)
        )

    @task(outlets=[BRONZE])
    def bronze_ready(pipeline_run_id: str):
        return pipeline_run_id

    @task(outlets=[SILVER], pool="shoplakehouse")
    def silver(pipeline_run_id: str):
        command("stage", "silver", "--run-id", pipeline_run_id)
        return pipeline_run_id

    @task(pool="shoplakehouse")
    def load(pipeline_run_id: str):
        command("stage", "load", "--run-id", pipeline_run_id)
        return pipeline_run_id

    @task(pool="shoplakehouse")
    def gold(pipeline_run_id: str):
        command("stage", "gold", "--run-id", pipeline_run_id)
        return pipeline_run_id

    @task(outlets=[GOLD])
    def publish(pipeline_run_id: str):
        command("stage", "publish", "--run-id", pipeline_run_id)

    pipeline_run_id = begin()
    with TaskGroup("ingestion"):
        extracted = extract.partial(pipeline_run_id=pipeline_run_id).expand(entity=ENTITIES)
        ready = bronze_ready(pipeline_run_id)
        extracted >> ready
    publish(gold(load(silver(ready))))

# Manual recovery DAGs reuse an existing active run. The scheduled master is
# the sole default coordinator, preventing competing dataset-triggered runs.
for dag_id, stages in {
    "ingest_bronze_daily": ["ingest"],
    "transform_silver_daily": ["silver", "load"],
    "build_gold_dbt": ["gold", "publish"],
}.items():
    with DAG(
        dag_id,
        schedule=None,
        start_date=pendulum.datetime(2026, 1, 1, tz="UTC"),
        catchup=False,
        max_active_runs=1,
        default_args=DEFAULT,
        tags=["shoplakehouse", "manual-recovery"],
    ) as recovery:

        @task(task_id="recover")
        def recover(stages=stages, **context):
            active = context["dag_run"].conf.get("run_id") or command("stage", "active")
            for stage_name in stages:
                if stage_name == "ingest":
                    for entity in ENTITIES:
                        command("stage", "ingest", "--run-id", active, "--entity", entity)
                else:
                    command("stage", stage_name, "--run-id", active)

        recover()
    globals()[dag_id] = recovery

with DAG(
    "maintenance",
    schedule="0 5 * * 0",
    start_date=pendulum.datetime(2026, 1, 1, tz="UTC"),
    catchup=False,
    max_active_runs=1,
    tags=["shoplakehouse"],
) as maintenance:

    @task
    def list_obsolete_schemas():
        return command("maintenance", "--days", "14")

    list_obsolete_schemas()
