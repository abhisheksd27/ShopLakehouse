"""Fill missing local secrets without replacing existing values or printing them."""

import base64
import os
import secrets
from pathlib import Path

root = Path(__file__).resolve().parents[1]
path = root / ".env"
existing = path.read_text().splitlines() if path.exists() else []
values = {}
for line in existing:
    if line and not line.startswith("#") and "=" in line:
        key, value = line.split("=", 1)
        values[key] = value
secret_keys = {
    "SOURCE_DB_PASSWORD",
    "ANALYTICS_DB_PASSWORD",
    "MINIO_ROOT_PASSWORD",
    "PII_HASH_KEY",
    "API_TOKEN",
    "AIRFLOW_DB_PASSWORD",
    "AIRFLOW_ADMIN_PASSWORD",
    "AIRFLOW_WEBSERVER_SECRET_KEY",
    "METABASE_DB_PASSWORD",
    "BI_DB_PASSWORD",
    "METABASE_ADMIN_PASSWORD",
}
for line in (root / ".env.example").read_text().splitlines():
    if not line or line.startswith("#") or "=" not in line:
        continue
    key, default = line.split("=", 1)
    if values.get(key):
        continue
    if key == "AIRFLOW_FERNET_KEY":
        values[key] = base64.urlsafe_b64encode(os.urandom(32)).decode()
    else:
        values[key] = secrets.token_hex(32) if key in secret_keys else default
temp = root / ".env.tmp"
fd = os.open(temp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
with os.fdopen(fd, "w") as handle:
    handle.write("".join(f"{key}={value}\n" for key, value in values.items()))
os.replace(temp, path)
print("Local configuration ready; existing nonempty values preserved. No secrets printed.")
