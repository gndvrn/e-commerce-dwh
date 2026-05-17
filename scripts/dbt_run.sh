#!/usr/bin/env bash
# dbt_run.sh – convenience wrapper called by Airflow BashOperators
# and usable directly inside the Airflow worker container.
#
# Usage:
#   ./scripts/dbt_run.sh [select_arg]
#   e.g.  ./scripts/dbt_run.sh staging
#         ./scripts/dbt_run.sh core
#         ./scripts/dbt_run.sh datamart
#         ./scripts/dbt_run.sh          (runs everything)

set -euo pipefail

DBT_PROJECT_DIR="${DBT_PROJECT_DIR:-/opt/dbt_click}"
DBT_PROFILES_DIR="${DBT_PROFILES_DIR:-/opt/dbt_click}"
DBT_TARGET="${DBT_TARGET:-prod}"
SELECT="${1:-}"

echo "[dbt_run.sh] Project  : $DBT_PROJECT_DIR"
echo "[dbt_run.sh] Profiles : $DBT_PROFILES_DIR"
echo "[dbt_run.sh] Target   : $DBT_TARGET"
echo "[dbt_run.sh] Select   : ${SELECT:-ALL}"

if [ -n "$SELECT" ]; then
  dbt run \
    --select "$SELECT" \
    --project-dir "$DBT_PROJECT_DIR" \
    --profiles-dir "$DBT_PROFILES_DIR" \
    --target "$DBT_TARGET"
else
  dbt run \
    --project-dir "$DBT_PROJECT_DIR" \
    --profiles-dir "$DBT_PROFILES_DIR" \
    --target "$DBT_TARGET"
fi

echo "[dbt_run.sh] Done."
