"""
Generate synthetic data for 3 KPI datamarts in staging schema (ClickHouse).
Covers all KPIs from diploma thesis section 1.5:
  - mart_new_sales:      Sales KPIs (1.1-1.8)
  - mart_new_marketing:  Marketing KPIs (2.1-2.7)
  - mart_new_inventory:  Inventory & Fulfillment KPIs (3.1-3.10)

Data represents the last 24 hours of hourly snapshots.
"""
import math
from datetime import datetime, timedelta

# ---------------------------------------------------------------------------
# Helper: deterministic pseudo-random float in [lo, hi]
# ---------------------------------------------------------------------------
def noise(seed_int: int, lo: float = 0.0, hi: float = 1.0) -> float:
    x = (abs(seed_int) * 1664525 + 1013904223) % (2 ** 32)
    x = (x * 22695477 + 1) % (2 ** 32)
    return lo + (hi - lo) * (x % 10000) / 10000.0


# ---------------------------------------------------------------------------
# Time helpers
# ---------------------------------------------------------------------------
def hour_factor(h: int) -> float:
    """Traffic multiplier by hour-of-day. Peaks at ~17h, trough at 4h."""
    return 0.12 + 0.88 * (1.0 + math.sin(2.0 * math.pi * (h - 10.0) / 24.0)) / 2.0


now_h = datetime.now().replace(minute=0, second=0, microsecond=0)
hours = [now_h - timedelta(hours=23 - i) for i in range(24)]  # oldest → newest


# ---------------------------------------------------------------------------
# PRODUCT CATALOG
# (category, name, unit_price, unit_cost, peak_orders_at_peak_hour)
# ---------------------------------------------------------------------------
PRODUCTS = [
    ("Electronics",    "Smartphone X12",          12999.0, 7800.0,  3.0),
    ("Electronics",    "Wireless Headphones Pro",  4499.0, 1980.0,  5.0),
    ("Electronics",    "Smart Watch Series 5",     8499.0, 4500.0,  2.0),
    ("Electronics",    "Laptop Pro 15\"",          54999.0, 34000.0, 1.0),
    ("Clothing",       "Winter Jacket Premium",    6499.0, 2400.0,  4.0),
    ("Clothing",       "Running Shoes Speed",      4199.0, 1750.0,  6.0),
    ("Clothing",       "Casual T-Shirt Cotton",    1199.0,  380.0, 12.0),
    ("Home & Garden",  "Coffee Maker Deluxe",      3499.0, 1580.0,  4.0),
    ("Home & Garden",  "Robot Vacuum Pro",         21999.0, 12800.0, 2.0),
    ("Home & Garden",  "Air Purifier Smart",       9499.0, 5400.0,  2.0),
    ("Sports",         "Dumbbells Set 20 kg",      3199.0, 1380.0,  3.0),
    ("Sports",         "Yoga Mat Premium",         1799.0,  680.0,  5.0),
    ("Sports",         "Cycling Helmet Safe",      2799.0, 1280.0,  3.0),
    ("Beauty",         "Hair Dryer Pro 2000W",     4799.0, 1980.0,  4.0),
    ("Beauty",         "Face Serum Vitamin C",     2199.0,  580.0,  7.0),
]

# ---------------------------------------------------------------------------
# CHANNEL CATALOG
# (name, type, base_sessions_peak, conv_rate, cpc_base, hourly_budget)
# ---------------------------------------------------------------------------
CHANNELS = [
    ("Google Ads",          "paid_search",  160, 0.048, 28.0, 4800),
    ("Yandex Direct",       "paid_search",  120, 0.043, 22.0, 3400),
    ("Facebook/Instagram",  "paid_social",  220, 0.026, 16.0, 3100),
    ("VK Target",           "paid_social",  80,  0.021, 11.0, 1400),
    ("Organic Search",      "organic",      310, 0.040, 0.0,  0),
    ("Email Newsletter",    "email",        65,  0.082, 0.0,  450),
    ("Direct",              "direct",       90,  0.062, 0.0,  0),
]

# ---------------------------------------------------------------------------
# 1. MART_NEW_SALES  (360 rows: 24h × 15 products)
# ---------------------------------------------------------------------------
SALES_COLS = (
    "snapshot_hour, category_name, product_name, "
    "total_revenue, total_cogs, gross_profit, gross_margin_pct, "
    "total_orders, total_units, aov, avg_items_per_order, "
    "total_sessions, cart_adds, converted_sessions, "
    "conversion_rate, cart_abandon_rate, "
    "unique_customers, new_customers, repeat_customers, estimated_ltv"
)

