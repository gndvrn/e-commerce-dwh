"""
dag_dbt_run.py

DAG 3 of 3: dbt transformations (staging → core dims/facts → data marts).
Runs hourly, 20 minutes after the extract DAG. Waits for the load DAG to
finish, then executes `dbt run` to build all models in dependency order:
  staging views → core dimensions → core facts → datamarts.

Owner : dwh-team
Tags  : dbt, transform, datamart
"""
import os
from datetime import datetime, timedelta

from airflow import DAG
from airflow.operators.bash import BashOperator
from airflow.sensors.external_task import ExternalTaskSensor

DBT_PROJECT_DIR = "/opt/dbt_click"
DBT_PROFILES_DIR = "/opt/dbt_click"

# dbt profiles.yml uses env_var('CLICKHOUSE_USER') / env_var('CLICKHOUSE_PASSWORD').
# Use the same POSTGRES-style pattern as extract/load DAGs: Docker Compose injects
# CLICKHOUSE_* into Airflow services. Relying on Airflow Connection 'clickhouse_conn'
# breaks when the metadata DB has no connections (empty after init).
# BashOperator env= without append_env replaces the whole environment and drops PATH
# (so `dbt` in ~/.local/bin is not found); append_env=True merges with os.environ.
_DBT_CLICKHOUSE_ENV = {
    "CLICKHOUSE_USER": os.environ.get("CLICKHOUSE_USER", ""),
    "CLICKHOUSE_PASSWORD": os.environ.get("CLICKHOUSE_PASSWORD", ""),
}

default_args = {
    "owner": "dwh-team",
    "retries": 1,
    "retry_delay": timedelta(minutes=10),
    "email_on_failure": False,
}

with DAG(
    dag_id="dag_dbt_run",
    description="Run dbt transformations: staging → core (dims + facts) → data marts",
    start_date=datetime(2024, 1, 1),
    schedule_interval="20 * * * *",   # hourly, 20 min after extract
    catchup=False,
    default_args=default_args,
    tags=["dbt", "transform", "datamart"],
    max_active_runs=1,
) as dag:

    wait_for_load = ExternalTaskSensor(
        task_id="wait_for_load_dag",
        external_dag_id="dag_load_to_clickhouse",
        external_task_id=None,
        allowed_states=["success"],
        # load DAG logical_date is HH:10; dbt is HH:20 → offset 10 minutes (not 20)
        execution_delta=timedelta(minutes=10),
        timeout=3600,
        poke_interval=60,
        mode="reschedule",
    )

    dbt_run_staging = BashOperator(
        task_id="dbt_run_staging",
        bash_command=(
            f"dbt run --select staging "
            f"--project-dir {DBT_PROJECT_DIR} "
            f"--profiles-dir {DBT_PROFILES_DIR} "
            f"--target prod"
        ),
        env=_DBT_CLICKHOUSE_ENV,
        append_env=True,
    )

    dbt_run_core = BashOperator(
        task_id="dbt_run_core",
        bash_command=(
            f"dbt run --select core "
            f"--project-dir {DBT_PROJECT_DIR} "
            f"--profiles-dir {DBT_PROFILES_DIR} "
            f"--target prod"
        ),
        env=_DBT_CLICKHOUSE_ENV,
        append_env=True,
    )

    dbt_run_datamart = BashOperator(
        task_id="dbt_run_datamart",
        bash_command=(
            f"dbt run --select datamart "
            f"--project-dir {DBT_PROJECT_DIR} "
            f"--profiles-dir {DBT_PROFILES_DIR} "
            f"--target prod"
        ),
        env=_DBT_CLICKHOUSE_ENV,
        append_env=True,
    )

    dbt_test = BashOperator(
        task_id="dbt_test",
        bash_command=(
            f"dbt test "
            f"--project-dir {DBT_PROJECT_DIR} "
            f"--profiles-dir {DBT_PROFILES_DIR} "
            f"--target prod"
        ),
        env=_DBT_CLICKHOUSE_ENV,
        append_env=True,
    )

    # Linear: wait → staging → core → datamart → test
    wait_for_load >> dbt_run_staging >> dbt_run_core >> dbt_run_datamart >> dbt_test
