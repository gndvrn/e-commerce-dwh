-- ============================================================
-- e-commerce DWH: OLTP layer DDL
-- Creates 4 isolated source schemas + metadata schema
-- Automatically executed by Postgres on first container start
-- ============================================================

-- ============================================================
-- SCHEMA: web  (web-platform: users, products, sessions, orders)
-- ============================================================
CREATE SCHEMA IF NOT EXISTS web;

CREATE TABLE IF NOT EXISTS web.categories (
    id          SERIAL PRIMARY KEY,
    name        TEXT NOT NULL,
    parent_id   INTEGER REFERENCES web.categories(id) ON DELETE SET NULL,
    created_at  TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS web.products (
    id          SERIAL PRIMARY KEY,
    category_id INTEGER NOT NULL REFERENCES web.categories(id),
    name        TEXT NOT NULL,
    price       NUMERIC(10,2) NOT NULL CHECK (price > 0),
    cost_price  NUMERIC(10,2) NOT NULL CHECK (cost_price > 0),
    is_active   BOOLEAN NOT NULL DEFAULT TRUE,
    created_at  TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS web.users (
    id            SERIAL PRIMARY KEY,
    email         TEXT NOT NULL UNIQUE,
    first_name    TEXT,
    last_name     TEXT,
    city          TEXT,
    country       TEXT NOT NULL DEFAULT 'Russia',
    registered_at TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS web.sessions (
    id           BIGSERIAL PRIMARY KEY,
    user_id      INTEGER REFERENCES web.users(id) ON DELETE SET NULL,
    utm_source   TEXT,
    utm_campaign TEXT,
    device_type  TEXT NOT NULL DEFAULT 'desktop',
    started_at   TIMESTAMP NOT NULL DEFAULT NOW(),
    ended_at     TIMESTAMP,
    page_views   INTEGER NOT NULL DEFAULT 1 CHECK (page_views >= 1)
);
CREATE INDEX IF NOT EXISTS idx_sessions_started_at ON web.sessions(started_at);
CREATE INDEX IF NOT EXISTS idx_sessions_user_id    ON web.sessions(user_id);

CREATE TABLE IF NOT EXISTS web.carts (
    id         BIGSERIAL PRIMARY KEY,
    user_id    INTEGER REFERENCES web.users(id) ON DELETE SET NULL,
    session_id BIGINT REFERENCES web.sessions(id) ON DELETE SET NULL,
    status     TEXT NOT NULL DEFAULT 'active'
                   CHECK (status IN ('active','abandoned','converted')),
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_carts_updated_at ON web.carts(updated_at);
CREATE INDEX IF NOT EXISTS idx_carts_user_id    ON web.carts(user_id);

CREATE TABLE IF NOT EXISTS web.cart_items (
    id            BIGSERIAL PRIMARY KEY,
    cart_id       BIGINT NOT NULL REFERENCES web.carts(id) ON DELETE CASCADE,
    product_id    INTEGER NOT NULL REFERENCES web.products(id),
    quantity      INTEGER NOT NULL DEFAULT 1 CHECK (quantity >= 1),
    price_at_time NUMERIC(10,2) NOT NULL CHECK (price_at_time > 0),
    cost_price    NUMERIC(10,2) NOT NULL CHECK (cost_price > 0),
    created_at    TIMESTAMP NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_cart_items_cart_id ON web.cart_items(cart_id);

CREATE TABLE IF NOT EXISTS web.orders (
    id           BIGSERIAL PRIMARY KEY,
    user_id      INTEGER NOT NULL REFERENCES web.users(id),
    cart_id      BIGINT REFERENCES web.carts(id) ON DELETE SET NULL,
    total_amount NUMERIC(10,2) NOT NULL CHECK (total_amount >= 0),
    status       TEXT NOT NULL DEFAULT 'pending'
                     CHECK (status IN ('pending','paid','processing','shipped','delivered','cancelled','refunded')),
    created_at   TIMESTAMP NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_orders_created_at ON web.orders(created_at);
CREATE INDEX IF NOT EXISTS idx_orders_user_id    ON web.orders(user_id);

CREATE TABLE IF NOT EXISTS web.order_items (
    id         BIGSERIAL PRIMARY KEY,
    order_id   BIGINT NOT NULL REFERENCES web.orders(id) ON DELETE CASCADE,
    product_id INTEGER NOT NULL REFERENCES web.products(id),
    quantity   INTEGER NOT NULL DEFAULT 1 CHECK (quantity >= 1),
    unit_price NUMERIC(10,2) NOT NULL CHECK (unit_price > 0),
    unit_cost  NUMERIC(10,2) NOT NULL CHECK (unit_cost > 0),
    created_at TIMESTAMP NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_order_items_order_id   ON web.order_items(order_id);
CREATE INDEX IF NOT EXISTS idx_order_items_created_at ON web.order_items(created_at);


-- ============================================================
-- SCHEMA: oms  (Order Management System)
-- ============================================================
CREATE SCHEMA IF NOT EXISTS oms;

CREATE TABLE IF NOT EXISTS oms.oms_orders (
    id           BIGSERIAL PRIMARY KEY,
    web_order_id BIGINT NOT NULL,
    status       TEXT NOT NULL DEFAULT 'received'
                     CHECK (status IN ('received','confirmed','dispatched','delivered','cancelled')),
    received_at  TIMESTAMP NOT NULL DEFAULT NOW(),
    confirmed_at TIMESTAMP,
    dispatched_at TIMESTAMP,
    created_at   TIMESTAMP NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_oms_orders_received_at  ON oms.oms_orders(received_at);
CREATE INDEX IF NOT EXISTS idx_oms_orders_web_order_id ON oms.oms_orders(web_order_id);

CREATE TABLE IF NOT EXISTS oms.shipments (
    id               BIGSERIAL PRIMARY KEY,
    oms_order_id     BIGINT NOT NULL REFERENCES oms.oms_orders(id),
    carrier_id       TEXT,
    tracking_number  TEXT,
    planned_delivery DATE,
    actual_delivery  DATE,
    is_on_time       BOOLEAN,
    is_complete      BOOLEAN NOT NULL DEFAULT TRUE,
    created_at       TIMESTAMP NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_shipments_created_at   ON oms.shipments(created_at);
CREATE INDEX IF NOT EXISTS idx_shipments_oms_order_id ON oms.shipments(oms_order_id);

CREATE TABLE IF NOT EXISTS oms.returns (
    id           BIGSERIAL PRIMARY KEY,
    oms_order_id BIGINT NOT NULL REFERENCES oms.oms_orders(id),
    reason       TEXT NOT NULL,
    status       TEXT NOT NULL DEFAULT 'pending'
                     CHECK (status IN ('pending','approved','rejected','completed')),
    created_at   TIMESTAMP NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_returns_created_at ON oms.returns(created_at);


-- ============================================================
-- SCHEMA: wms  (Warehouse Management System)
-- ============================================================
CREATE SCHEMA IF NOT EXISTS wms;

CREATE TABLE IF NOT EXISTS wms.wms_products (
    id             SERIAL PRIMARY KEY,
    web_product_id INTEGER NOT NULL,
    sku            TEXT NOT NULL UNIQUE,
    unit_cost      NUMERIC(10,2) NOT NULL CHECK (unit_cost > 0),
    created_at     TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS wms.inventory (
    id                SERIAL PRIMARY KEY,
    wms_product_id    INTEGER NOT NULL REFERENCES wms.wms_products(id),
    quantity_on_hand  INTEGER NOT NULL DEFAULT 0 CHECK (quantity_on_hand >= 0),
    quantity_reserved INTEGER NOT NULL DEFAULT 0 CHECK (quantity_reserved >= 0),
    reorder_point     INTEGER NOT NULL DEFAULT 10,
    updated_at        TIMESTAMP NOT NULL DEFAULT NOW(),
    UNIQUE (wms_product_id)
);
CREATE INDEX IF NOT EXISTS idx_inventory_updated_at ON wms.inventory(updated_at);

CREATE TABLE IF NOT EXISTS wms.inventory_movements (
    id             BIGSERIAL PRIMARY KEY,
    wms_product_id INTEGER NOT NULL REFERENCES wms.wms_products(id),
    movement_type  TEXT NOT NULL
                       CHECK (movement_type IN ('inbound','outbound','adjustment','return')),
    quantity       INTEGER NOT NULL CHECK (quantity > 0),
    created_at     TIMESTAMP NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_inv_movements_created_at    ON wms.inventory_movements(created_at);
CREATE INDEX IF NOT EXISTS idx_inv_movements_product_id    ON wms.inventory_movements(wms_product_id);

CREATE TABLE IF NOT EXISTS wms.picking_tasks (
    id             BIGSERIAL PRIMARY KEY,
    oms_order_id   BIGINT NOT NULL,
    wms_product_id INTEGER NOT NULL REFERENCES wms.wms_products(id),
    quantity       INTEGER NOT NULL CHECK (quantity >= 1),
    is_accurate    BOOLEAN NOT NULL DEFAULT TRUE,
    is_substituted BOOLEAN NOT NULL DEFAULT FALSE,
    completed_at   TIMESTAMP,
    created_at     TIMESTAMP NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_picking_tasks_created_at ON wms.picking_tasks(created_at);


-- ============================================================
-- SCHEMA: marketing  (Marketing Analytics Platform)
-- ============================================================
CREATE SCHEMA IF NOT EXISTS marketing;

CREATE TABLE IF NOT EXISTS marketing.traffic_sources (
    id           SERIAL PRIMARY KEY,
    name         TEXT NOT NULL UNIQUE,
    channel_type TEXT NOT NULL
                     CHECK (channel_type IN ('organic','google_ads','yandex_direct','email','referral','social')),
    created_at   TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS marketing.ad_campaigns (
    id           SERIAL PRIMARY KEY,
    source_id    INTEGER NOT NULL REFERENCES marketing.traffic_sources(id),
    name         TEXT NOT NULL,
    budget       NUMERIC(12,2),
    actual_spend NUMERIC(12,2) NOT NULL DEFAULT 0,
    start_date   DATE,
    end_date     DATE,
    created_at   TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS marketing.ad_campaign_daily_stats (
    id          BIGSERIAL PRIMARY KEY,
    campaign_id INTEGER NOT NULL REFERENCES marketing.ad_campaigns(id),
    stat_date   DATE NOT NULL,
    impressions INTEGER NOT NULL DEFAULT 0 CHECK (impressions >= 0),
    clicks      INTEGER NOT NULL DEFAULT 0 CHECK (clicks >= 0),
    spend       NUMERIC(10,2) NOT NULL DEFAULT 0 CHECK (spend >= 0),
    conversions INTEGER NOT NULL DEFAULT 0 CHECK (conversions >= 0),
    created_at  TIMESTAMP NOT NULL DEFAULT NOW(),
    UNIQUE (campaign_id, stat_date)
);
CREATE INDEX IF NOT EXISTS idx_ad_daily_stats_stat_date ON marketing.ad_campaign_daily_stats(stat_date);

CREATE TABLE IF NOT EXISTS marketing.visits (
    id           BIGSERIAL PRIMARY KEY,
    user_id      INTEGER,    -- NULL for anonymous visitors
    source_id    INTEGER REFERENCES marketing.traffic_sources(id),
    utm_campaign TEXT,
    duration_sec INTEGER NOT NULL DEFAULT 0 CHECK (duration_sec >= 0),
    page_views   INTEGER NOT NULL DEFAULT 1 CHECK (page_views >= 1),
    is_bounce    BOOLEAN NOT NULL DEFAULT FALSE,
    visited_at   TIMESTAMP NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_visits_visited_at ON marketing.visits(visited_at);
CREATE INDEX IF NOT EXISTS idx_visits_user_id    ON marketing.visits(user_id);
CREATE INDEX IF NOT EXISTS idx_visits_source_id  ON marketing.visits(source_id);

CREATE TABLE IF NOT EXISTS marketing.page_events (
    id         BIGSERIAL PRIMARY KEY,
    visit_id   BIGINT NOT NULL REFERENCES marketing.visits(id) ON DELETE CASCADE,
    event_type TEXT NOT NULL
                   CHECK (event_type IN ('pageview','product_view','add_to_cart','checkout','purchase')),
    page_url   TEXT,
    event_at   TIMESTAMP NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_page_events_visit_id ON marketing.page_events(visit_id);
CREATE INDEX IF NOT EXISTS idx_page_events_event_at ON marketing.page_events(event_at);


-- ============================================================
-- SCHEMA: metadata  (ETL pipeline watermarks)
-- ============================================================
CREATE SCHEMA IF NOT EXISTS metadata;

CREATE TABLE IF NOT EXISTS metadata.s3_max_dates (
    table_name TEXT PRIMARY KEY,
    max_date   DATE NOT NULL,
    updated_at TIMESTAMP NOT NULL DEFAULT NOW()
);

-- ============================================================
-- Grant usage on all schemas to the airflow user
-- ============================================================
DO $$
DECLARE
    schm TEXT;
BEGIN
    FOREACH schm IN ARRAY ARRAY['web','oms','wms','marketing','metadata'] LOOP
        EXECUTE format('GRANT USAGE ON SCHEMA %I TO airflow', schm);
        EXECUTE format('GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA %I TO airflow', schm);
        EXECUTE format('GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA %I TO airflow', schm);
        EXECUTE format('ALTER DEFAULT PRIVILEGES IN SCHEMA %I GRANT ALL ON TABLES TO airflow', schm);
        EXECUTE format('ALTER DEFAULT PRIVILEGES IN SCHEMA %I GRANT ALL ON SEQUENCES TO airflow', schm);
    END LOOP;
END;
$$;