sales_rows = []
for h_i, h_time in enumerate(hours):
    hf = hour_factor(h_time.hour)
    for p_i, (cat, prod, price, cost, peak_ord) in enumerate(PRODUCTS):
        s = h_i * 100 + p_i  # unique seed per (hour, product)

        orders = max(0, round(peak_ord * hf * noise(s, 0.82, 1.18)))

        # Units per order: 1.0–1.4
        units = max(orders, round(orders * noise(s + 50, 1.0, 1.4))) if orders > 0 else 0

        # Price discount noise (0.95–1.00)
        revenue = round(units * price * noise(s + 100, 0.95, 1.00), 2)
        cogs    = round(units * cost, 2)
        gp      = round(revenue - cogs, 2)
        gm_pct  = round(gp / revenue * 100, 2) if revenue > 0 else 0.0

        aov       = round(revenue / orders, 2) if orders > 0 else 0.0
        avg_items = round(units / orders, 2)    if orders > 0 else 0.0

        # Sessions (2.5–4.5% conversion rate)
        cr = noise(s + 200, 0.025, 0.045)
        total_sessions = max(orders + 5, round(orders / cr)) if orders > 0 else max(8, round(peak_ord * hf * 12))

        # Cart adds (28–42% of sessions add to cart)
        cart_adds      = max(orders, round(total_sessions * noise(s + 300, 0.28, 0.42)))
        conv_rate_pct  = round(orders / total_sessions * 100, 2) if total_sessions > 0 else 0.0
        abandon_pct    = round((cart_adds - orders) / cart_adds * 100, 2) if cart_adds > 0 else 0.0

        unique_cust  = max(1, round(orders * noise(s + 400, 0.88, 0.98))) if orders > 0 else 0
        new_cust     = round(unique_cust * noise(s + 500, 0.38, 0.52))
        repeat_cust  = unique_cust - new_cust

        # LTV estimate: avg_order_value × ~10 expected lifetime orders × cohort multiplier
        estimated_ltv = round(aov * 10.0 * noise(s + 600, 0.85, 1.25), 2) if aov > 0 else 0.0

        ts = h_time.strftime("%Y-%m-%d %H:%M:%S")
        sales_rows.append(
            f"('{ts}','{cat}','{prod}',"
            f"{revenue},{cogs},{gp},{gm_pct},"
            f"{orders},{units},{aov},{avg_items},"
            f"{total_sessions},{cart_adds},{orders},"
            f"{conv_rate_pct},{abandon_pct},"
            f"{unique_cust},{new_cust},{repeat_cust},{estimated_ltv})"
        )

# ---------------------------------------------------------------------------
# 2. MART_NEW_MARKETING  (168 rows: 24h × 7 channels)
# ---------------------------------------------------------------------------
MARKETING_COLS = (
    "snapshot_hour, channel_name, channel_type, "
    "site_traffic, unique_visitors, avg_session_duration_sec, avg_time_on_site_min, "
    "bounce_rate, visit_frequency_avg, conversions, "
    "impressions, clicks, ctr, cpc, total_spend, "
    "cpa, attributed_revenue, roas, romi, "
    "new_customers, cac, "
    "blog_sessions, chat_sessions_initiated"
)

# Baseline session durations per type
SESSION_DUR = {
    "paid_search": (120, 180),
    "paid_social": (80,  130),
    "organic":     (180, 280),
    "email":       (160, 240),
    "direct":      (190, 270),
}
BOUNCE_RATE = {
    "paid_search": (38, 52),
    "paid_social": (52, 68),
    "organic":     (32, 45),
    "email":       (22, 35),
    "direct":      (20, 32),
}

# Avg order value across all products (weighted roughly)
AVG_ORDER_VAL = 5200.0

