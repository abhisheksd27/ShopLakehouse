from datetime import datetime, timezone
from decimal import Decimal
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest
from fastapi.testclient import TestClient
from moto import mock_aws

from shoplakehouse.api import app
from shoplakehouse.contracts import load
from shoplakehouse.database import identifier
from shoplakehouse.errors import DataQualityError
from shoplakehouse.ingestion import ingest_table
from shoplakehouse.quality import validate_snapshot
from shoplakehouse.settings import ROOT, Settings
from shoplakehouse.storage import Lake, canonical
from shoplakehouse.warehouse import publish


def test_contracts_cover_every_source():
    tables = load(ROOT / "config/tables.yml")
    assert len(tables) == 12
    assert len([t for t in tables.values() if t.source == "postgres"]) == 9
    assert tables["customers"].pii == ("name", "email")
    assert "review_text" not in tables["reviews"].silver_columns


def test_money_and_timestamps_are_lossless_in_bronze():
    payload = canonical(
        {
            "amount": Decimal("1234567890123456.78"),
            "time": datetime(2026, 1, 1, tzinfo=timezone.utc),
        }
    )
    assert '"1234567890123456.78"' in payload
    assert "+00:00" in payload


def test_identifiers_cannot_inject_sql():
    with pytest.raises(ValueError):
        identifier("orders; drop table customers")


@mock_aws
def test_bronze_roundtrip_and_empty_batch(monkeypatch):
    monkeypatch.setenv("AWS_ACCESS_KEY_ID", "testing")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "testing")
    settings = Settings(endpoint=None, bucket="shoplakehouse-tests", region="us-east-1")
    lake = Lake(settings)
    lake.ensure_bucket()
    now = datetime.now(timezone.utc)
    assert (
        lake.write_bronze(
            "bronze/test.parquet", [{"id": 1, "amount": Decimal("1.25")}], "test", "abc", now
        )
        == 1
    )
    assert (
        lake.parquet("bronze/test.parquet").to_pylist()[0]["payload"] == '{"amount":"1.25","id":1}'
    )
    lake.write_bronze("bronze/empty.parquet", [], "test", "abc", now)
    assert lake.parquet("bronze/empty.parquet").num_rows == 0


def test_failed_object_write_does_not_record_ingestion():
    settings = Settings()
    now = datetime.now(timezone.utc)
    with (
        patch(
            "shoplakehouse.ingestion.require_running",
            return_value={"cutoff": now, "started_at": now, "logical_date": now.date()},
        ),
        patch("shoplakehouse.ingestion.table_records", return_value=[]),
        patch("shoplakehouse.ingestion.checkpoint", return_value=None),
        patch("shoplakehouse.ingestion.PostgresExtractor.extract", return_value=[]),
        patch("shoplakehouse.ingestion.Lake") as lake,
        patch("shoplakehouse.ingestion.connect") as db,
    ):
        lake.return_value.write_bronze.side_effect = OSError("storage unavailable")
        with pytest.raises(OSError):
            ingest_table(settings, "abc", "customers")
        db.assert_not_called()


def test_publish_requires_dbt_success():
    with (
        patch("shoplakehouse.warehouse.require_running", return_value={"gold_validated": False}),
        patch("shoplakehouse.warehouse.connect") as db,
    ):
        with pytest.raises(DataQualityError, match="dbt"):
            publish(Settings(), "abc")
        db.assert_not_called()


def test_gx_rejects_duplicate_primary_keys():
    table = load(ROOT / "config/tables.yml")["product_api"]
    frame = pd.DataFrame(
        [
            {
                "id": 1,
                "sku": "one",
                "brand": "demo",
                "material": "metal",
                "updated_at": "2026-01-01",
            },
            {
                "id": 1,
                "sku": "one",
                "brand": "demo",
                "material": "metal",
                "updated_at": "2026-01-01",
            },
        ]
    )
    with pytest.raises(DataQualityError):
        validate_snapshot(frame, table)


def test_api_requires_token(monkeypatch):
    monkeypatch.setenv("API_TOKEN", "test-token")
    client = TestClient(app)
    assert client.get("/health").status_code == 200
    assert client.get("/products").status_code == 401


def test_api_keyset_pagination(monkeypatch):
    monkeypatch.setenv("API_TOKEN", "test-token")
    monkeypatch.setenv("API_FAILURE_RATE", "0")
    now = datetime.now(timezone.utc)
    connection = MagicMock()
    connection.__enter__.return_value = connection
    connection.execute.side_effect = [
        None,
        [{"id": 1, "sku": "A", "updated_at": now}, {"id": 2, "sku": "B", "updated_at": now}],
    ]
    with patch("shoplakehouse.api.connect", return_value=connection):
        response = TestClient(app).get(
            "/products?limit=1", headers={"Authorization": "Bearer test-token"}
        )
    assert response.status_code == 200
    assert len(response.json()["items"]) == 1
    assert response.json()["next_after_id"] == 1
