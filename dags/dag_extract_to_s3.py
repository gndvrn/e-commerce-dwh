"""
dag_extract_to_s3.py

DAG 1 of 3: Extract → Staging (MinIO)
Runs hourly. For each source schema (web, oms, wms, marketing), reads all
configured tables incrementally (watermark from metadata.s3_max_dates) and
uploads raw parquet files to MinIO.

Owner : dwh-team
Tags  : etl, extract, s3
"""
import os
from datetime import datetime, timedelta

from airflow import DAG
from airflow.operators.python import PythonOperator

import boto3
import pandas as pd
from botocore.config import Config

# ---------------------------------------------------------------------------
# Table configuration: source schema → list of (table, timestamp_col)
# ---------------------------------------------------------------------------

SOURCE_TABLES = {
    "web": [
        ("categories",  "created_at"),
        ("products",    "created_at"),
        ("users",       "registered_at"),
        ("sessions",    "started_at"),
        ("carts",       "updated_at"),
        ("cart_items",  "created_at"),
        ("orders",      "created_at"),
        ("order_items", "created_at"),
    ],
    "oms": [
        ("oms_orders", "received_at"),
        ("shipments",  "created_at"),
        ("returns",    "created_at"),
    ],
    "wms": [
        ("wms_products",          "created_at"),
        ("inventory",             "updated_at"),
        ("inventory_movements",   "created_at"),
        ("picking_tasks",         "created_at"),
    ],
    "marketing": [
        ("traffic_sources",           "created_at"),
        ("ad_campaigns",              "created_at"),
        ("ad_campaign_daily_stats",   "created_at"),
        ("visits",                    "visited_at"),
        ("page_events",               "event_at"),
    ],
}

# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

def _get_pg_dsn() -> str:
    user = os.environ["POSTGRES_USER"]
    pw = os.environ["POSTGRES_PASSWORD"]
    db = os.environ.get("POSTGRES_DB", "airflow")
    return f"host=postgres port=5432 user={user} password={pw} dbname={db}"


def _get_s3_client():
    return boto3.client(
        "s3",
        endpoint_url="http://minio:9000",
        aws_access_key_id=os.environ["MINIO_ROOT_USER"],
        aws_secret_access_key=os.environ["MINIO_ROOT_PASSWORD"],
        config=Config(signature_version="s3v4"),
        region_name="us-east-1",
    )


def _get_bucket() -> str:
    return os.environ.get("MINIO_PROD_BUCKET_NAME", "dwh-prod")


# ---------------------------------------------------------------------------
# Task callable
# ---------------------------------------------------------------------------

def extract_source(source: str, **context) -> None:
    """Extract all tables for one source schema to MinIO."""
    from etl_utils import (
        extract_table_incremental,
        upload_dataframe_to_s3,
        build_s3_key,
        get_watermark,
        set_watermark,
    )

    ds = context["ds"]           # execution date string YYYY-MM-DD
    dsn = _get_pg_dsn()
    s3  = _get_s3_client()
    bucket = _get_bucket()
    tables = SOURCE_TABLES[source]

    for table, ts_col in tables:
        table_key = f"{source}.{table}"
        watermark = get_watermark(table_key, init_date="2020-01-01")

        df = extract_table_incremental(
            dsn=dsn,
            schema=source,
            table=table,
            timestamp_col=ts_col,
            watermark=watermark,
        )

        if df.empty:
            continue

        # ClickHouse DateTime is naive; strip tz from Postgres timestamptz for Parquet/CH
        for col in df.select_dtypes(include=["datetimetz"]).columns:
            df[col] = pd.to_datetime(df[col], utc=True).dt.tz_localize(None)

        key = build_s3_key(source=source, table=table, ds=ds)
        upload_dataframe_to_s3(df, s3_client=s3, bucket=bucket, key=key)

        # Update watermark to the max timestamp found in this batch
        max_ts = df[ts_col].max()
        if max_ts:
            set_watermark(table_key, str(max_ts)[:10])


# ---------------------------------------------------------------------------
# DAG definition
# ---------------------------------------------------------------------------

default_args = {
    "owner": "dwh-team",
    "retries": 2,
    "retry_delay": timedelta(minutes=5),
    "email_on_failure": False,
}

with DAG(
    dag_id="dag_extract_to_s3",
    description="Incremental extract from OLTP sources to MinIO staging layer",
    start_date=datetime(2024, 1, 1),
    schedule_interval="0 * * * *",   # hourly
    catchup=False,
    default_args=default_args,
    tags=["etl", "extract", "s3"],
    max_active_runs=1,
) as dag:

    extract_web = PythonOperator(
        task_id="extract_web",
        python_callable=extract_source,
        op_kwargs={"source": "web"},
    )

    extract_oms = PythonOperator(
        task_id="extract_oms",
        python_callable=extract_source,
        op_kwargs={"source": "oms"},
    )

    extract_wms = PythonOperator(
        task_id="extract_wms",
        python_callable=extract_source,
        op_kwargs={"source": "wms"},
    )

    extract_marketing = PythonOperator(
        task_id="extract_marketing",
        python_callable=extract_source,
        op_kwargs={"source": "marketing"},
    )

    # All four sources run in parallel – no dependencies between them
    [extract_web, extract_oms, extract_wms, extract_marketing]