marketing_rows = []
for h_i, h_time in enumerate(hours):
    hf = hour_factor(h_time.hour)
    for c_i, (ch_name, ch_type, base_sess, cr, cpc_base, hourly_budget) in enumerate(CHANNELS):
        s = h_i * 200 + c_i * 13

        sessions   = max(2, round(base_sess * hf * noise(s, 0.80, 1.20)))
        unique_vis = max(1, round(sessions * noise(s + 10, 0.70, 0.85)))

        dur_lo, dur_hi = SESSION_DUR[ch_type]
        avg_dur  = round(noise(s + 20, dur_lo, dur_hi), 1)
        avg_min  = round(avg_dur / 60.0, 2)

        br_lo, br_hi = BOUNCE_RATE[ch_type]
        bounce   = round(noise(s + 30, br_lo, br_hi), 2)

        visit_freq = round(noise(s + 40, 1.0, 1.6), 2)

        conversions = max(0, round(sessions * cr * noise(s + 50, 0.80, 1.20)))

        # Paid channels: impressions & spend
        if cpc_base > 0:
            ctr_pct       = round(noise(s + 60, 2.8, 6.5), 2)
            impressions   = max(clicks := sessions, round(sessions / (ctr_pct / 100)))
            clicks        = sessions  # all paid traffic = clicks
            spend         = round(sessions * cpc_base * noise(s + 70, 0.88, 1.12), 2)
            cpc           = round(spend / sessions, 2) if sessions > 0 else cpc_base
            cpa           = round(spend / conversions, 2) if conversions > 0 else 0.0
        else:
            impressions   = 0
            clicks        = 0
            ctr_pct       = 0.0
            spend         = round(hourly_budget * hf * noise(s + 70, 0.85, 1.15), 2) if hourly_budget > 0 else 0.0
            cpc           = 0.0
            cpa           = round(spend / conversions, 2) if conversions > 0 and spend > 0 else 0.0

        attr_revenue = round(conversions * AVG_ORDER_VAL * noise(s + 80, 0.90, 1.10), 2)
        roas         = round(attr_revenue / spend, 2) if spend > 0 else 0.0
        romi         = round((attr_revenue - spend) / spend * 100.0, 2) if spend > 0 else 0.0

        new_customers = max(0, round(conversions * noise(s + 90, 0.38, 0.55)))
        cac           = round(spend / new_customers, 2) if new_customers > 0 and spend > 0 else 0.0

        blog_sess     = round(sessions * noise(s + 100, 0.04, 0.12)) if ch_type in ("organic", "email") else 0
        chat_init     = max(0, round(sessions * noise(s + 110, 0.020, 0.055)))

        ts = h_time.strftime("%Y-%m-%d %H:%M:%S")
        marketing_rows.append(
            f"('{ts}','{ch_name}','{ch_type}',"
            f"{sessions},{unique_vis},{avg_dur},{avg_min},"
            f"{bounce},{visit_freq},{conversions},"
            f"{impressions},{clicks},{ctr_pct},{cpc},{spend},"
            f"{cpa},{attr_revenue},{roas},{romi},"
            f"{new_customers},{cac},"
            f"{blog_sess},{chat_init})"
        )

# ---------------------------------------------------------------------------
# 3. MART_NEW_INVENTORY  (360 rows: 24h × 15 products)
# ---------------------------------------------------------------------------
INVENTORY_COLS = (
    "snapshot_hour, category_name, product_name, sku, "
    "unit_cost, quantity_on_hand, quantity_reserved, quantity_available, reorder_point, "
    "inventory_value, is_out_of_stock, is_below_reorder, "
    "hourly_outbound_qty, daily_sales_avg, days_supply, inventory_turns_annual, gmroi, "
    "total_shipments, otif_rate, order_accuracy, substitution_rate, "
    "return_rate, avg_lead_time_hours, damage_free_rate, out_of_stock_events"
)

# Base stock levels per product (at snapshot time 0 = 24h ago)
BASE_STOCK = {
    "Smartphone X12":          350,
    "Wireless Headphones Pro":  520,
    "Smart Watch Series 5":    280,
    "Laptop Pro 15\"":          90,
    "Winter Jacket Premium":   680,
    "Running Shoes Speed":     850,
    "Casual T-Shirt Cotton":  1800,
    "Coffee Maker Deluxe":     420,
    "Robot Vacuum Pro":        150,
    "Air Purifier Smart":      230,
    "Dumbbells Set 20 kg":     310,
    "Yoga Mat Premium":        590,
    "Cycling Helmet Safe":     270,
    "Hair Dryer Pro 2000W":    380,
    "Face Serum Vitamin C":    760,
}

