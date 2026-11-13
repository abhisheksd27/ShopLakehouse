.PHONY: setup up down migrate generate-data run test lint typecheck format airflow metabase status tf-init tf-plan tf-apply tf-destroy
PYTHON := .venv/bin/python
CLI := .venv/bin/shoplakehouse
setup:
	python3.11 -m venv .venv
	$(PYTHON) -m pip install -e '.[dev]'
	$(PYTHON) scripts/setup_env.py
up:
	$(PYTHON) scripts/build_image.py --minio
	$(PYTHON) scripts/build_image.py
	docker compose up -d --no-build --wait source-postgres analytics-postgres minio product-api
	docker compose run --rm pipeline init-lake
down:
	docker compose down
migrate:
	docker compose run --rm pipeline migrate
generate-data:
	docker compose run --rm pipeline generate --mode initial --day $(or $(DAY),$(shell date +%F)) --orders $(or $(ORDERS),100)
run:
	docker compose run --rm pipeline run --day $(or $(DAY),$(shell date +%F))
status:
	docker compose run --rm pipeline status
test:
	$(PYTHON) -m pytest -m 'not integration and not spark'
test-integration:
	$(PYTHON) -m pytest -m integration
test-spark:
	$(PYTHON) -m pytest -m spark
lint:
	.venv/bin/ruff check src tests scripts dags
	.venv/bin/black --check src tests scripts dags
	.venv/bin/sqlfluff lint sql/analytics/queries --rules LT12
dbt-run:
	docker compose run --rm pipeline stage gold --run-id $(RUN_ID)
typecheck:
	.venv/bin/mypy src/shoplakehouse
format:
	.venv/bin/ruff check --fix src tests scripts dags
	.venv/bin/black src tests scripts dags
airflow:
	$(PYTHON) scripts/build_image.py --airflow
	docker compose --profile orchestration up -d --no-build
metabase:
	docker compose --profile bi up -d --wait metabase
tf-init:
	terraform -chdir=infra/environments/$(or $(ENV),dev) init
tf-plan:
	terraform -chdir=infra/environments/$(or $(ENV),dev) plan -out=plan.tfplan
tf-apply:
	terraform -chdir=infra/environments/$(or $(ENV),dev) apply plan.tfplan
tf-destroy:
	terraform -chdir=infra/environments/$(or $(ENV),dev) destroy
