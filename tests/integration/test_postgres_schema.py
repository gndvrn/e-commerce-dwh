"""
Integration tests for Postgres OLTP schema.

TDD: these tests verify that src/init_db/init.sql creates the expected
schema structure. They require a running Postgres instance.

Run with:
    POSTGRES_HOST=localhost POSTGRES_USER=airflow POSTGRES_PASSWORD=airflow \
    pytest tests/integration/test_postgres_schema.py -v -m integration
"""
import pytest


pytestmark = pytest.mark.integration


# Helper to check table/column existence
def table_exists(cur, schema, table):
    cur.execute(
        "SELECT 1 FROM information_schema.tables "
        "WHERE table_schema = %s AND table_name = %s",
        (schema, table),
    )
    return cur.fetchone() is not None


def column_exists(cur, schema, table, column):
    cur.execute(
        "SELECT 1 FROM information_schema.columns "
        "WHERE table_schema = %s AND table_name = %s AND column_name = %s",
        (schema, table, column),
    )
    return cur.fetchone() is not None


def get_column_type(cur, schema, table, column):
    cur.execute(
        "SELECT data_type FROM information_schema.columns "
        "WHERE table_schema = %s AND table_name = %s AND column_name = %s",
        (schema, table, column),
    )
    row = cur.fetchone()
    return row[0] if row else None


# ---------------------------------------------------------------------------
# Schema existence
# ---------------------------------------------------------------------------

class TestSchemaExistence:
    def test_web_schema_exists(self, pg_connection):
        with pg_connection.cursor() as cur:
            cur.execute("SELECT 1 FROM information_schema.schemata WHERE schema_name = 'web'")
            assert cur.fetchone(), "Schema 'web' not found"

    def test_oms_schema_exists(self, pg_connection):
        with pg_connection.cursor() as cur:
            cur.execute("SELECT 1 FROM information_schema.schemata WHERE schema_name = 'oms'")
            assert cur.fetchone(), "Schema 'oms' not found"

    def test_wms_schema_exists(self, pg_connection):
        with pg_connection.cursor() as cur:
            cur.execute("SELECT 1 FROM information_schema.schemata WHERE schema_name = 'wms'")
            assert cur.fetchone(), "Schema 'wms' not found"

    def test_marketing_schema_exists(self, pg_connection):
        with pg_connection.cursor() as cur:
            cur.execute("SELECT 1 FROM information_schema.schemata WHERE schema_name = 'marketing'")
            assert cur.fetchone(), "Schema 'marketing' not found"

    def test_metadata_schema_exists(self, pg_connection):
        with pg_connection.cursor() as cur:
            cur.execute("SELECT 1 FROM information_schema.schemata WHERE schema_name = 'metadata'")
            assert cur.fetchone(), "Schema 'metadata' not found"


# ---------------------------------------------------------------------------
# Web schema tables
# ---------------------------------------------------------------------------

class TestWebSchemaTables:
    @pytest.mark.parametrize("table", [
        "users", "categories", "products", "sessions",
        "carts", "cart_items", "orders", "order_items",
    ])
    def test_table_exists(self, pg_connection, table):
        with pg_connection.cursor() as cur:
            assert table_exists(cur, "web", table), f"web.{table} not found"

    def test_users_has_required_columns(self, pg_connection):
        with pg_connection.cursor() as cur:
            for col in ("id", "email", "city", "country", "registered_at"):
                assert column_exists(cur, "web", "users", col), f"web.users.{col} missing"

    def test_users_email_is_unique(self, pg_connection):
        with pg_connection.cursor() as cur:
            cur.execute(
                "SELECT COUNT(*) FROM information_schema.table_constraints tc "
                "JOIN information_schema.constraint_column_usage ccu USING (constraint_name, table_schema) "
                "WHERE tc.constraint_type = 'UNIQUE' AND tc.table_schema = 'web' "
                "AND tc.table_name = 'users' AND ccu.column_name = 'email'"
            )
            count = cur.fetchone()[0]
            assert count >= 1, "web.users.email lacks UNIQUE constraint"

    def test_products_has_price_and_cost(self, pg_connection):
        with pg_connection.cursor() as cur:
            for col in ("price", "cost_price"):
                assert column_exists(cur, "web", "products", col), f"web.products.{col} missing"

    def test_carts_has_status_column(self, pg_connection):
        with pg_connection.cursor() as cur:
            assert column_exists(cur, "web", "carts", "status"), "web.carts.status missing"

    def test_orders_has_total_amount(self, pg_connection):
        with pg_connection.cursor() as cur:
            assert column_exists(cur, "web", "orders", "total_amount"), "web.orders.total_amount missing"

    def test_order_items_has_unit_cost(self, pg_connection):
        with pg_connection.cursor() as cur:
            assert column_exists(cur, "web", "order_items", "unit_cost"), "web.order_items.unit_cost missing"

    def test_all_tables_have_created_at(self, pg_connection):
        """created_at is the watermark column for incremental extraction."""
        tables_with_alt_ts = {
            "users": "registered_at",
            "sessions": "started_at",
        }
        tables = ["categories", "products", "carts", "cart_items", "orders", "order_items"]
        with pg_connection.cursor() as cur:
            for t in tables:
                assert column_exists(cur, "web", t, "created_at"), f"web.{t} missing created_at"
            for t, ts_col in tables_with_alt_ts.items():
                assert column_exists(cur, "web", t, ts_col), f"web.{t} missing {ts_col}"