# Daily average sales per product (units/day)
DAILY_SALES = {
    "Smartphone X12":          42,
    "Wireless Headphones Pro":  68,
    "Smart Watch Series 5":    28,
    "Laptop Pro 15\"":          12,
    "Winter Jacket Premium":   55,
    "Running Shoes Speed":     80,
    "Casual T-Shirt Cotton":  185,
    "Coffee Maker Deluxe":     55,
    "Robot Vacuum Pro":        22,
    "Air Purifier Smart":      26,
    "Dumbbells Set 20 kg":     38,
    "Yoga Mat Premium":        72,
    "Cycling Helmet Safe":     38,
    "Hair Dryer Pro 2000W":    52,
    "Face Serum Vitamin C":    98,
}

REORDER_POINTS = {
    "Smartphone X12":          80,
    "Wireless Headphones Pro": 120,
    "Smart Watch Series 5":    60,
    "Laptop Pro 15\"":          25,
    "Winter Jacket Premium":  100,
    "Running Shoes Speed":    150,
    "Casual T-Shirt Cotton":  300,
    "Coffee Maker Deluxe":     80,
    "Robot Vacuum Pro":        35,
    "Air Purifier Smart":      50,
    "Dumbbells Set 20 kg":     60,
    "Yoga Mat Premium":       120,
    "Cycling Helmet Safe":     55,
    "Hair Dryer Pro 2000W":    70,
    "Face Serum Vitamin C":   140,
}

inventory_rows = []
for h_i, h_time in enumerate(hours):
    hf = hour_factor(h_time.hour)
    for p_i, (cat, prod, price, cost, peak_ord) in enumerate(PRODUCTS):
        s = h_i * 300 + p_i * 17

        # Decrease stock realistically over 24 hours
        daily_avg = DAILY_SALES[prod]
        hourly_avg = daily_avg / 24.0
        outbound = max(0, round(hourly_avg * hf * noise(s, 0.75, 1.30)))

        # Running balance: start from base stock and deplete
        base = BASE_STOCK[prod]
        total_sold_so_far = sum(
            max(0, round((DAILY_SALES[prod] / 24.0) * hour_factor(hours[j].hour) * noise(j * 300 + p_i * 17, 0.75, 1.30)))
            for j in range(h_i + 1)
        )
        qty_on_hand = max(0, base - total_sold_so_far)

        # Occasionally restock (if below reorder point at start of day)
        if h_i == 0 and qty_on_hand < REORDER_POINTS[prod]:
            qty_on_hand += round(REORDER_POINTS[prod] * 2.5)

        qty_reserved = max(0, round(qty_on_hand * noise(s + 10, 0.05, 0.15)))
        qty_available = max(0, qty_on_hand - qty_reserved)
        reorder_pt = REORDER_POINTS[prod]

        inv_value = round(qty_on_hand * cost, 2)
        is_oos   = 1 if qty_available == 0 else 0
        is_below = 1 if qty_on_hand < reorder_pt else 0

        days_supply = round(qty_available / daily_avg, 1) if daily_avg > 0 and qty_available > 0 else 0.0
        inv_turns   = round(365.0 / days_supply, 2) if days_supply > 0 else 0.0

        gross_margin = (price - cost) / price if price > 0 else 0
        gmroi        = round(gross_margin * inv_turns, 2) if inv_turns > 0 else 0.0

        # Fulfillment metrics (per-hour snapshot)
        total_shipments  = max(0, round(outbound * noise(s + 20, 0.85, 1.00)))
        otif_rate        = round(noise(s + 30, 88.0, 98.5), 2)
        order_accuracy   = round(noise(s + 40, 94.0, 99.5), 2)
        substitution_rate = round(noise(s + 50, 1.0, 6.5), 2)
        return_rate       = round(noise(s + 60, 0.8, 4.5), 2)
        avg_lead_time_h   = round(noise(s + 70, 18.0, 48.0), 1)
        damage_free_rate  = round(noise(s + 80, 97.0, 99.8), 2)
        oos_events        = 1 if is_oos else 0

        # SKU: category prefix + 4-digit product index
        sku = f"SKU-{cat[:3].upper()}-{p_i+1:04d}"

        ts = h_time.strftime("%Y-%m-%d %H:%M:%S")
        inventory_rows.append(
            f"('{ts}','{cat}','{prod}','{sku}',"
            f"{cost},{qty_on_hand},{qty_reserved},{qty_available},{reorder_pt},"
            f"{inv_value},{is_oos},{is_below},"
            f"{outbound},{round(daily_avg,1)},{days_supply},{inv_turns},{gmroi},"
            f"{total_shipments},{otif_rate},{order_accuracy},{substitution_rate},"
            f"{return_rate},{avg_lead_time_h},{damage_free_rate},{oos_events})"
        )

