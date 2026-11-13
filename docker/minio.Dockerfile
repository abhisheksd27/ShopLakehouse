# Official upstream source; retained locally for development only (AGPL-3.0).
FROM golang:1.24.2-bookworm AS build
ARG MINIO_VERSION=RELEASE.2025-04-22T22-12-26Z
RUN git clone --depth 1 --branch "$MINIO_VERSION" https://github.com/minio/minio.git /src
WORKDIR /src
RUN CGO_ENABLED=0 go build -trimpath -o /minio .
FROM python:3.11.15-slim-bookworm
RUN sed -i 's|http://deb.debian.org|https://deb.debian.org|g' /etc/apt/sources.list.d/debian.sources \
    && apt-get -o Acquire::Retries=5 update \
    && apt-get -o Acquire::Retries=5 install -y --no-install-recommends ca-certificates curl \
    && rm -rf /var/lib/apt/lists/*
COPY --from=build /minio /usr/local/bin/minio
COPY --from=build /src/LICENSE /usr/share/licenses/minio/LICENSE
LABEL org.opencontainers.image.source="https://github.com/minio/minio" \
      org.opencontainers.image.version="RELEASE.2025-04-22T22-12-26Z" \
      org.opencontainers.image.licenses="AGPL-3.0"
EXPOSE 9000 9001
ENTRYPOINT ["minio"]
