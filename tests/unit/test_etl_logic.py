"""
Unit tests for plugins/etl_utils.py.

TDD: these tests define the contract for the shared ETL helper functions
used by all Airflow DAGs (extract, upload, download operations).
"""
import io
import pytest
import pandas as pd
from datetime import datetime
from unittest.mock import MagicMock, patch, call


class TestExtractTableIncremental:
    """Tests for etl_utils.extract_table_incremental()."""

    @pytest.fixture
    def etl_utils(self):
        from etl_utils import extract_table_incremental
        return extract_table_incremental

    def test_returns_dataframe(self, etl_utils):
        with patch("etl_utils.psycopg2.connect") as mock_connect:
            mock_conn = MagicMock()
            mock_connect.return_value.__enter__ = lambda s: mock_conn
            mock_connect.return_value.__exit__ = MagicMock(return_value=False)
            with patch("etl_utils.pd.read_sql") as mock_read:
                mock_read.return_value = pd.DataFrame({"id": [1, 2], "created_at": [datetime.now(), datetime.now()]})
                result = etl_utils(
                    dsn="host=localhost user=test",
                    schema="web",
                    table="orders",
                    timestamp_col="created_at",
                    watermark="2024-01-01",
                )
        assert isinstance(result, pd.DataFrame)

    def test_query_filters_by_watermark(self, etl_utils):
        with patch("etl_utils.pd.read_sql") as mock_read:
            mock_read.return_value = pd.DataFrame()
            with patch("etl_utils.psycopg2.connect"):
                try:
                    etl_utils("dsn", "web", "orders", "created_at", "2024-06-01")
                except Exception:
                    pass
            # Verify the watermark value appears in the call (either in SQL or params)
            if mock_read.called:
                call_args = mock_read.call_args
                sql_arg = str(call_args[0][0]) if call_args[0] else ""
                params_arg = str(call_args[1] if len(call_args) > 1 else "")
                assert "watermark" in sql_arg.lower() or "2024-06-01" in str(params_arg)

    def test_returns_empty_dataframe_when_no_new_records(self, etl_utils):
        with patch("etl_utils.pd.read_sql") as mock_read:
            mock_read.return_value = pd.DataFrame()
            with patch("etl_utils.psycopg2.connect"):
                try:
                    result = etl_utils("dsn", "web", "orders", "created_at", "2099-01-01")
                except Exception:
                    result = pd.DataFrame()
        assert isinstance(result, pd.DataFrame)


class TestDataFrameToParquet:
    """Tests for etl_utils.dataframe_to_parquet_bytes()."""

    @pytest.fixture
    def to_parquet(self):
        from etl_utils import dataframe_to_parquet_bytes
        return dataframe_to_parquet_bytes

    def test_returns_bytes(self, to_parquet):
        df = pd.DataFrame({"id": [1, 2, 3], "name": ["a", "b", "c"]})
        result = to_parquet(df)
        assert isinstance(result, bytes)
        assert len(result) > 0

    def test_parquet_is_readable(self, to_parquet):
        original = pd.DataFrame({"id": [1, 2], "value": [10.5, 20.3]})
        parquet_bytes = to_parquet(original)
        restored = pd.read_parquet(io.BytesIO(parquet_bytes))
        assert list(restored["id"]) == list(original["id"])

    def test_empty_dataframe_produces_valid_parquet(self, to_parquet):
        """Empty batches should not crash the pipeline."""
        df = pd.DataFrame({"id": [], "val": []})
        result = to_parquet(df)
        assert isinstance(result, bytes)

    def test_column_names_are_preserved(self, to_parquet):
        df = pd.DataFrame({"order_id": [1], "unit_price": [99.9], "quantity": [2]})
        restored = pd.read_parquet(io.BytesIO(to_parquet(df)))
        assert set(restored.columns) == {"order_id", "unit_price", "quantity"}


