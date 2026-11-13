"""Environment configuration; credentials are never included in repr/logs."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv
from psycopg.conninfo import make_conninfo

ROOT = Path(os.getenv("SHOPLAKEHOUSE_ROOT", str(Path(__file__).resolve().parents[2])))
load_dotenv(ROOT / ".env", override=False)


@dataclass(frozen=True)
class Settings:
    region: str = field(default_factory=lambda: os.getenv("AWS_DEFAULT_REGION", "ap-south-1"))
    bucket: str = field(default_factory=lambda: os.getenv("LAKE_BUCKET", "shoplakehouse-local"))
    endpoint: str | None = field(default_factory=lambda: os.getenv("S3_ENDPOINT_URL") or None)
    api_url: str = field(
        default_factory=lambda: os.getenv("PRODUCT_API_URL", "http://localhost:8000")
    )
    api_token: str = field(default_factory=lambda: os.getenv("API_TOKEN", ""), repr=False)
    pii_key: str = field(default_factory=lambda: os.getenv("PII_HASH_KEY", ""), repr=False)
    warehouse: str = field(default_factory=lambda: os.getenv("WAREHOUSE_ENGINE", "postgres"))
    lookback_hours: int = field(default_factory=lambda: int(os.getenv("LOOKBACK_HOURS", "168")))
    max_rejected: int = field(default_factory=lambda: int(os.getenv("MAX_REJECTED_ROWS", "0")))
    data_dir: Path = field(default_factory=lambda: Path(os.getenv("DATA_DIR", str(ROOT / "data"))))
    contracts: Path = field(
        default_factory=lambda: Path(os.getenv("CONTRACTS_PATH", str(ROOT / "config/tables.yml")))
    )

    def dsn(self, source: bool = False) -> str:
        prefix = "SOURCE" if source else "ANALYTICS"
        defaults = (
            ("shoplakehouse", "shop_admin", "5433")
            if source
            else ("shoplakehouse_analytics", "analytics_admin", "5434")
        )
        password = os.getenv(f"{prefix}_DB_PASSWORD", "")
        if not password:
            raise ValueError(f"{prefix}_DB_PASSWORD must be set")
        return make_conninfo(
            host=os.getenv(f"{prefix}_DB_HOST", "localhost"),
            port=os.getenv(f"{prefix}_DB_PORT", defaults[2]),
            dbname=os.getenv(f"{prefix}_DB_NAME", defaults[0]),
            user=os.getenv(f"{prefix}_DB_USER", defaults[1]),
            password=password,
            sslmode=os.getenv(f"{prefix}_DB_SSLMODE", "prefer"),
            connect_timeout=10,
        )
