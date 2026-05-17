"""
main.py – Entry point for the synthetic data generator container.

Lifecycle:
  1. Wait for Postgres to be ready.
  2. Bootstrap: insert reference data and 30-day historical dataset.
  3. Continuous loop: every INTERVAL_SECONDS insert a small realistic batch
     of new transactional events (users → sessions → carts → orders → OMS →
     WMS movements + shipments → marketing visits).
"""
import logging
import os
import random
import time
from datetime import date, timedelta

from db_writer import DbWriter
from generators import (
    generate_categories,
    generate_traffic_sources,
    generate_ad_campaigns,
    generate_ad_daily_stats,
    generate_products,
    generate_wms_products,
    generate_inventory_record,
    generate_inventory_movement,
    generate_picking_task,
    generate_users,
    generate_sessions,
    generate_cart_and_items,
    generate_order_from_cart,
    generate_oms_order,
    generate_shipment,
    generate_return,
    generate_visit,
    generate_page_events,
    _random_ts,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [generator] %(levelname)s %(message)s",
)
log = logging.getLogger(__name__)

# ------------------------------------------------------------------
# Config from environment
# ------------------------------------------------------------------
POSTGRES_HOST     = os.getenv("POSTGRES_HOST", "postgres")
POSTGRES_PORT     = os.getenv("POSTGRES_PORT", "5432")
POSTGRES_USER     = os.getenv("POSTGRES_USER", "airflow")
POSTGRES_PASSWORD = os.getenv("POSTGRES_PASSWORD", "airflow")
POSTGRES_DB       = os.getenv("POSTGRES_DB", "airflow")
INTERVAL_SECONDS  = int(os.getenv("GENERATOR_INTERVAL_SECONDS", "15"))
HISTORY_DAYS      = int(os.getenv("GENERATOR_HISTORY_DAYS", "30"))

DSN = (
    f"host={POSTGRES_HOST} port={POSTGRES_PORT} "
    f"user={POSTGRES_USER} password={POSTGRES_PASSWORD} dbname={POSTGRES_DB}"
)


# ------------------------------------------------------------------
# Wait until Postgres accepts connections
# ------------------------------------------------------------------

def wait_for_postgres(max_retries: int = 30, delay: int = 5) -> DbWriter:
    import psycopg2
    for attempt in range(1, max_retries + 1):
        try:
            writer = DbWriter(DSN)
            log.info("Postgres is ready.")
            return writer
        except Exception as exc:
            log.warning("Postgres not ready (attempt %d/%d): %s", attempt, max_retries, exc)
            time.sleep(delay)
    raise RuntimeError("Could not connect to Postgres after %d attempts" % max_retries)


# ------------------------------------------------------------------
# Bootstrap
# ------------------------------------------------------------------

def bootstrap(writer: DbWriter):
    """Insert reference data and historical records (idempotent)."""

    # --- categories ---
    if writer.count("web.categories") == 0:
        log.info("Inserting categories...")
        cats = generate_categories()
        for cat in cats:
            writer.insert_one("web.categories", cat)
        log.info("Inserted %d categories.", len(cats))

    cat_ids = writer.fetch_ids("web.categories")
    leaf_cat_ids = [cid for cid in cat_ids if cid in [2, 3, 5, 6, 8, 9, 10]]

    # --- products ---
    if writer.count("web.products") == 0:
        log.info("Inserting products...")
        products = generate_products(category_ids=leaf_cat_ids, n=80)
        p_ids = writer.insert_many("web.products", products)
        log.info("Inserted %d products.", len(p_ids))

    product_ids = writer.fetch_ids("web.products")
    product_prices: dict[int, tuple[float, float]] = {}
    with writer.conn.cursor() as cur:
        cur.execute("SELECT id, price, cost_price FROM web.products")
        for pid, price, cost in cur.fetchall():
            product_prices[pid] = (float(price), float(cost))

    # --- wms_products ---
    if writer.count("wms.wms_products") == 0:
        log.info("Inserting WMS products & inventory...")
        wms_prods = generate_wms_products(web_product_ids=product_ids)
        wms_ids = writer.insert_many("wms.wms_products", wms_prods)
        inv_records = [generate_inventory_record(wid) for wid in wms_ids if wid]
        writer.insert_many("wms.inventory", inv_records)
        log.info("Inserted %d WMS products.", len(wms_ids))

    wms_product_ids = writer.fetch_ids("wms.wms_products")

    # --- traffic sources ---
    if writer.count("marketing.traffic_sources") == 0:
        log.info("Inserting traffic sources...")
        sources = generate_traffic_sources()
        writer.insert_many("marketing.traffic_sources", sources, returning="id")
        log.info("Inserted %d traffic sources.", len(sources))

    source_ids = writer.fetch_ids("marketing.traffic_sources")
    # paid source IDs (google_ads, yandex_direct)
    paid_source_ids: list[int] = []
    with writer.conn.cursor() as cur:
        cur.execute(
            "SELECT id FROM marketing.traffic_sources "
            "WHERE channel_type IN ('google_ads','yandex_direct')"
        )
        paid_source_ids = [r[0] for r in cur.fetchall()]

    # --- ad_campaigns ---
    if writer.count("marketing.ad_campaigns") == 0:
        log.info("Inserting ad campaigns...")
        campaigns = generate_ad_campaigns(source_ids=paid_source_ids)
        writer.insert_many("marketing.ad_campaigns", campaigns, returning="id")
        log.info("Inserted %d campaigns.", len(campaigns))

    campaign_ids = writer.fetch_ids("marketing.ad_campaigns")

    # --- historical data (30 days) ---
    if writer.count("web.users") < 100:
        log.info("Generating %d-day historical dataset...", HISTORY_DAYS)
        _generate_historical(
            writer,
            product_ids=product_ids,
            product_prices=product_prices,
            wms_product_ids=wms_product_ids,
            source_ids=source_ids,
            campaign_ids=campaign_ids,
            days=HISTORY_DAYS,
        )
        log.info("Historical dataset ready.")