# ---------------------------------------------------------------------------
# OMS schema tables
# ---------------------------------------------------------------------------

class TestOmsSchemaTables:
    @pytest.mark.parametrize("table", ["oms_orders", "shipments", "returns"])
    def test_table_exists(self, pg_connection, table):
        with pg_connection.cursor() as cur:
            assert table_exists(cur, "oms", table), f"oms.{table} not found"

    def test_oms_orders_has_timing_columns(self, pg_connection):
        with pg_connection.cursor() as cur:
            for col in ("received_at", "confirmed_at", "dispatched_at"):
                assert column_exists(cur, "oms", "oms_orders", col), f"oms.oms_orders.{col} missing"

    def test_oms_orders_has_web_order_id(self, pg_connection):
        with pg_connection.cursor() as cur:
            assert column_exists(cur, "oms", "oms_orders", "web_order_id")

    def test_shipments_has_otif_flags(self, pg_connection):
        with pg_connection.cursor() as cur:
            for col in ("is_on_time", "is_complete"):
                assert column_exists(cur, "oms", "shipments", col), f"oms.shipments.{col} missing"

    def test_shipments_has_delivery_dates(self, pg_connection):
        with pg_connection.cursor() as cur:
            for col in ("planned_delivery", "actual_delivery"):
                assert column_exists(cur, "oms", "shipments", col), f"oms.shipments.{col} missing"


# ---------------------------------------------------------------------------
# WMS schema tables
# ---------------------------------------------------------------------------

class TestWmsSchemaTables:
    @pytest.mark.parametrize("table", [
        "wms_products", "inventory", "inventory_movements", "picking_tasks",
    ])
    def test_table_exists(self, pg_connection, table):
        with pg_connection.cursor() as cur:
            assert table_exists(cur, "wms", table), f"wms.{table} not found"

    def test_inventory_has_quantity_fields(self, pg_connection):
        with pg_connection.cursor() as cur:
            for col in ("quantity_on_hand", "quantity_reserved", "reorder_point"):
                assert column_exists(cur, "wms", "inventory", col), f"wms.inventory.{col} missing"

    def test_inventory_movements_has_movement_type(self, pg_connection):
        with pg_connection.cursor() as cur:
            assert column_exists(cur, "wms", "inventory_movements", "movement_type")

    def test_picking_tasks_has_accuracy_flags(self, pg_connection):
        with pg_connection.cursor() as cur:
            for col in ("is_accurate", "is_substituted"):
                assert column_exists(cur, "wms", "picking_tasks", col), f"wms.picking_tasks.{col} missing"


# ---------------------------------------------------------------------------
# Marketing schema tables
# ---------------------------------------------------------------------------

class TestMarketingSchemaTables:
    @pytest.mark.parametrize("table", [
        "traffic_sources", "ad_campaigns", "ad_campaign_daily_stats", "visits", "page_events",
    ])
    def test_table_exists(self, pg_connection, table):
        with pg_connection.cursor() as cur:
            assert table_exists(cur, "marketing", table), f"marketing.{table} not found"

    def test_traffic_sources_has_channel_type(self, pg_connection):
        with pg_connection.cursor() as cur:
            assert column_exists(cur, "marketing", "traffic_sources", "channel_type")

    def test_visits_has_behavior_columns(self, pg_connection):
        with pg_connection.cursor() as cur:
            for col in ("duration_sec", "page_views", "is_bounce", "visited_at"):
                assert column_exists(cur, "marketing", "visits", col), f"marketing.visits.{col} missing"

    def test_ad_campaign_daily_stats_has_metrics(self, pg_connection):
        with pg_connection.cursor() as cur:
            for col in ("impressions", "clicks", "spend", "conversions"):
                assert column_exists(cur, "marketing", "ad_campaign_daily_stats", col), \
                    f"marketing.ad_campaign_daily_stats.{col} missing"


# ---------------------------------------------------------------------------
# Metadata schema
# ---------------------------------------------------------------------------

class TestMetadataSchema:
    def test_s3_max_dates_table_exists(self, pg_connection):
        with pg_connection.cursor() as cur:
            assert table_exists(cur, "metadata", "s3_max_dates"), "metadata.s3_max_dates not found"

    def test_s3_max_dates_has_required_columns(self, pg_connection):
        with pg_connection.cursor() as cur:
            for col in ("table_name", "max_date", "updated_at"):
                assert column_exists(cur, "metadata", "s3_max_dates", col), \
                    f"metadata.s3_max_dates.{col} missing"

    def test_s3_max_dates_table_name_is_primary_key(self, pg_connection):
        with pg_connection.cursor() as cur:
            cur.execute(
                "SELECT COUNT(*) FROM information_schema.table_constraints "
                "WHERE constraint_type = 'PRIMARY KEY' AND table_schema = 'metadata' "
                "AND table_name = 's3_max_dates'"
            )
            assert cur.fetchone()[0] >= 1, "metadata.s3_max_dates lacks PRIMARY KEY"
