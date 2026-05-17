"""
db_utils.py – Watermark management for incremental ETL loads.

S3MaxDateManager stores and retrieves the maximum processed date for each
source table in the metadata.s3_max_dates Postgres table.
"""
import os
from datetime import date
from typing import Optional

import psycopg2

# Module-level import allows tests to patch `db_utils.PostgresHook`
# Falls back to None when apache-airflow is not installed (e.g. unit-test venv).
try:
    from airflow.providers.postgres.hooks.postgres import PostgresHook
except ImportError:  # pragma: no cover
    PostgresHook = None  # type: ignore


def _dsn_from_env() -> str:
    """Same DSN shape as incremental extract DAGs (docker-compose sets POSTGRES_*)."""
    user = os.environ["POSTGRES_USER"]
    pw = os.environ["POSTGRES_PASSWORD"]
    db = os.environ.get("POSTGRES_DB", "airflow")
    host = os.environ.get("POSTGRES_HOST", "postgres")
    port = os.environ.get("POSTGRES_PORT", "5432")
    return f"host={host} port={port} user={user} password={pw} dbname={db}"


class S3MaxDateManager:
    """
    Track the high-water-mark date for incremental extracts.

    The watermark is persisted in metadata.s3_max_dates:
        table_name TEXT PRIMARY KEY,
        max_date   DATE NOT NULL,
        updated_at TIMESTAMP DEFAULT NOW()

    Args:
        table_name:       Unique key for this source table (e.g. 'web.orders').
        init_date:        Fallback date string if no row exists yet.
        postgres_conn_id: If set, use Airflow PostgresHook for the metadata DB.
                          If None (default), connect via POSTGRES_* env vars so
                          watermarks work even when connections were never seeded.
    """

    _UPSERT_SQL = """
        INSERT INTO metadata.s3_max_dates (table_name, max_date, updated_at)
        VALUES (%s, %s, NOW())
        ON CONFLICT (table_name)
        DO UPDATE SET max_date = EXCLUDED.max_date, updated_at = NOW()
    """

    _SELECT_SQL = """
        SELECT COALESCE(MAX(max_date), %s::DATE)
        FROM metadata.s3_max_dates
        WHERE table_name = %s
    """

    def __init__(
        self,
        table_name: str,
        init_date: str,
        postgres_conn_id: Optional[str] = None,
    ):
        self.table_name = table_name
        self.init_date = init_date
        self.postgres_conn_id = postgres_conn_id
        self._hook = None
        if postgres_conn_id is not None:
            if PostgresHook is None:
                raise RuntimeError(
                    "postgres_conn_id was set but apache-airflow PostgresHook is not available"
                )
            self._hook = PostgresHook(postgres_conn_id=postgres_conn_id)

    def get_max_date(self) -> str:
        """Return the stored watermark date as an ISO string (YYYY-MM-DD)."""
        if self._hook is not None:
            row = self._hook.get_first(
                self._SELECT_SQL,
                parameters=(self.init_date, self.table_name),
            )
        else:
            with psycopg2.connect(_dsn_from_env()) as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        self._SELECT_SQL,
                        (self.init_date, self.table_name),
                    )
                    row = cur.fetchone()
        result: date = row[0]
        return str(result)

    def update_max_date(self, new_date: str) -> None:
        """Persist a new watermark date for this table (upsert)."""
        if self._hook is not None:
            self._hook.run(
                self._UPSERT_SQL,
                parameters=(self.table_name, new_date),
            )
        else:
            with psycopg2.connect(_dsn_from_env()) as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        self._UPSERT_SQL,
                        (self.table_name, new_date),
                    )
