#!/usr/bin/env bash
# dbt_test.sh – run dbt tests, optionally scoped to a selector.
set -euo pipefail

DBT_PROJECT_DIR="${DBT_PROJECT_DIR:-/opt/dbt_click}"
DBT_PROFILES_DIR="${DBT_PROFILES_DIR:-/opt/dbt_click}"
SELECT="${1:-}"

if [ -n "$SELECT" ]; then
  dbt test --select "$SELECT" \
    --project-dir "$DBT_PROJECT_DIR" --profiles-dir "$DBT_PROFILES_DIR"
else
  dbt test \
    --project-dir "$DBT_PROJECT_DIR" --profiles-dir "$DBT_PROFILES_DIR"
fi
