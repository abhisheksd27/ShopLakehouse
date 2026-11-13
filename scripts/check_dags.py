"""Import every packaged DAG using Airflow's own interpreter."""

from airflow.models import DagBag

bag = DagBag(dag_folder="/opt/airflow/dags", include_examples=False)
assert not bag.import_errors, bag.import_errors
expected = {
    "master_pipeline",
    "ingest_bronze_daily",
    "transform_silver_daily",
    "build_gold_dbt",
    "maintenance",
}
assert expected <= set(bag.dags), set(bag.dags)
master = bag.dags["master_pipeline"]
assert master.max_active_runs == 1
assert master.get_task("silver").pool == "shoplakehouse"
assert master.get_task("publish").upstream_task_ids == {"gold"}
print("Five DAGs imported; concurrency and publication dependencies verified")
