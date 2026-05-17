"""
etl_utils.py – Shared ETL helper functions used by all Airflow DAGs.

Functions are pure or near-pure (accept external clients as arguments)
so they can be unit-tested without running infrastructure.
"""
import io
import logging
from typing import Any, Optional

import pandas as pd
import psycopg2

log = logging.getLogger(__name__)


# ===================================================================
# S3 key naming convention
# ===================================================================

def build_s3_key(source: str, table: str, ds: str) -> str:
    """
    Return the canonical S3/MinIO object key for a daily extract.
    Pattern: {source}/{table}/{ds}/data.parquet
    Example: web/orders/2024-06-01/data.parquet
    """
    return f"{source}/{table}/{ds}/data.parquet"


# ===================================================================
# Extract from Postgres
# ===================================================================

def extract_table_incremental(
    dsn: str,
    schema: str,
    table: str,
    timestamp_col: str,
    watermark: str,
) -> pd.DataFrame:
    """
    Extract all rows from schema.table where timestamp_col > watermark.

    Args:
        dsn:           psycopg2-compatible DSN string.
        schema:        Postgres schema name (e.g. 'web').
        table:         Table name within the schema.
        timestamp_col: Column name used as the incremental watermark.
        watermark:     ISO date/datetime string; only rows newer than this are fetched.

    Returns:
        DataFrame with fetched rows, or empty DataFrame if nothing to fetch.
    """
    sql = f"SELECT * FROM {schema}.{table} WHERE {timestamp_col} > %(watermark)s"
    try:
        with psycopg2.connect(dsn) as conn:
            df = pd.read_sql(sql, conn, params={"watermark": watermark})
        log.info("Extracted %d rows from %s.%s (watermark=%s)", len(df), schema, table, watermark)
        return df
    except Exception as exc:
        log.error("Failed to extract %s.%s: %s", schema, table, exc)
        raise


def extract_table_full(dsn: str, schema: str, table: str) -> pd.DataFrame:
    """Full extract for small reference/lookup tables (categories, products, etc.)."""
    sql = f"SELECT * FROM {schema}.{table}"
    with psycopg2.connect(dsn) as conn:
        df = pd.read_sql(sql, conn)
    log.info("Full extract: %d rows from %s.%s", len(df), schema, table)
    return df


# ===================================================================
# Parquet serialisation
# ===================================================================

def dataframe_to_parquet_bytes(df: pd.DataFrame) -> bytes:
    """Serialize a DataFrame to parquet bytes (in-memory, no disk I/O)."""
    buf = io.BytesIO()
    df.to_parquet(buf, index=False, engine="pyarrow")
    return buf.getvalue()


def parquet_bytes_to_dataframe(data: bytes) -> pd.DataFrame:
    """Deserialize parquet bytes back to a DataFrame."""
    return pd.read_parquet(io.BytesIO(data), engine="pyarrow")


# ===================================================================
# S3 / MinIO operations
# ===================================================================

def upload_dataframe_to_s3(
    df: pd.DataFrame,
    s3_client: Any,
    bucket: str,
    key: str,
) -> None:
    """
    Upload a DataFrame as a parquet object to S3/MinIO.
    Skips upload if DataFrame is empty (avoids 0-byte objects).
    """
    if df.empty:
        log.info("DataFrame is empty – skipping upload to s3://%s/%s", bucket, key)
        return
    data = dataframe_to_parquet_bytes(df)
    s3_client.put_object(Bucket=bucket, Key=key, Body=data)
    log.info("Uploaded %d rows to s3://%s/%s (%d bytes)", len(df), bucket, key, len(data))


def download_parquet_from_s3(
    s3_client: Any,
    bucket: str,
    key: str,
) -> pd.DataFrame:
    """Download a parquet object from S3/MinIO and return as DataFrame."""
    response = s3_client.get_object(Bucket=bucket, Key=key)
    data = response["Body"].read()
    df = parquet_bytes_to_dataframe(data)
    log.info("Downloaded %d rows from s3://%s/%s", len(df), bucket, key)
    return df