def _generate_historical(
    writer: DbWriter,
    product_ids, product_prices, wms_product_ids,
    source_ids, campaign_ids, days: int,
):
    import random
    from datetime import datetime

    # 1000 users spread over the history period
    users = generate_users(1000)
    user_ids = writer.insert_web_users_resolve_ids(users)
    log.info("  Inserted %d historical users.", len(user_ids))

    # Daily: sessions, carts, orders, oms, wms, marketing
    for d in range(days, 0, -1):
        day = date.today() - timedelta(days=d)
        n_sessions = random.randint(80, 300)

        # sessions
        sessions_data = []
        for _ in range(n_sessions):
            uid = random.choice(user_ids)
            s = generate_sessions([uid], source_ids, 1)[0]
            # Fix timestamps to the historical day
            hour = random.randint(7, 23)
            start = datetime(day.year, day.month, day.day, hour,
                             random.randint(0, 59), random.randint(0, 59))
            s["started_at"] = start
            s["ended_at"] = start + timedelta(seconds=s.get("duration", 300))
            sessions_data.append(s)
        sess_ids = writer.insert_many("web.sessions", sessions_data)

        # carts (50% of sessions get a cart)
        for i, sess_id in enumerate(sess_ids):
            if random.random() > 0.50 or not sess_id:
                continue
            uid = sessions_data[i]["user_id"]
            cart, items = generate_cart_and_items(uid, sess_id, product_ids, product_prices)
            cart["created_at"] = sessions_data[i]["started_at"]
            cart["updated_at"] = sessions_data[i]["started_at"]
            cart_id = writer.insert_one("web.carts", cart)
            for it in items:
                it["cart_id"] = cart_id
            writer.insert_many("web.cart_items", items, returning="id")

            if cart["status"] == "converted":
                order, order_items = generate_order_from_cart({"id": cart_id, "user_id": uid, "status": "converted", "created_at": cart["created_at"]}, items)
                order_id = writer.insert_one("web.orders", order)
                for oi in order_items:
                    oi["order_id"] = order_id
                writer.insert_many("web.order_items", oi, returning=None)

                # OMS
                oms_order = generate_oms_order(web_order_id=order_id)
                oms_order["received_at"] = order["created_at"]
                oms_id = writer.insert_one("oms.oms_orders", oms_order)

                # Shipment
                if oms_order["status"] in ("dispatched", "delivered"):
                    shipment = generate_shipment(oms_order_id=oms_id)
                    writer.insert_one("oms.shipments", shipment)

                    # Picking tasks
                    for oi in order_items:
                        wms_pid = random.choice(wms_product_ids)
                        task = generate_picking_task(oms_id, wms_pid)
                        writer.insert_one("wms.picking_tasks", task)

                # Occasional return (~5%)
                if random.random() < 0.05:
                    ret = generate_return(oms_order_id=oms_id)
                    writer.insert_one("oms.returns", ret)

        # WMS outbound movements
        for _ in range(random.randint(5, 20)):
            wms_pid = random.choice(wms_product_ids)
            mov = generate_inventory_movement(wms_pid)
            writer.insert_one("wms.inventory_movements", mov)

        # Marketing visits
        n_visits = random.randint(100, 400)
        for _ in range(n_visits):
            visit = generate_visit(user_ids=[uid for uid in user_ids if uid], source_ids=source_ids)
            visit["visited_at"] = datetime(day.year, day.month, day.day,
                                           random.randint(7, 23), random.randint(0, 59))
            visit_id = writer.insert_one("marketing.visits", visit)
            events = generate_page_events(visit_id, n_events=random.randint(1, 5))
            writer.insert_many("marketing.page_events", events, returning=None)

        # Ad daily stats
        stats = generate_ad_daily_stats(campaign_ids, stat_date=day)
        for stat in stats:
            try:
                writer.upsert_many(
                    "marketing.ad_campaign_daily_stats",
                    [stat],
                    conflict_cols=["campaign_id", "stat_date"],
                    update_cols=["impressions", "clicks", "spend", "conversions"],
                    returning="id",
                )
            except Exception:
                writer.conn.rollback()

        if d % 5 == 0:
            log.info("  Historical data: %d days remaining...", d)


