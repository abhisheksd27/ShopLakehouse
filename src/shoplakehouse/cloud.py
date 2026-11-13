"""Athena/Glue implementation. AWS publication resolves a versioned release."""

from __future__ import annotations

import json
import os
import time
from decimal import Decimal
from typing import Any

import boto3

from .contracts import load
from .database import connect, require_running, table_records
from .errors import DataQualityError, PipelineError
from .settings import Settings
from .storage import Lake

GLUE_TYPES = {
    "long": "bigint",
    "integer": "int",
    "string": "string",
    "date": "date",
    "timestamp": "timestamp",
    "decimal(18,2)": "decimal(18,2)",
}


def athena(settings: Settings, query: str, database: str) -> list[dict]:
    client = boto3.client("athena", region_name=settings.region)
    execution = client.start_query_execution(
        QueryString=query,
        QueryExecutionContext={"Database": database},
        WorkGroup=os.getenv("ATHENA_WORKGROUP", "shoplakehouse-dev"),
        ResultConfiguration={"OutputLocation": f"s3://{settings.bucket}/athena-results/"},
    )
    query_id = execution["QueryExecutionId"]
    deadline = time.monotonic() + 1800
    while True:
        state = client.get_query_execution(QueryExecutionId=query_id)["QueryExecution"]["Status"]
        if state["State"] == "SUCCEEDED":
            break
        if state["State"] in {"FAILED", "CANCELLED"}:
            raise PipelineError(f"Athena query failed: {query_id}")
        if time.monotonic() > deadline:
            client.stop_query_execution(QueryExecutionId=query_id)
            raise TimeoutError(f"Athena query timed out: {query_id}")
        time.sleep(2)
    rows, headers = [], None
    for page in client.get_paginator("get_query_results").paginate(QueryExecutionId=query_id):
        for row in page["ResultSet"]["Rows"]:
            values = [cell.get("VarCharValue") for cell in row["Data"]]
            if headers is None:
                headers = values
            else:
                rows.append(dict(zip(headers, values, strict=True)))
    return rows


def _database(glue, name: str) -> None:
    try:
        glue.create_database(DatabaseInput={"Name": name})
    except glue.exceptions.AlreadyExistsException:
        pass


def load_glue(settings: Settings, run_id: str) -> None:
    run = require_running(settings, run_id)
    glue = boto3.client("glue", region_name=settings.region)
    schema = "s_" + run_id[:20]
    _database(glue, schema)
    _database(glue, run["candidate_schema"])
    tables = load(settings.contracts)
    for record in table_records(settings, run_id):
        table = tables[record["entity"]]
        definition: Any = {
            "Name": table.name,
            "TableType": "EXTERNAL_TABLE",
            "Parameters": {"classification": "parquet", "EXTERNAL": "TRUE"},
            "StorageDescriptor": {
                "Columns": [
                    {"Name": key, "Type": GLUE_TYPES[kind]}
                    for key, kind in dict(table.silver_columns, _loaded_at="timestamp").items()
                ],
                "Location": f"s3://{settings.bucket}/{record['silver_key'].rsplit('/',1)[0]}/",
                "InputFormat": "org.apache.hadoop.hive.ql.io.parquet.MapredParquetInputFormat",
                "OutputFormat": "org.apache.hadoop.hive.ql.io.parquet.MapredParquetOutputFormat",
                "SerdeInfo": {
                    "SerializationLibrary": "org.apache.hadoop.hive.ql.io.parquet.serde.ParquetHiveSerDe"
                },
            },
        }
        try:
            glue.create_table(DatabaseName=schema, TableInput=definition)
        except glue.exceptions.AlreadyExistsException:
            glue.update_table(DatabaseName=schema, TableInput=definition)
    with connect(settings) as conn:
        previous = conn.execute(
            """SELECT r.candidate_schema FROM control.publications p
                                    JOIN control.runs r USING(run_id)"""
        ).fetchone()
    if previous:
        try:
            glue.get_table(DatabaseName=run["candidate_schema"], Name="customer_history")
        except glue.exceptions.EntityNotFoundException:
            candidate = run["candidate_schema"]
            prior = previous["candidate_schema"]
            athena(
                settings,
                f"""CREATE TABLE "{candidate}"."customer_history"
                WITH (table_type='ICEBERG',is_external=false,format='PARQUET',
                location='s3://{settings.bucket}/gold/{candidate}/customer_history/')
                AS SELECT * FROM "{prior}"."customer_history" """,
                candidate,
            )


def reconcile_athena(settings: Settings, run_id: str) -> dict:
    run = require_running(settings, run_id)
    schema = run["candidate_schema"]
    rows = athena(
        settings,
        f"""SELECT count(*) AS orders,
        coalesce(sum(CASE WHEN status='delivered' THEN total_amount ELSE 0 END),0) AS revenue
        FROM "{schema}"."fact_orders" """,
        schema,
    )
    if (
        int(rows[0]["orders"]) != run["source_orders"]
        or Decimal(rows[0]["revenue"]) != run["source_revenue"]
    ):
        raise DataQualityError("Source/Athena reconciliation failed")
    result = {
        "run_id": run_id,
        "orders": int(rows[0]["orders"]),
        "revenue": rows[0]["revenue"],
        "passed": True,
    }
    Lake(settings).put(f"audit/{run_id}/reconciliation.json", json.dumps(result).encode())
    return result


def publish_athena(settings: Settings, run_id: str) -> None:
    from .warehouse import GOLD_MODELS, commit_checkpoints

    run = require_running(settings, run_id)
    release = {"run_id": run_id, "schema": run["candidate_schema"], "tables": GOLD_MODELS}
    lake = Lake(settings)
    # Immutable release first, then an atomic control-plane publication. Readers
    # resolve control.publications once and pin this schema for all queries.
    lake.put(f"releases/{run_id}.json", json.dumps(release).encode())
    with connect(settings) as conn:
        commit_checkpoints(conn, settings, run_id)


def current_release(settings: Settings) -> dict:
    with connect(settings) as conn:
        record = conn.execute(
            """SELECT r.run_id,r.candidate_schema,p.published_at
            FROM control.publications p JOIN control.runs r USING(run_id)"""
        ).fetchone()
    if not record:
        raise ValueError("No published release")
    return dict(record, s3_manifest=f"s3://{settings.bucket}/releases/{record['run_id']}.json")
