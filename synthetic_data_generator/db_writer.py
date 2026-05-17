"""
db_writer.py – Database interaction layer for the synthetic data generator.
Responsible for inserting generated records into PostgreSQL.
Separated from generators.py so pure generation logic stays testable.
"""
import logging
from typing import Any

import psycopg2
import psycopg2.extras

log = logging.getLogger(__name__)


class DbWriter:
    """Thin wrapper around a psycopg2 connection for bulk inserts."""

    def __init__(self, dsn: str):
        self.conn = psycopg2.connect(dsn)
        self.conn.autocommit = False

    # ------------------------------------------------------------------
    # Generic helpers
    # ------------------------------------------------------------------

    def insert_many(self, table: str, rows: list[dict[str, Any]], returning: str = "id") -> list[Any]:
        """
        Bulk-insert rows into table (schema.table notation supported).
        Returns list of generated IDs if returning is set, else [].
        """
        if not rows:
            return []
        columns = list(rows[0].keys())
        values_template = "(" + ", ".join([f"%({c})s" for c in columns]) + ")"
        sql = (
            f"INSERT INTO {table} ({', '.join(columns)}) VALUES {values_template} "
            + (f"RETURNING {returning}" if returning else "")
        )
        ids = []
        with self.conn.cursor() as cur:
            for row in rows:
                cur.execute(sql, row)
                if returning:
                    result = cur.fetchone()
                    ids.append(result[0] if result else None)
        self.conn.commit()
        return ids

    def insert_one(self, table: str, row: dict[str, Any], returning: str = "id") -> Any:
        ids = self.insert_many(table, [row], returning=returning)
        return ids[0] if ids else None

    def insert_web_users_resolve_ids(self, rows: list[dict[str, Any]]) -> list[int]:
        """
        Insert web.users; on duplicate email, return existing row id.
        One id per input row (order preserved) for stable FK usage.
        """
        if not rows:
            return []
        sql_insert = """
            INSERT INTO web.users (email, first_name, last_name, city, country, registered_at)
            VALUES (%(email)s, %(first_name)s, %(last_name)s, %(city)s, %(country)s, %(registered_at)s)
            ON CONFLICT (email) DO NOTHING
            RETURNING id
        """
        sql_lookup = "SELECT id FROM web.users WHERE email = %s"
        ids: list[int] = []
        with self.conn.cursor() as cur:
            for row in rows:
                cur.execute(sql_insert, row)
                got = cur.fetchone()
                uid = got[0] if got else None
                if uid is None:
                    cur.execute(sql_lookup, (row["email"],))
                    uid = cur.fetchone()[0]
                ids.append(uid)
        self.conn.commit()
        return ids

    def upsert_many(
        self,
        table: str,
        rows: list[dict[str, Any]],
        conflict_cols: list[str],
        update_cols: list[str],
        returning: str = "id",
    ) -> list[Any]:
        """INSERT … ON CONFLICT DO UPDATE for idempotent writes."""
        if not rows:
            return []
        columns = list(rows[0].keys())
        values_tpl = "(" + ", ".join([f"%({c})s" for c in columns]) + ")"
        update_clause = ", ".join([f"{c} = EXCLUDED.{c}" for c in update_cols])
        sql = (
            f"INSERT INTO {table} ({', '.join(columns)}) VALUES {values_tpl} "
            f"ON CONFLICT ({', '.join(conflict_cols)}) DO UPDATE SET {update_clause} "
            + (f"RETURNING {returning}" if returning else "")
        )
        ids = []
        with self.conn.cursor() as cur:
            for row in rows:
                cur.execute(sql, row)
                if returning:
                    result = cur.fetchone()
                    ids.append(result[0] if result else None)
        self.conn.commit()
        return ids

    def fetch_ids(self, table: str, limit: int = 10_000) -> list[int]:
        """Fetch existing primary-key IDs from a table (for FK consistency)."""
        with self.conn.cursor() as cur:
            cur.execute(f"SELECT id FROM {table} ORDER BY id DESC LIMIT %s", (limit,))
            return [row[0] for row in cur.fetchall()]

    def fetch_column(self, table: str, column: str, limit: int = 10_000) -> list[Any]:
        with self.conn.cursor() as cur:
            cur.execute(f"SELECT {column} FROM {table} LIMIT %s", (limit,))
            return [row[0] for row in cur.fetchall()]

    def count(self, table: str) -> int:
        with self.conn.cursor() as cur:
            cur.execute(f"SELECT COUNT(*) FROM {table}")
            return cur.fetchone()[0]

    def close(self):
        self.conn.close()
