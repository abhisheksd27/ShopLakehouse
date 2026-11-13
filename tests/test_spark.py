import hashlib
import json

import pytest

from shoplakehouse.contracts import load
from shoplakehouse.settings import ROOT
from shoplakehouse.silver import parse_and_validate, protect, spark_session

pytestmark = pytest.mark.spark


@pytest.fixture(scope="module")
def spark():
    session = spark_session()
    yield session
    session.stop()


def bronze(spark, rows):
    payloads = [json.dumps(row, sort_keys=True) for row in rows]
    return spark.createDataFrame(
        [
            (
                payload,
                "products",
                "run",
                "2026-11-12T00:00:00+00:00",
                hashlib.sha256(payload.encode()).hexdigest(),
            )
            for payload in payloads
        ],
        ["payload", "_source", "_batch_id", "_ingested_at", "_record_hash"],
    )


def test_typing_dedup_and_quarantine_accounting(spark):
    table = load(ROOT / "config/tables.yml")["products"]
    row = {
        "id": 1,
        "category_id": 1,
        "sku": "A",
        "name": "Product",
        "price": "100.00",
        "stock_quantity": 3,
        "created_at": "2026-01-01T00:00:00Z",
        "updated_at": "2026-01-01T00:00:00Z",
    }
    invalid = dict(row, id=2, sku="B", price="-1.00")
    good, bad, duplicates = parse_and_validate(bronze(spark, [row, row, invalid]), table)
    assert good.count() == 1
    assert bad.count() == 1
    assert duplicates == 1
    assert "price_nonnegative" in bad.first()["reject_reason"]


def test_newest_version_wins(spark):
    table = load(ROOT / "config/tables.yml")["product_api"]
    old = {
        "id": 1,
        "sku": "A",
        "brand": "old",
        "material": "metal",
        "updated_at": "2026-01-01T00:00:00Z",
    }
    new = dict(old, brand="new", updated_at="2026-01-02T00:00:00Z")
    good, bad, duplicates = parse_and_validate(bronze(spark, [new, old]), table)
    assert good.first()["brand"] == "new"
    assert bad.count() == 0
    assert duplicates == 1


def test_pii_is_hmac_and_sensitive_columns_removed(spark):
    table = load(ROOT / "config/tables.yml")["customers"]
    df = spark.createDataFrame([(" Test Name ", "TEST@EXAMPLE.TEST")], ["name", "email"])
    first = protect(df, table, "a" * 64).first()
    second = protect(df, table, "b" * 64).first()
    assert len(first["email"]) == 64
    assert first["email"] != second["email"]
    assert first["name"] != " Test Name "
    address = load(ROOT / "config/tables.yml")["addresses"]
    cleaned = protect(
        spark.createDataFrame(
            [("street", "line2", "560001", "Bengaluru")],
            ["address_line1", "address_line2", "postal_code", "city"],
        ),
        address,
        "a" * 64,
    )
    assert cleaned.columns == ["city"]


@pytest.mark.parametrize("entity", ["orders", "payments"])
def test_indian_currency_is_inr_not_country_code(spark, entity):
    table = load(ROOT / "config/tables.yml")[entity]
    row = {
        "id": 1,
        "currency": "INR",
        "created_at": "2026-01-01T00:00:00Z",
        "updated_at": "2026-01-01T00:00:00Z",
    }
    if entity == "orders":
        row.update(
            customer_id=1, ordered_at=row["created_at"], status="delivered", total_amount="100.00"
        )
    else:
        row.update(
            order_id=1,
            payment_reference="test",
            transaction_type="payment",
            payment_method="upi",
            status="succeeded",
            amount="100.00",
            processed_at=row["created_at"],
        )
    good, bad, _ = parse_and_validate(bronze(spark, [row, dict(row, id=2, currency="IN")]), table)
    assert good.count() == 1
    assert good.first()["currency"] == "INR"
    assert bad.count() == 1
    assert "currency_valid" in bad.first()["reject_reason"]
