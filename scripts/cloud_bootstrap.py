"""Run once as an ECS task with the RDS bootstrap credentials."""

import base64
import json
import os
import secrets

import boto3
from psycopg import sql

from shoplakehouse.database import connect, migrate
from shoplakehouse.settings import Settings

settings = Settings()
with connect(settings, True, autocommit=True) as conn:
    for name in ("shoplakehouse_analytics", "airflow", "metabase"):
        if not conn.execute("SELECT 1 FROM pg_database WHERE datname=%s", (name,)).fetchone():
            conn.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(name)))
secret_id = os.environ["APPLICATION_SECRET_ARN"]
client = boto3.client("secretsmanager", region_name=settings.region)
try:
    client.get_secret_value(SecretId=secret_id)
except client.exceptions.ResourceNotFoundException:
    values = {
        key: secrets.token_hex(32)
        for key in (
            "pii_hash_key",
            "api_token",
            "airflow_admin_password",
            "airflow_webserver_secret_key",
        )
    }
    values["airflow_fernet_key"] = base64.urlsafe_b64encode(os.urandom(32)).decode()
    client.put_secret_value(SecretId=secret_id, SecretString=json.dumps(values))
migrate(settings)
print("Cloud database schemas and application secrets initialized; no secret values printed")
