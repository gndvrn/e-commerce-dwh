FROM apache/superset:latest

USER root

# Образ apache/superset собирают через `uv venv /app/.venv` — там нет обычного pip.
# Системный `pip`/чужой site-packages не подходят: Superset выполняется из этого venv.
# Доп. пакеты ставим так же, как upstream: `uv pip install --python …`.
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libssl-dev \
    libffi-dev \
    python3-dev \
    pkg-config \
    default-libmysqlclient-dev \
    curl \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

RUN uv pip install --python /app/.venv/bin/python --no-cache \
    "clickhouse-connect>=0.13.0" \
    mysqlclient

ENV ADMIN_USERNAME=${ADMIN_USERNAME}
ENV ADMIN_EMAIL=${ADMIN_EMAIL}
ENV ADMIN_PASSWORD=${ADMIN_PASSWORD}
ENV EXECUTOR=Local

COPY ./superset-init.sh /superset-init.sh
COPY superset_config.py /app/
COPY superset.db /app/superset_home/superset.db
ENV SUPERSET_LOAD_EXAMPLES=no
ENV SUPERSET_CONFIG_PATH /app/superset_config.py

RUN chmod +x /superset-init.sh

USER superset
ENTRYPOINT [ "/superset-init.sh" ]
