"""
dag_load_to_clickhouse.py

DAG 2 of 3: Staging (MinIO) → ClickHouse raw staging tables.
Runs hourly, 10 minutes after the extract DAG. Reads today's parquet files
from MinIO and inserts them into the corresponding ClickHouse staging tables.
Uses ExternalTaskSensor to wait for the extract DAG to finish.

Owner : dwh-team
Tags  : etl, load, clickhouse
"""
import os
from datetime import datetime, timedelta

from airflow import DAG
from airflow.operators.python import PythonOperator
from airflow.sensors.external_task import ExternalTaskSensor

import boto3
from botocore.config import Config

# ---------------------------------------------------------------------------
# Mapping: (source, table) → ClickHouse staging table name
# ---------------------------------------------------------------------------

STAGING_TABLES = {
    "web": [
        ("categories",  "raw_web_categories"),
        ("products",    "raw_web_products"),
        ("users",       "raw_web_users"),
        ("sessions",    "raw_web_sessions"),
        ("carts",       "raw_web_carts"),
        ("cart_items",  "raw_web_cart_items"),
        ("orders",      "raw_web_orders"),
        ("order_items", "raw_web_order_items"),
    ],
    "oms": [
        ("oms_orders", "raw_oms_orders"),
        ("shipments",  "raw_oms_shipments"),
        ("returns",    "raw_oms_returns"),
    ],
    "wms": [
        ("wms_products",        "raw_wms_products"),
        ("inventory",           "raw_wms_inventory"),
        ("inventory_movements", "raw_wms_inventory_movements"),
        ("picking_tasks",       "raw_wms_picking_tasks"),
    ],
    "marketing": [
        ("traffic_sources",          "raw_marketing_traffic_sources"),
        ("ad_campaigns",             "raw_marketing_ad_campaigns"),
        ("ad_campaign_daily_stats",  "raw_marketing_ad_campaign_daily_stats"),
        ("visits",                   "raw_marketing_visits"),
        ("page_events",              "raw_marketing_page_events"),
    ],
}

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _get_s3_client():
    return boto3.client(
        "s3",
        endpoint_url="http://minio:9000",
        aws_access_key_id=os.environ["MINIO_ROOT_USER"],
        aws_secret_access_key=os.environ["MINIO_ROOT_PASSWORD"],
        config=Config(signature_version="s3v4"),
        region_name="us-east-1",
    )


def _get_ch_client():
    from etl_utils import get_clickhouse_client
    return get_clickhouse_client(
        host="clickhouse",
        port=8123,
        user=os.environ["CLICKHOUSE_USER"],
        password=os.environ["CLICKHOUSE_PASSWORD"],
    )


def _get_bucket() -> str:
    return os.environ.get("MINIO_PROD_BUCKET_NAME", "dwh-prod")


# ---------------------------------------------------------------------------
# Task callable
# ---------------------------------------------------------------------------

def load_source_to_clickhouse(source: str, **context) -> None:
    """Download parquet files for a source and insert into ClickHouse staging."""
    from etl_utils import download_parquet_from_s3, load_dataframe_to_clickhouse, build_s3_key, list_s3_keys

    ds = context["ds"]
    s3 = _get_s3_client()
    ch = _get_ch_client()
    bucket = _get_bucket()
    tables = STAGING_TABLES[source]

    for table, ch_table in tables:
        key = build_s3_key(source=source, table=table, ds=ds)

        # Check object exists before downloading
        try:
            s3.head_object(Bucket=bucket, Key=key)
        except Exception:
            # Also try listing all keys for this table (might have multiple files)
            prefix = f"{source}/{table}/"
            keys = list_s3_keys(s3, bucket, prefix)
            if not keys:
                continue
            # Load all available files for this table
            for k in keys:
                try:
                    df = download_parquet_from_s3(s3, bucket, k)
                    load_dataframe_to_clickhouse(df, ch, database="staging", table=ch_table)
                except Exception as exc:
                    import logging
                    logging.getLogger(__name__).warning("Skipping %s: %s", k, exc)
            continue

        df = download_parquet_from_s3(s3, bucket, key)
        load_dataframe_to_clickhouse(df, ch, database="staging", table=ch_table)


# ---------------------------------------------------------------------------
# DAG definition
# ---------------------------------------------------------------------------

default_args = {
    "owner": "dwh-team",
    "retries": 3,
    "retry_delay": timedelta(minutes=5),
    "email_on_failure": False,
}

with DAG(
    dag_id="dag_load_to_clickhouse",
    description="Load parquet files from MinIO staging into ClickHouse raw tables",
    start_date=datetime(2024, 1, 1),
    schedule_interval="10 * * * *",  # hourly, 10 min after extract
    catchup=False,
    default_args=default_args,
    tags=["etl", "load", "clickhouse"],
    max_active_runs=1,
) as dag:

    wait_for_extract = ExternalTaskSensor(
        task_id="wait_for_extract_dag",
        external_dag_id="dag_extract_to_s3",
        external_task_id=None,        # wait for the whole DAG run
        allowed_states=["success"],
        execution_delta=timedelta(minutes=10),
        timeout=3600,
        poke_interval=60,
        mode="reschedule",
    )

    load_web = PythonOperator(
        task_id="load_web",
        python_callable=load_source_to_clickhouse,
        op_kwargs={"source": "web"},
    )

    load_oms = PythonOperator(
        task_id="load_oms",
        python_callable=load_source_to_clickhouse,
        op_kwargs={"source": "oms"},
    )

    load_wms = PythonOperator(
        task_id="load_wms",
        python_callable=load_source_to_clickhouse,
        op_kwargs={"source": "wms"},
    )

    load_marketing = PythonOperator(
        task_id="load_marketing",
        python_callable=load_source_to_clickhouse,
        op_kwargs={"source": "marketing"},
    )

    # Wait for extract, then load all sources in parallel
    wait_for_extract >> [load_web, load_oms, load_wms, load_marketing]
