"""
Shared pytest fixtures for all test suites.
"""
import os
import sys
from datetime import date, datetime
from unittest.mock import MagicMock, patch

import pytest

# Make project root importable
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "plugins"))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "synthetic_data_generator"))


# ---------------------------------------------------------------------------
# Postgres integration fixture (skipped if env not set)
# ---------------------------------------------------------------------------

@pytest.fixture(scope="session")
def pg_connection():
    """Live Postgres connection – only used in integration tests."""
    import psycopg2

    pg_host = os.getenv("POSTGRES_HOST", "localhost")
    pg_user = os.getenv("POSTGRES_USER", "airflow")
    pg_password = os.getenv("POSTGRES_PASSWORD", "airflow")

    try:
        conn = psycopg2.connect(
            host=pg_host,
            port=5432,
            user=pg_user,
            password=pg_password,
            dbname=os.getenv("POSTGRES_DB", "airflow"),
            connect_timeout=3,
        )
        yield conn
        conn.close()
    except Exception as exc:
        pytest.skip(f"Postgres not available: {exc}")


# ---------------------------------------------------------------------------
# MinIO / S3 mock fixture
# ---------------------------------------------------------------------------

@pytest.fixture
def mock_s3_client():
    """Returns a MagicMock acting as a boto3 S3 client."""
    client = MagicMock()
    # put_object succeeds silently
    client.put_object.return_value = {"ResponseMetadata": {"HTTPStatusCode": 200}}
    return client


# ---------------------------------------------------------------------------
# Sample data fixtures (small, deterministic)
# ---------------------------------------------------------------------------

@pytest.fixture
def sample_category_ids():
    return [1, 2, 3, 4, 5]


@pytest.fixture
def sample_product_ids():
    return list(range(1, 51))


@pytest.fixture
def sample_user_ids():
    return list(range(1, 21))


@pytest.fixture
def sample_source_ids():
    return [1, 2, 3, 4, 5]


@pytest.fixture
def sample_campaign_ids():
    return [1, 2, 3]
