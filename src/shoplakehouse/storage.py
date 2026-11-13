"""Immutable Parquet objects; a successful write is not yet publication."""

from __future__ import annotations

import hashlib
import io
import json
import os
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

import boto3
import pyarrow as pa
import pyarrow.parquet as pq
from botocore.config import Config
from botocore.exceptions import ClientError
from tenacity import retry, stop_after_attempt, wait_exponential

from .settings import Settings

BRONZE_SCHEMA = pa.schema(
    [
        ("payload", pa.string()),
        ("_source", pa.string()),
        ("_batch_id", pa.string()),
        ("_ingested_at", pa.string()),
        ("_record_hash", pa.string()),
    ]
)


def json_value(value):
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, Decimal):
        return str(value)
    raise TypeError(type(value).__name__)


def canonical(row: dict) -> str:
    return json.dumps(
        row, default=json_value, sort_keys=True, separators=(",", ":"), allow_nan=False
    )


class Lake:
    def __init__(self, settings: Settings):
        self.settings = settings
        kwargs: dict[str, Any] = {
            "region_name": settings.region,
            "config": Config(
                retries={"max_attempts": 5, "mode": "standard"}, s3={"addressing_style": "path"}
            ),
        }
        if settings.endpoint:
            kwargs.update(
                endpoint_url=settings.endpoint,
                aws_access_key_id=os.environ["MINIO_ROOT_USER"],
                aws_secret_access_key=os.environ["MINIO_ROOT_PASSWORD"],
            )
        self.client = boto3.client("s3", **kwargs)

    def ensure_bucket(self) -> None:
        try:
            self.client.head_bucket(Bucket=self.settings.bucket)
        except ClientError as exc:
            if exc.response["Error"]["Code"] not in ("404", "NoSuchBucket"):
                raise
            kwargs: dict[str, Any] = {"Bucket": self.settings.bucket}
            if not self.settings.endpoint and self.settings.region != "us-east-1":
                kwargs["CreateBucketConfiguration"] = {"LocationConstraint": self.settings.region}
            self.client.create_bucket(**kwargs)

    @retry(stop=stop_after_attempt(4), wait=wait_exponential(min=1, max=8), reraise=True)
    def put(self, key: str, data: bytes) -> None:
        self.client.put_object(
            Bucket=self.settings.bucket,
            Key=key,
            Body=data,
            Metadata={"sha256": hashlib.sha256(data).hexdigest()},
        )

    def get(self, key: str) -> bytes:
        result = self.client.get_object(Bucket=self.settings.bucket, Key=key)
        data = result["Body"].read()
        digest = result.get("Metadata", {}).get("sha256")
        if digest and hashlib.sha256(data).hexdigest() != digest:
            raise ValueError("Object checksum mismatch")
        return data

    def download(self, key: str, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(self.get(key))

    def parquet(self, key: str) -> pa.Table:
        return pq.read_table(io.BytesIO(self.get(key)))

    def write_bronze(
        self, key: str, rows: list[dict], entity: str, run_id: str, ingested_at: datetime
    ) -> int:
        records = []
        for row in rows:
            payload = canonical(row)
            records.append(
                {
                    "payload": payload,
                    "_source": entity,
                    "_batch_id": run_id,
                    "_ingested_at": ingested_at.isoformat(),
                    "_record_hash": hashlib.sha256(payload.encode()).hexdigest(),
                }
            )
        data = pa.Table.from_pylist(records, schema=BRONZE_SCHEMA)
        buffer = io.BytesIO()
        pq.write_table(data, buffer, compression="snappy")
        self.put(key, buffer.getvalue())
        return len(records)
