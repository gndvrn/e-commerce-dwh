"""
Unit tests for plugins/db_utils.py (S3MaxDateManager).

TDD: verify the watermark management contract used by all incremental ETL DAGs.

Note: apache-airflow is NOT required in the test virtualenv.
      We stub the airflow modules before importing db_utils so
      PostgresHook can be replaced with a MagicMock.
"""
import os
import sys
from unittest.mock import MagicMock, patch
import pytest
from datetime import date

# ---------------------------------------------------------------------------
# Airflow stub – must be in place before anything imports from airflow.*
# ---------------------------------------------------------------------------
for mod in [
    "airflow",
    "airflow.providers",
    "airflow.providers.postgres",
    "airflow.providers.postgres.hooks",
    "airflow.providers.postgres.hooks.postgres",
]:
    sys.modules.setdefault(mod, MagicMock())

# Now we can import safely
from db_utils import S3MaxDateManager   # noqa: E402


class TestS3MaxDateManager:
    """Tests for S3MaxDateManager – the incremental watermark keeper."""

    @pytest.fixture(autouse=True)
    def mock_hook_class(self):
        """Replace PostgresHook with a MagicMock for every test."""
        with patch("db_utils.PostgresHook") as mock_cls:
            self.MockHook = mock_cls
            self.mock_hook_instance = mock_cls.return_value
            yield mock_cls

    # ------------------------------------------------------------------
    # get_max_date()
    # ------------------------------------------------------------------

    def test_get_max_date_returns_init_date_when_table_is_empty(self):
        """When no watermark row exists, COALESCE returns the init_date."""
        self.mock_hook_instance.get_first.return_value = (date(2024, 1, 1),)
        mgr = S3MaxDateManager(
            table_name="web.orders",
            init_date="2024-01-01",
            postgres_conn_id="metadata_db",
        )
        result = mgr.get_max_date()
        assert result == "2024-01-01"

    def test_get_max_date_returns_stored_date_when_row_exists(self):
        """When a watermark row exists, the stored date is returned."""
        stored = date(2024, 6, 15)
        self.mock_hook_instance.get_first.return_value = (stored,)
        mgr = S3MaxDateManager(
            table_name="web.orders",
            init_date="2024-01-01",
            postgres_conn_id="metadata_db",
        )
        result = mgr.get_max_date()
        assert result == "2024-06-15"

    def test_get_max_date_queries_correct_table_name(self):
        """The SQL must filter by the correct table_name parameter."""
        self.mock_hook_instance.get_first.return_value = (date(2024, 1, 1),)
        table = "marketing.visits"
        mgr = S3MaxDateManager(
            table_name=table,
            init_date="2024-01-01",
            postgres_conn_id="metadata_db",
        )
        mgr.get_max_date()
        args, kwargs = self.mock_hook_instance.get_first.call_args
        params = kwargs.get("parameters", args[1] if len(args) > 1 else ())
        assert table in params

    def test_get_max_date_uses_psycopg2_when_conn_id_none(self):
        """Production default: no Airflow connection row required."""
        self.MockHook.reset_mock()
        mock_cur = MagicMock()
        mock_cur.fetchone.return_value = (date(2024, 3, 1),)
        mock_cur_cm = MagicMock()
        mock_cur_cm.__enter__.return_value = mock_cur
        mock_cur_cm.__exit__.return_value = False

        mock_conn = MagicMock()
        mock_conn.cursor.return_value = mock_cur_cm
        mock_conn_cm = MagicMock()
        mock_conn_cm.__enter__.return_value = mock_conn
        mock_conn_cm.__exit__.return_value = False

        with patch.dict(
            os.environ,
            {
                "POSTGRES_USER": "u",
                "POSTGRES_PASSWORD": "p",
                "POSTGRES_DB": "airflow",
            },
            clear=False,
        ):
            with patch("db_utils.psycopg2.connect", return_value=mock_conn_cm) as mock_connect:
                mgr = S3MaxDateManager(table_name="test", init_date="2020-01-01")
                result = mgr.get_max_date()

        self.MockHook.assert_not_called()
        mock_connect.assert_called_once()
        assert result == "2024-03-01"

    def test_get_max_date_accepts_custom_conn_id(self):
        mgr = S3MaxDateManager(
            table_name="test",
            init_date="2020-01-01",
            postgres_conn_id="custom_db",
        )
        self.MockHook.assert_called_once_with(postgres_conn_id="custom_db")

    # ------------------------------------------------------------------
    # update_max_date()
    # ------------------------------------------------------------------

    def test_update_max_date_calls_hook_run(self):
        mgr = S3MaxDateManager(
            table_name="web.orders",
            init_date="2024-01-01",
            postgres_conn_id="metadata_db",
        )
        mgr.update_max_date("2024-07-01")
        self.mock_hook_instance.run.assert_called_once()

    def test_update_max_date_passes_table_name_and_date(self):
        """Parameters tuple must contain both table_name and the new date value."""
        table = "oms.shipments"
        new_date = "2024-08-01"
        mgr = S3MaxDateManager(
            table_name=table,
            init_date="2024-01-01",
            postgres_conn_id="metadata_db",
        )
        mgr.update_max_date(new_date)
        _, kwargs = self.mock_hook_instance.run.call_args
        params = kwargs.get("parameters", ())
        assert table in params
        assert new_date in params

    def test_update_max_date_uses_upsert_semantics(self):
        """SQL should use INSERT … ON CONFLICT to ensure idempotency."""
        mgr = S3MaxDateManager(
            table_name="test",
            init_date="2024-01-01",
            postgres_conn_id="metadata_db",
        )
        mgr.update_max_date("2024-07-01")
        sql_call_args = self.mock_hook_instance.run.call_args[0][0]
        assert "ON CONFLICT" in sql_call_args.upper()
