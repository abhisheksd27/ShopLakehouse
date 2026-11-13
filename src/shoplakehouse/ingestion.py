"""Bounded incremental extraction. Checkpoints commit only after publication."""

from __future__ import annotations

import csv
import io
import json
import os
import uuid
from abc import ABC, abstractmethod
from datetime import datetime, timedelta, timezone

import httpx
from psycopg import sql
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_random_exponential

from .contracts import Table, load
from .database import checkpoint, connect, require_running, source_totals, table_records
from .errors import SchemaDriftError
from .settings import Settings
from .storage import Lake


class BaseExtractor(ABC):
    @abstractmethod
    def extract(self, table: Table, lower: datetime, upper: datetime) -> list[dict]:
        raise NotImplementedError


class PostgresExtractor(BaseExtractor):
    def __init__(self, settings: Settings):
        self.settings = settings

    def extract(self, table: Table, lower: datetime, upper: datetime) -> list[dict]:
        with connect(self.settings, True) as conn:
            conn.execute("SET TRANSACTION READ ONLY")
            actual = {
                row["column_name"]
                for row in conn.execute(
                    "SELECT column_name FROM information_schema.columns WHERE table_schema='public' AND table_name=%s",
                    (table.name,),
                )
            }
            if actual != set(table.columns):
                raise SchemaDriftError(f"Column mismatch in {table.name}")
            query = sql.SQL(
                "SELECT * FROM public.{} WHERE updated_at >= %s AND updated_at <= %s ORDER BY updated_at,id"
            ).format(sql.Identifier(table.name))
            with conn.cursor(name="extract") as cursor:
                cursor.execute(query, (lower, upper))
                return list(cursor)


@retry(
    retry=retry_if_exception_type((httpx.TransportError, httpx.HTTPStatusError)),
    wait=wait_random_exponential(multiplier=1, max=20),
    stop=stop_after_attempt(5),
    reraise=True,
)
def request_page(client: httpx.Client, url: str, params: dict) -> dict:
    response = client.get(url, params=params)
    response.raise_for_status()
    return response.json()


class ApiExtractor(BaseExtractor):
    def __init__(self, settings: Settings):
        self.settings = settings

    def extract(self, table: Table, lower: datetime, upper: datetime) -> list[dict]:
        rows, after = [], 0
        with httpx.Client(
            timeout=30, headers={"Authorization": f"Bearer {self.settings.api_token}"}
        ) as client:
            while True:
                page = request_page(
                    client,
                    self.settings.api_url + "/products",
                    {
                        "after_id": after,
                        "limit": 200,
                        "updated_since": lower.isoformat(),
                        "as_of": upper.isoformat(),
                    },
                )
                items = page["items"]
                for item in items:
                    if set(item) != set(table.columns):
                        raise SchemaDriftError(f"API column mismatch in {table.name}")
                rows.extend(items)
                next_id = page["next_after_id"]
                if next_id is None:
                    return rows
                if next_id <= after:
                    raise SchemaDriftError("API cursor did not advance")
                after = next_id


class CsvExtractor(BaseExtractor):
    def __init__(self, settings: Settings):
        self.settings = settings

    def extract(self, table: Table, lower: datetime, upper: datetime) -> list[dict]:
        rows: list[dict] = []
        if not self.settings.endpoint:
            lake = Lake(self.settings)
            pages = lake.client.get_paginator("list_objects_v2").paginate(
                Bucket=self.settings.bucket, Prefix=f"landing/csv/{table.name}/"
            )
            for page in pages:
                for item in page.get("Contents", []):
                    if item["Key"].endswith(".csv"):
                        reader = csv.DictReader(io.StringIO(lake.get(item["Key"]).decode()))
                        if set(reader.fieldnames or []) != set(table.columns):
                            raise SchemaDriftError(f"CSV column mismatch in {table.name}")
                        rows.extend(dict(row) for row in reader)
            return rows
        # Replay all small CSV files so late-arriving historical files are found.
        for path in sorted((self.settings.data_dir / "csv" / table.name).glob("*.csv")):
            if path.name.startswith("._"):
                continue
            with path.open(newline="") as handle:
                reader = csv.DictReader(handle)
                if set(reader.fieldnames or []) != set(table.columns):
                    raise SchemaDriftError(f"CSV column mismatch in {table.name}")
                rows.extend(dict(row) for row in reader)
        return rows


def ingest_table(settings: Settings, run_id: str, entity: str, full: bool = False) -> dict:
    run = require_running(settings, run_id)
    table = load(settings.contracts)[entity]
    existing = next(
        (row for row in table_records(settings, run_id) if row["entity"] == entity), None
    )
    if existing:
        return {"entity": entity, "extracted": existing["extracted"]}
    previous = checkpoint(settings, entity)
    lower = datetime(1970, 1, 1, tzinfo=timezone.utc)
    if previous and not full:
        lower = previous["watermark"] - timedelta(hours=settings.lookback_hours)
    extractor: BaseExtractor
    if table.source == "postgres":
        extractor = PostgresExtractor(settings)
    elif table.source == "api":
        extractor = ApiExtractor(settings)
    else:
        extractor = CsvExtractor(settings)
    rows = extractor.extract(table, lower, run["cutoff"])
    fixture = settings.data_dir / "fixtures" / f"{entity}.jsonl"
    if os.getenv("INJECT_DQ_FIXTURES", "false").lower() == "true" and fixture.exists():
        rows.extend(json.loads(line) for line in fixture.read_text().splitlines() if line)
    key = f"bronze/{entity}/ingest_date={run['logical_date']}/run_id={run_id}/attempt={uuid.uuid4().hex}/data.parquet"
    Lake(settings).write_bronze(key, rows, entity, run_id, run["started_at"])
    with connect(settings) as conn:
        conn.execute(
            """INSERT INTO control.table_runs(run_id,entity,bronze_key,extracted) VALUES(%s,%s,%s,%s)
          ON CONFLICT(run_id,entity) DO UPDATE SET bronze_key=excluded.bronze_key,extracted=excluded.extracted""",
            (run_id, entity, key, len(rows)),
        )
    return {"entity": entity, "extracted": len(rows)}


def ingest(settings: Settings, run_id: str, full: bool = False) -> None:
    totals = source_totals(settings)
    with connect(settings) as conn:
        conn.execute(
            "UPDATE control.runs SET source_orders=%s,source_revenue=%s WHERE run_id=%s",
            (totals["orders"], totals["revenue"], run_id),
        )
    for entity in load(settings.contracts):
        ingest_table(settings, run_id, entity, full)