def list_s3_keys(s3_client: Any, bucket: str, prefix: str) -> list[str]:
    """List all object keys under the given prefix in a bucket."""
    paginator = s3_client.get_paginator("list_objects_v2")
    keys = []
    for page in paginator.paginate(Bucket=bucket, Prefix=prefix):
        for obj in page.get("Contents", []):
            keys.append(obj["Key"])
    return keys


# ===================================================================
# ClickHouse loading
# ===================================================================

def _coerce_datetime_like_string_columns(df: pd.DataFrame) -> pd.DataFrame:
    """
    clickhouse_connect insert_df expects datetime64 for ClickHouse DateTime columns.
    Parquet from extract may store timestamps as strings (legacy path).
    Blank strings (common for nullable timestamps) must not block conversion of real values.
    """
    out = df.copy()
    for col in out.columns:
        s = out[col]
        if isinstance(s.dtype, pd.CategoricalDtype):
            s = s.astype(object)
        try:
            import pyarrow as pa

            if hasattr(s.dtype, "pyarrow_dtype"):
                t = s.dtype.pyarrow_dtype
                if pa.types.is_timestamp(t) or pa.types.is_date(t):
                    out[col] = pd.to_datetime(s, errors="coerce")
                    continue
        except Exception:
            pass
        if pd.api.types.is_datetime64_any_dtype(s):
            continue
        if not (pd.api.types.is_object_dtype(s) or pd.api.types.is_string_dtype(s)):
            continue

        # Empty / whitespace-only strings are "missing" for datetime purposes but pandas treats "" as notna()
        strv = s.astype(str)
        is_blank = strv.str.strip().str.lower().isin(("", "nan", "none", "<na>", "nat"))

        must_parse = s.notna() & ~is_blank
        if not must_parse.any():
            conv = pd.to_datetime(s, errors="coerce")
            if conv.isna().all():
                continue
            out[col] = conv
            continue

        conv = pd.to_datetime(s, errors="coerce")
        if bool(conv[must_parse].notna().all()):
            out[col] = conv
    return out


def load_dataframe_to_clickhouse(
    df: pd.DataFrame,
    ch_client: Any,
    database: str,
    table: str,
    truncate: bool = False,
) -> int:
    """
    Insert a DataFrame into a ClickHouse staging table.

    Args:
        df:        Data to insert.
        ch_client: clickhouse_connect client instance.
        database:  Target ClickHouse database.
        table:     Target table name.
        truncate:  If True, truncate the table before inserting (for full reloads).

    Returns:
        Number of rows inserted.
    """
    if df.empty:
        log.info("Empty DataFrame – skipping ClickHouse insert into %s.%s", database, table)
        return 0

    if truncate:
        ch_client.command(f"TRUNCATE TABLE IF EXISTS {database}.{table}")
        log.info("Truncated %s.%s", database, table)

    df = _coerce_datetime_like_string_columns(df)
    ch_client.insert_df(f"{database}.{table}", df)
    log.info("Inserted %d rows into ClickHouse %s.%s", len(df), database, table)
    return len(df)


def get_clickhouse_client(host: str, port: int, user: str, password: str):
    """Create and return a clickhouse_connect client."""
    import clickhouse_connect
    return clickhouse_connect.get_client(
        host=host,
        port=port,
        username=user,
        password=password,
        connect_timeout=10,
    )


# ===================================================================
# Watermark helpers (wrappers around db_utils.S3MaxDateManager)
# ===================================================================

def get_watermark(table_key: str, init_date: str = "2020-01-01") -> str:
    """
    Fetch the current watermark for a given table key from the metadata DB.
    Falls back to init_date if no watermark is recorded yet.
    """
    from db_utils import S3MaxDateManager
    mgr = S3MaxDateManager(table_name=table_key, init_date=init_date)
    return mgr.get_max_date()


def set_watermark(table_key: str, new_date: str) -> None:
    """Persist a new watermark for a given table key."""
    from db_utils import S3MaxDateManager
    mgr = S3MaxDateManager(table_name=table_key, init_date=new_date)
    mgr.update_max_date(new_date)
