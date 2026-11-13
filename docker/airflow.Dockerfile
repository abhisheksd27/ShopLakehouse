FROM apache/airflow:2.11.2-python3.11
USER root
RUN apt-get update && apt-get install -y --no-install-recommends openjdk-17-jre-headless python3-venv \
    && rm -rf /var/lib/apt/lists/* \
    && ln -s "$(dirname "$(dirname "$(readlink -f "$(command -v java)")")")" /opt/java
ENV JAVA_HOME=/opt/java SPARK_LOCAL_IP=127.0.0.1 GX_ANALYTICS_ENABLED=false SHOPLAKEHOUSE_ROOT=/opt/shoplakehouse
RUN python -m venv /opt/pipeline && chown -R airflow:root /opt/pipeline
WORKDIR /opt/shoplakehouse
RUN chown airflow:root /opt/shoplakehouse
COPY --chown=airflow:root pyproject.toml README.md ./
USER airflow
ARG INSTALL_CLOUD=false
RUN /opt/pipeline/bin/python -c 'import os,subprocess,tomllib; p=tomllib.load(open("pyproject.toml","rb"))["project"]; deps=p["dependencies"]+(p["optional-dependencies"]["cloud"] if os.environ.get("INSTALL_CLOUD")=="true" else []); subprocess.check_call(["/opt/pipeline/bin/pip","install","--no-cache-dir",*deps])'
COPY --chown=airflow:root src ./src
RUN /opt/pipeline/bin/pip install --no-deps .
COPY --chown=airflow:root config ./config
COPY --chown=airflow:root sql ./sql
COPY --chown=airflow:root dbt ./dbt
COPY --chown=airflow:root scripts ./scripts
COPY --chown=airflow:root dags /opt/airflow/dags
RUN mkdir -p data artifacts
ENV SHOPLAKEHOUSE_CLI=/opt/pipeline/bin/shoplakehouse