# ------------------------------------------------------------------
# Continuous generation loop
# ------------------------------------------------------------------

def run_continuous(writer: DbWriter):
    """Insert small batches of fresh data every INTERVAL_SECONDS."""
    log.info("Starting continuous generation (interval=%ds)...", INTERVAL_SECONDS)

    user_ids      = writer.fetch_ids("web.users", limit=5000)
    product_ids   = writer.fetch_ids("web.products")
    wms_product_ids = writer.fetch_ids("wms.wms_products")
    source_ids    = writer.fetch_ids("marketing.traffic_sources")
    campaign_ids  = writer.fetch_ids("marketing.ad_campaigns")
    product_prices: dict = {}
    with writer.conn.cursor() as cur:
        cur.execute("SELECT id, price, cost_price FROM web.products")
        for pid, price, cost in cur.fetchall():
            product_prices[pid] = (float(price), float(cost))

    cycle = 0
    while True:
        try:
            cycle += 1
            log.info("Cycle %d: inserting fresh batch...", cycle)

            # Occasionally add a new user
            if random.random() < 0.30:
                new_users = generate_users(random.randint(1, 5))
                new_ids = writer.insert_web_users_resolve_ids(new_users)
                user_ids.extend([u for u in new_ids if u and u not in user_ids])

            # Sessions (5-20 per cycle)
            n_sess = random.randint(5, 20)
            sess_data = generate_sessions(user_ids, source_ids, n_sess)
            sess_ids = writer.insert_many("web.sessions", sess_data)

            # Carts + orders for ~40% of sessions
            for i, sess_id in enumerate(sess_ids):
                if random.random() > 0.40 or not sess_id:
                    continue
                uid = sess_data[i]["user_id"] or random.choice(user_ids)
                cart, items = generate_cart_and_items(uid, sess_id, product_ids, product_prices)
                cart_id = writer.insert_one("web.carts", cart)
                for it in items:
                    it["cart_id"] = cart_id
                writer.insert_many("web.cart_items", items, returning=None)

                if cart["status"] == "converted":
                    order, order_items = generate_order_from_cart(
                        {"id": cart_id, "user_id": uid, "status": "converted",
                         "created_at": cart["created_at"]},
                        items,
                    )
                    order_id = writer.insert_one("web.orders", order)
                    for oi in order_items:
                        oi["order_id"] = order_id
                    writer.insert_many("web.order_items", order_items, returning=None)

                    oms_order = generate_oms_order(web_order_id=order_id)
                    oms_id = writer.insert_one("oms.oms_orders", oms_order)
                    if oms_order["status"] in ("dispatched", "delivered"):
                        writer.insert_one("oms.shipments", generate_shipment(oms_id))
                        for oi in order_items:
                            writer.insert_one(
                                "wms.picking_tasks",
                                generate_picking_task(oms_id, random.choice(wms_product_ids)),
                            )
                    if random.random() < 0.05:
                        writer.insert_one("oms.returns", generate_return(oms_id))

            # WMS movements (1-5 per cycle)
            for _ in range(random.randint(1, 5)):
                writer.insert_one(
                    "wms.inventory_movements",
                    generate_inventory_movement(random.choice(wms_product_ids)),
                )

            # Marketing visits (10-40 per cycle)
            for _ in range(random.randint(10, 40)):
                visit = generate_visit(user_ids, source_ids)
                visit_id = writer.insert_one("marketing.visits", visit)
                events = generate_page_events(visit_id, n_events=random.randint(1, 4))
                writer.insert_many("marketing.page_events", events, returning=None)

            # Ad daily stats for today
            today_stats = generate_ad_daily_stats(campaign_ids, date.today())
            for stat in today_stats:
                try:
                    writer.upsert_many(
                        "marketing.ad_campaign_daily_stats",
                        [stat],
                        conflict_cols=["campaign_id", "stat_date"],
                        update_cols=["impressions", "clicks", "spend", "conversions"],
                        returning="id",
                    )
                except Exception:
                    writer.conn.rollback()

            log.info("Cycle %d complete. Sleeping %ds...", cycle, INTERVAL_SECONDS)
        except Exception as exc:
            log.error("Error in generation cycle: %s", exc, exc_info=True)
            try:
                writer.conn.rollback()
            except Exception:
                pass

        time.sleep(INTERVAL_SECONDS)


# ------------------------------------------------------------------
# Entrypoint
# ------------------------------------------------------------------

if __name__ == "__main__":
    writer = wait_for_postgres()
    bootstrap(writer)
    run_continuous(writer)
