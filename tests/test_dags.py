"""DAG import test runs inside the optional Airflow environment."""

import importlib.util

import pytest


def test_dags_import():
    if importlib.util.find_spec("airflow") is None:
        pytest.skip("Run inside the Airflow image")
    from airflow.models import DagBag

    from shoplakehouse.settings import ROOT

    bag = DagBag(dag_folder=str(ROOT / "dags"), include_examples=False)
    assert bag.import_errors == {}
    assert {
        "master_pipeline",
        "ingest_bronze_daily",
        "transform_silver_daily",
        "build_gold_dbt",
        "maintenance",
    } <= set(bag.dags)