# ---------------------------------------------------------------------------
# Build complete SQL
# ---------------------------------------------------------------------------
DDL = """
-- ============================================================
-- mart_new_sales  (Sales KPIs 1.1-1.8)
-- ============================================================
CREATE TABLE IF NOT EXISTS staging.mart_new_sales
(
    snapshot_hour           DateTime     COMMENT 'Start of the hour',
    category_name           String       COMMENT 'Product category',
    product_name            String       COMMENT 'Product name',
    -- Revenue metrics (KPI 1.1, 1.8)
    total_revenue           Float64      COMMENT 'Gross revenue',
    total_cogs              Float64      COMMENT 'Cost of goods sold (COGS) – KPI 1.8',
    gross_profit            Float64      COMMENT 'Revenue minus COGS',
    gross_margin_pct        Float64      COMMENT 'Gross margin % – KPI 1.1',
    -- Order metrics (KPI 1.2, 1.3, 1.7)
    total_orders            Int32        COMMENT 'Number of placed orders – KPI 1.2',
    total_units             Int32        COMMENT 'Total units sold',
    aov                     Float64      COMMENT 'Average order value (AOV) – KPI 1.3',
    avg_items_per_order     Float64      COMMENT 'Avg items per order – KPI 1.7',
    -- Funnel metrics (KPI 1.4, 1.5)
    total_sessions          Int32        COMMENT 'Product-page sessions',
    cart_adds               Int32        COMMENT 'Sessions with cart addition',
    converted_sessions      Int32        COMMENT 'Sessions resulting in purchase',
    conversion_rate         Float64      COMMENT 'Conversion rate % – KPI 1.4',
    cart_abandon_rate       Float64      COMMENT 'Cart abandon rate % – KPI 1.5',
    -- Customer metrics (KPI 1.6)
    unique_customers        Int32        COMMENT 'Distinct buyers this hour',
    new_customers           Int32        COMMENT 'First-time buyers',
    repeat_customers        Int32        COMMENT 'Returning buyers',
    estimated_ltv           Float64      COMMENT 'Estimated customer LTV – KPI 1.6'
) ENGINE = MergeTree()
  ORDER BY (snapshot_hour, category_name, product_name)
  PARTITION BY toYYYYMMDD(snapshot_hour);

-- ============================================================
-- mart_new_marketing  (Marketing KPIs 2.1-2.7)
-- ============================================================
CREATE TABLE IF NOT EXISTS staging.mart_new_marketing
(
    snapshot_hour               DateTime COMMENT 'Start of the hour',
    channel_name                String   COMMENT 'Marketing channel name',
    channel_type                String   COMMENT 'Channel type: paid_search/paid_social/organic/email/direct',
    -- Traffic (KPI 2.1, 2.5, 2.6)
    site_traffic                Int32    COMMENT 'Total sessions – KPI 2.1',
    unique_visitors             Int32    COMMENT 'Unique visitors – KPI 2.1',
    avg_session_duration_sec    Float64  COMMENT 'Avg session duration in seconds – KPI 2.5',
    avg_time_on_site_min        Float64  COMMENT 'Avg time on site (minutes) – KPI 2.5',
    bounce_rate                 Float64  COMMENT 'Bounce rate %',
    visit_frequency_avg         Float64  COMMENT 'Avg visits per unique user – KPI 2.6',
    conversions                 Int32    COMMENT 'Sessions converting to purchase',
    -- Ad performance (KPI 2.3, 2.4)
    impressions                 Int32    COMMENT 'Ad impressions (paid channels)',
    clicks                      Int32    COMMENT 'Ad clicks (paid channels)',
    ctr                         Float64  COMMENT 'Click-through rate % (paid)',
    cpc                         Float64  COMMENT 'Cost per click – KPI 2.4',
    total_spend                 Float64  COMMENT 'Ad spend this hour',
    -- Efficiency (KPI 2.2, 2.3, 2.4)
    cpa                         Float64  COMMENT 'Cost per acquisition – KPI 2.4',
    attributed_revenue          Float64  COMMENT 'Revenue attributed to channel',
    roas                        Float64  COMMENT 'Return on ad spend – KPI 2.3',
    romi                        Float64  COMMENT 'Return on marketing investment % – KPI 2.3',
    new_customers               Int32    COMMENT 'New customers acquired',
    cac                         Float64  COMMENT 'Customer acquisition cost – KPI 2.2',
    -- Engagement (KPI 2.7)
    blog_sessions               Int32    COMMENT 'Blog / content sessions – KPI 2.7',
    chat_sessions_initiated     Int32    COMMENT 'Chat sessions initiated – KPI 2.7'
) ENGINE = MergeTree()
  ORDER BY (snapshot_hour, channel_name)
  PARTITION BY toYYYYMMDD(snapshot_hour);

-- ============================================================
-- mart_new_inventory  (Inventory & Fulfillment KPIs 3.1-3.10)
-- ============================================================
CREATE TABLE IF NOT EXISTS staging.mart_new_inventory
(
    snapshot_hour           DateTime COMMENT 'Start of the hour',
    category_name           String   COMMENT 'Product category',
    product_name            String   COMMENT 'Product name',
    sku                     String   COMMENT 'Stock-keeping unit',
    -- Stock levels (KPI 3.1)
    unit_cost               Float64  COMMENT 'Unit procurement cost',
    quantity_on_hand        Int32    COMMENT 'Units on hand – KPI 3.1',
    quantity_reserved       Int32    COMMENT 'Reserved for pending orders',
    quantity_available      Int32    COMMENT 'Available for sale – KPI 3.1',
    reorder_point           Int32    COMMENT 'Reorder trigger level',
    inventory_value         Float64  COMMENT 'Stock value at cost',
    is_out_of_stock         UInt8    COMMENT '1 = zero available – KPI 3.5',
    is_below_reorder        UInt8    COMMENT '1 = below reorder point',
    -- Velocity (KPI 3.2, 3.4)
    hourly_outbound_qty     Int32    COMMENT 'Units dispatched this hour',
    daily_sales_avg         Float64  COMMENT 'Avg units sold per day',
    days_supply             Float64  COMMENT 'Days until stockout at current pace – KPI 3.4',
    inventory_turns_annual  Float64  COMMENT 'Annual inventory turns – KPI 3.2',
    -- Efficiency (KPI 3.3)
    gmroi                   Float64  COMMENT 'Gross margin return on inventory – KPI 3.3',
    -- Fulfillment quality (KPI 3.6-3.10)
    total_shipments         Int32    COMMENT 'Shipments dispatched this hour',
    otif_rate               Float64  COMMENT 'On-Time-In-Full rate % – KPI 3.6',
    order_accuracy          Float64  COMMENT 'Order picking accuracy % – KPI 3.7',
    substitution_rate       Float64  COMMENT 'Substitution rate % – KPI 3.10',
    return_rate             Float64  COMMENT 'Return rate % – KPI 3.9',
    avg_lead_time_hours     Float64  COMMENT 'Avg order-to-ship hours – KPI 3.8',
    damage_free_rate        Float64  COMMENT 'Shipped damage-free % – KPI 3.9',
    out_of_stock_events     UInt8    COMMENT 'OOS event flag this hour – KPI 3.5'
) ENGINE = MergeTree()
  ORDER BY (snapshot_hour, category_name, product_name)
  PARTITION BY toYYYYMMDD(snapshot_hour);
"""

INSERT_SALES = (
    f"INSERT INTO staging.mart_new_sales ({SALES_COLS}) VALUES\n"
    + ",\n".join(sales_rows)
    + ";"
)

INSERT_MARKETING = (
    f"INSERT INTO staging.mart_new_marketing ({MARKETING_COLS}) VALUES\n"
    + ",\n".join(marketing_rows)
    + ";"
)

INSERT_INVENTORY = (
    f"INSERT INTO staging.mart_new_inventory ({INVENTORY_COLS}) VALUES\n"
    + ",\n".join(inventory_rows)
    + ";"
)

if __name__ == "__main__":
    import sys
    mode = sys.argv[1] if len(sys.argv) > 1 else "all"

    if mode in ("ddl", "all"):
        print(DDL)
    if mode in ("sales", "all"):
        print(INSERT_SALES)
    if mode in ("marketing", "all"):
        print(INSERT_MARKETING)
    if mode in ("inventory", "all"):
        print(INSERT_INVENTORY)
