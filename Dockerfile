FROM python:3.11.15-slim-bookworm
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 \
    JAVA_HOME=/usr/lib/jvm/java-17-openjdk-arm64 \
    SPARK_LOCAL_IP=127.0.0.1 GX_ANALYTICS_ENABLED=false SHOPLAKEHOUSE_ROOT=/app
RUN sed -i 's|http://deb.debian.org|https://deb.debian.org|g' /etc/apt/sources.list.d/debian.sources \
    && apt-get -o Acquire::Retries=5 update && apt-get -o Acquire::Retries=5 install -y --no-install-recommends openjdk-17-jre-headless curl \
    && rm -rf /var/lib/apt/lists/* \
    && ln -s "$(dirname "$(dirname "$(readlink -f "$(command -v java)")")")" /opt/java
ENV JAVA_HOME=/opt/java
WORKDIR /app
COPY pyproject.toml README.md ./
ARG INSTALL_CLOUD=false
RUN python -c 'import os,subprocess,tomllib; p=tomllib.load(open("pyproject.toml","rb"))["project"]; deps=p["dependencies"]+(p["optional-dependencies"]["cloud"] if os.environ.get("INSTALL_CLOUD")=="true" else []); subprocess.check_call(["pip","install","--no-cache-dir",*deps])' \
    && useradd --create-home --uid 10001 app
COPY src ./src
RUN pip install --no-deps .
COPY config ./config
COPY sql ./sql
COPY dbt ./dbt
COPY scripts ./scripts
RUN mkdir -p data artifacts && chown -R app:app /app
USER app
ENTRYPOINT ["shoplakehouse"]
CMD ["--help"]