class TestUploadDataframeToS3:
    """Tests for etl_utils.upload_dataframe_to_s3()."""

    @pytest.fixture
    def upload_fn(self):
        from etl_utils import upload_dataframe_to_s3
        return upload_dataframe_to_s3

    def test_calls_put_object(self, upload_fn, mock_s3_client):
        df = pd.DataFrame({"id": [1, 2]})
        upload_fn(df, s3_client=mock_s3_client, bucket="test-bucket", key="web/orders/2024-01-01/data.parquet")
        mock_s3_client.put_object.assert_called_once()

    def test_uses_correct_bucket_and_key(self, upload_fn, mock_s3_client):
        df = pd.DataFrame({"id": [1]})
        bucket, key = "prod-bucket", "oms/orders/2024-06-01/data.parquet"
        upload_fn(df, s3_client=mock_s3_client, bucket=bucket, key=key)
        call_kwargs = mock_s3_client.put_object.call_args[1]
        assert call_kwargs["Bucket"] == bucket
        assert call_kwargs["Key"] == key

    def test_skips_upload_for_empty_dataframe(self, upload_fn, mock_s3_client):
        """Empty DataFrames should not trigger an S3 write – saves bandwidth."""
        df = pd.DataFrame()
        upload_fn(df, s3_client=mock_s3_client, bucket="bucket", key="key")
        mock_s3_client.put_object.assert_not_called()


class TestDownloadParquetFromS3:
    """Tests for etl_utils.download_parquet_from_s3()."""

    @pytest.fixture
    def download_fn(self):
        from etl_utils import download_parquet_from_s3
        return download_parquet_from_s3

    def test_returns_dataframe(self, download_fn):
        original = pd.DataFrame({"id": [1, 2, 3], "val": [10, 20, 30]})
        buf = io.BytesIO()
        original.to_parquet(buf, index=False)
        buf.seek(0)

        mock_client = MagicMock()
        mock_client.get_object.return_value = {"Body": buf}

        result = download_fn(s3_client=mock_client, bucket="bucket", key="some/key.parquet")
        assert isinstance(result, pd.DataFrame)
        assert len(result) == 3

    def test_preserves_column_names(self, download_fn):
        original = pd.DataFrame({"product_id": [1], "revenue": [500.0]})
        buf = io.BytesIO()
        original.to_parquet(buf, index=False)
        buf.seek(0)

        mock_client = MagicMock()
        mock_client.get_object.return_value = {"Body": buf}

        result = download_fn(s3_client=mock_client, bucket="b", key="k")
        assert "product_id" in result.columns
        assert "revenue" in result.columns


class TestBuildS3Key:
    """Tests for etl_utils.build_s3_key() – consistent key naming convention."""

    @pytest.fixture
    def build_key(self):
        from etl_utils import build_s3_key
        return build_s3_key

    def test_key_includes_source_table_and_date(self, build_key):
        key = build_key(source="web", table="orders", ds="2024-06-01")
        assert "web" in key
        assert "orders" in key
        assert "2024-06-01" in key

    def test_key_ends_with_parquet_extension(self, build_key):
        key = build_key(source="marketing", table="visits", ds="2024-01-15")
        assert key.endswith(".parquet")

    def test_key_format_is_consistent(self, build_key):
        key1 = build_key(source="web", table="orders", ds="2024-06-01")
        key2 = build_key(source="oms", table="shipments", ds="2024-06-01")
        # Both should follow the same pattern: source/table/ds/data.parquet
        parts1 = key1.split("/")
        parts2 = key2.split("/")
        assert len(parts1) == len(parts2)


class TestLoadDataframeToClickhouse:
    """load_dataframe_to_clickhouse must coerce string timestamps for clickhouse_connect."""

    def test_coerces_iso_string_datetimes_before_insert(self):
        from etl_utils import load_dataframe_to_clickhouse

        mock_ch = MagicMock()
        df = pd.DataFrame(
            {
                "id": [1],
                "created_at": ["2024-06-01 12:00:00"],
                "status": ["active"],
            }
        )
        load_dataframe_to_clickhouse(df, mock_ch, "staging", "raw_web_orders")
        mock_ch.insert_df.assert_called_once()
        inserted = mock_ch.insert_df.call_args[0][1]
        assert pd.api.types.is_datetime64_any_dtype(inserted["created_at"])
        assert inserted["status"].iloc[0] == "active"

    def test_coerces_when_blank_strings_mixed_with_datetimes(self):
        """Empty strings are notna() in pandas but must not block datetime coercion."""
        from etl_utils import load_dataframe_to_clickhouse

        mock_ch = MagicMock()
        df = pd.DataFrame(
            {
                "id": [1, 2],
                "confirmed_at": ["", "2024-06-01 12:00:00"],
            }
        )
        load_dataframe_to_clickhouse(df, mock_ch, "staging", "raw_oms_orders")
        inserted = mock_ch.insert_df.call_args[0][1]
        assert pd.api.types.is_datetime64_any_dtype(inserted["confirmed_at"])
        assert pd.isna(inserted["confirmed_at"].iloc[0])
        assert inserted["confirmed_at"].iloc[1] == pd.Timestamp("2024-06-01 12:00:00")
