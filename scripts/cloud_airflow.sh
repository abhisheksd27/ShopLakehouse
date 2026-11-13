#!/usr/bin/env bash
set -euo pipefail
export AIRFLOW__DATABASE__SQL_ALCHEMY_CONN="$(python -c 'import os; from urllib.parse import quote; print("postgresql+psycopg2://"+quote(os.environ["SOURCE_DB_USER"],safe="")+":"+quote(os.environ["SOURCE_DB_PASSWORD"],safe="")+"@"+os.environ["SOURCE_DB_HOST"]+":5432/airflow")')"
if [ "${1:-}" = init ]; then
    exec bash /opt/shoplakehouse/scripts/airflow_init.sh
fi
exec /entrypoint "$@"
