#!/usr/bin/env bash
set -euo pipefail
airflow db migrate
if ! airflow users list --output json | python -c 'import json,sys; sys.exit(0 if any(u["username"]=="admin" for u in json.load(sys.stdin)) else 1)'; then
    airflow users create --username admin --firstname Local --lastname Admin \
      --role Admin --email admin@example.test --password "$AIRFLOW_ADMIN_PASSWORD"
fi
airflow pools set shoplakehouse 2 "Bounded local pipeline concurrency"
