-- ============================================================
-- ClickHouse DDL: databases + raw staging tables
-- Executed automatically on first container start.
-- Core/datamart tables are built by dbt.
-- ============================================================

-- Databases
CREATE DATABASE IF NOT EXISTS staging;
CREATE DATABASE IF NOT EXISTS core;
CREATE DATABASE IF NOT EXISTS datamart;

-- ============================================================
-- STAGING: raw tables (one per OLTP source table)
-- Engine: ReplacingMergeTree – idempotent re-loads by (id, loaded_at)
-- ============================================================

-- web schema ------------------------------------------------
CREATE TABLE IF NOT EXISTS staging.raw_web_categories
(
    id          Int32,
    name        String,
    parent_id   Nullable(Int32),
    created_at  DateTime,
    loaded_at   DateTime DEFAULT now()
) ENGINE = ReplacingMergeTree(loaded_at)
ORDER BY id;

CREATE TABLE IF NOT EXISTS staging.raw_web_products
(
    id          Int32,
    category_id Int32,
    name        String,
    price       Float64,
    cost_price  Float64,
    is_active   UInt8,
    created_at  DateTime,
    loaded_at   DateTime DEFAULT now()
) ENGINE = ReplacingMergeTree(loaded_at)
ORDER BY id;

CREATE TABLE IF NOT EXISTS staging.raw_web_users
(
    id            Int32,
    email         String,
    first_name    Nullable(String),
    last_name     Nullable(String),
    city          Nullable(String),
    country       String,
    registered_at DateTime,
    loaded_at     DateTime DEFAULT now()
) ENGINE = ReplacingMergeTree(loaded_at)
ORDER BY id;

CREATE TABLE IF NOT EXISTS staging.raw_web_sessions
(
    id           Int64,
    user_id      Nullable(Int32),
    utm_source   Nullable(String),
    utm_campaign Nullable(String),
    device_type  String,
    started_at   DateTime,
    ended_at     Nullable(DateTime),
    page_views   Int32,
    loaded_at    DateTime DEFAULT now()
) ENGINE = ReplacingMergeTree(loaded_at)
ORDER BY id;

CREATE TABLE IF NOT EXISTS staging.raw_web_carts
(
    id         Int64,
    user_id    Nullable(Int32),
    session_id Nullable(Int64),
    status     String,
    created_at DateTime,
    updated_at DateTime,
    loaded_at  DateTime DEFAULT now()
) ENGINE = ReplacingMergeTree(loaded_at)
ORDER BY id;

CREATE TABLE IF NOT EXISTS staging.raw_web_cart_items
(
    id            Int64,
    cart_id       Int64,
    product_id    Int32,
    quantity      Int32,
    price_at_time Float64,
    cost_price    Float64,
    created_at    DateTime,
    loaded_at     DateTime DEFAULT now()
) ENGINE = ReplacingMergeTree(loaded_at)
ORDER BY id;

CREATE TABLE IF NOT EXISTS staging.raw_web_orders
(
    id           Int64,
    user_id      Int32,
    cart_id      Nullable(Int64),
    total_amount Float64,
    status       String,
    created_at   DateTime,
    loaded_at    DateTime DEFAULT now()
) ENGINE = ReplacingMergeTree(loaded_at)
ORDER BY id;

CREATE TABLE IF NOT EXISTS staging.raw_web_order_items
(
    id         Int64,
    order_id   Int64,
    product_id Int32,
    quantity   Int32,
    unit_price Float64,
    unit_cost  Float64,
    created_at DateTime,
    loaded_at  DateTime DEFAULT now()
) ENGINE = ReplacingMergeTree(loaded_at)
ORDER BY id;

-- oms schema ------------------------------------------------
CREATE TABLE IF NOT EXISTS staging.raw_oms_orders
(
    id            Int64,
    web_order_id  Int64,
    status        String,
    received_at   DateTime,
    confirmed_at  Nullable(DateTime),
    dispatched_at Nullable(DateTime),
    created_at    DateTime,
    loaded_at     DateTime DEFAULT now()
) ENGINE = ReplacingMergeTree(loaded_at)
ORDER BY id;

CREATE TABLE IF NOT EXISTS staging.raw_oms_shipments
(
    id               Int64,
    oms_order_id     Int64,
    carrier_id       Nullable(String),
    tracking_number  Nullable(String),
    planned_delivery Nullable(Date),
    actual_delivery  Nullable(Date),
    is_on_time       Nullable(UInt8),
    is_complete      UInt8,
    created_at       DateTime,
    loaded_at        DateTime DEFAULT now()
) ENGINE = ReplacingMergeTree(loaded_at)
ORDER BY id;

CREATE TABLE IF NOT EXISTS staging.raw_oms_returns
(
    id           Int64,
    oms_order_id Int64,
    reason       String,
    status       String,
    created_at   DateTime,
    loaded_at    DateTime DEFAULT now()
) ENGINE = ReplacingMergeTree(loaded_at)
ORDER BY id;

-- wms schema ------------------------------------------------
CREATE TABLE IF NOT EXISTS staging.raw_wms_products
(
    id             Int32,
    web_product_id Int32,
    sku            String,
    unit_cost      Float64,
    created_at     DateTime,
    loaded_at      DateTime DEFAULT now()
) ENGINE = ReplacingMergeTree(loaded_at)
ORDER BY id;

CREATE TABLE IF NOT EXISTS staging.raw_wms_inventory
(
    id                Int32,
    wms_product_id    Int32,
    quantity_on_hand  Int32,
    quantity_reserved Int32,
    reorder_point     Int32,
    updated_at        DateTime,
    loaded_at         DateTime DEFAULT now()
) ENGINE = ReplacingMergeTree(loaded_at)
ORDER BY id;

CREATE TABLE IF NOT EXISTS staging.raw_wms_inventory_movements
(
    id             Int64,
    wms_product_id Int32,
    movement_type  String,
    quantity       Int32,
    created_at     DateTime,
    loaded_at      DateTime DEFAULT now()
) ENGINE = ReplacingMergeTree(loaded_at)
ORDER BY id;

CREATE TABLE IF NOT EXISTS staging.raw_wms_picking_tasks
(
    id             Int64,
    oms_order_id   Int64,
    wms_product_id Int32,
    quantity       Int32,
    is_accurate    UInt8,
    is_substituted UInt8,
    completed_at   Nullable(DateTime),
    created_at     DateTime,
    loaded_at      DateTime DEFAULT now()
) ENGINE = ReplacingMergeTree(loaded_at)
ORDER BY id;

-- marketing schema ------------------------------------------
CREATE TABLE IF NOT EXISTS staging.raw_marketing_traffic_sources
(
    id           Int32,
    name         String,
    channel_type String,
    created_at   DateTime,
    loaded_at    DateTime DEFAULT now()
) ENGINE = ReplacingMergeTree(loaded_at)
ORDER BY id;

CREATE TABLE IF NOT EXISTS staging.raw_marketing_ad_campaigns
(
    id           Int32,
    source_id    Int32,
    name         String,
    budget       Nullable(Float64),
    actual_spend Float64,
    start_date   Nullable(Date),
    end_date     Nullable(Date),
    created_at   DateTime,
    loaded_at    DateTime DEFAULT now()
) ENGINE = ReplacingMergeTree(loaded_at)
ORDER BY id;

CREATE TABLE IF NOT EXISTS staging.raw_marketing_ad_campaign_daily_stats
(
    id          Int64,
    campaign_id Int32,
    stat_date   Date,
    impressions Int32,
    clicks      Int32,
    spend       Float64,
    conversions Int32,
    created_at  DateTime,
    loaded_at   DateTime DEFAULT now()
) ENGINE = ReplacingMergeTree(loaded_at)
ORDER BY (campaign_id, stat_date);

CREATE TABLE IF NOT EXISTS staging.raw_marketing_visits
(
    id           Int64,
    user_id      Nullable(Int32),
    source_id    Nullable(Int32),
    utm_campaign Nullable(String),
    duration_sec Int32,
    page_views   Int32,
    is_bounce    UInt8,
    visited_at   DateTime,
    loaded_at    DateTime DEFAULT now()
) ENGINE = ReplacingMergeTree(loaded_at)
ORDER BY id;

CREATE TABLE IF NOT EXISTS staging.raw_marketing_page_events
(
    id         Int64,
    visit_id   Int64,
    event_type String,
    page_url   Nullable(String),
    event_at   DateTime,
    loaded_at  DateTime DEFAULT now()
) ENGINE = ReplacingMergeTree(loaded_at)
ORDER BY id;
