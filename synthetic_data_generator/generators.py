"""
generators.py – Pure data-generation functions for the synthetic OLTP layer.

All functions are side-effect-free: they accept parameters, use Faker for
realistic-looking values, and return plain Python dicts / lists of dicts.
No database calls here – testable without any infrastructure.
"""
import random
from datetime import datetime, date, timedelta
from typing import Optional

from faker import Faker

_fake = Faker("ru_RU")
Faker.seed(0)  # reproducible by default; callers can reset with Faker.seed(n)


# ===================================================================
# Reference / lookup data (stable, inserted once on bootstrap)
# ===================================================================

CATEGORY_TREE = [
    {"name": "Электроника",       "parent_id": None},
    {"name": "Смартфоны",         "parent_id": 1},
    {"name": "Ноутбуки",          "parent_id": 1},
    {"name": "Одежда и обувь",    "parent_id": None},
    {"name": "Мужская одежда",    "parent_id": 4},
    {"name": "Женская одежда",    "parent_id": 4},
    {"name": "Товары для дома",   "parent_id": None},
    {"name": "Кухонная техника",  "parent_id": 7},
    {"name": "Мебель",            "parent_id": 7},
    {"name": "Спорт и туризм",    "parent_id": None},
]

TRAFFIC_SOURCE_DEFS = [
    {"name": "Google Organic",  "channel_type": "organic"},
    {"name": "Yandex Organic",  "channel_type": "organic"},
    {"name": "Google Ads",      "channel_type": "google_ads"},
    {"name": "Yandex Direct",   "channel_type": "yandex_direct"},
    {"name": "Email Newsletter","channel_type": "email"},
    {"name": "VK Referral",     "channel_type": "referral"},
    {"name": "Telegram Social", "channel_type": "social"},
]

PRODUCT_TEMPLATES = {
    2: [  # Смартфоны
        ("iPhone 15 Pro",      89990, 55000),
        ("Samsung Galaxy S24", 79990, 48000),
        ("Xiaomi 14",          64990, 38000),
        ("Realme GT 5",        34990, 20000),
    ],
    3: [  # Ноутбуки
        ("MacBook Air M2",     119990, 75000),
        ("Dell XPS 15",        109990, 68000),
        ("Lenovo ThinkPad X1",  99990, 62000),
        ("ASUS ZenBook 14",     69990, 42000),
    ],
    5: [  # Мужская одежда
        ("Джинсы Levi's 501",    5990, 2500),
        ("Кроссовки Nike Air",   8990, 4200),
        ("Куртка Columbia",     12990, 6500),
        ("Футболка Uniqlo",      1990,  800),
    ],
    6: [  # Женская одежда
        ("Платье Zara",          4990, 2000),
        ("Блузка H&M",           2490, 1000),
        ("Сапоги Ecco",         11990, 5800),
        ("Пальто Massimo Dutti", 14990, 7500),
    ],
    8: [  # Кухонная техника
        ("Кофемашина DeLonghi",  29990, 17000),
        ("Блендер Vitamix",      14990,  8500),
        ("Микроволновка LG",      8990,  4500),
        ("Тостер Bosch",          3990,  1800),
    ],
    9: [  # Мебель
        ("Диван IKEA SÖDERHAMN", 49990, 28000),
        ("Стол IKEA BEKANT",     14990,  8000),
        ("Кресло Herman Miller", 89990, 55000),
        ("Шкаф-купе custom",     34990, 18000),
    ],
    10: [  # Спорт и туризм
        ("Велосипед Trek Marlin",  59990, 35000),
        ("Беговые кроссовки Asics", 8990,  4000),
        ("Палатка Quechua",        12990,  7000),
        ("Гантели набор 20кг",      5990,  2800),
    ],
}

RETURN_REASONS = [
    "Товар не подошёл по размеру",
    "Дефект/повреждение при доставке",
    "Не соответствует описанию",
    "Передумал(а) покупать",
    "Пришёл не тот товар",
]

CITIES = ["Москва", "Санкт-Петербург", "Новосибирск", "Екатеринбург",
          "Казань", "Нижний Новгород", "Самара", "Омск", "Челябинск", "Ростов-на-Дону"]


# ===================================================================
# Reference data generators
# ===================================================================

def generate_categories() -> list[dict]:
    """Return fixed category tree (leaf categories have parent_id set)."""
    return [dict(row) for row in CATEGORY_TREE]


def generate_traffic_sources() -> list[dict]:
    """Return fixed list of marketing traffic sources."""
    return [dict(row) for row in TRAFFIC_SOURCE_DEFS]


def generate_ad_campaigns(source_ids: list[int]) -> list[dict]:
    """Generate 1-3 campaigns per paid source (google_ads, yandex_direct)."""
    paid_sources = source_ids  # caller filters paid ones externally
    campaigns = []
    base = date(2024, 1, 1)
    for source_id in paid_sources:
        for i in range(random.randint(1, 3)):
            start = base + timedelta(days=random.randint(0, 180))
            end = start + timedelta(days=random.randint(14, 90))
            budget = round(random.uniform(50_000, 500_000), 2)
            campaigns.append({
                "source_id": source_id,
                "name": f"Кампания {_fake.word().capitalize()} {start.strftime('%b %Y')}",
                "budget": budget,
                "actual_spend": round(budget * random.uniform(0.4, 1.0), 2),
                "start_date": start,
                "end_date": end,
            })
    return campaigns


def generate_ad_daily_stats(campaign_ids: list[int], stat_date: date) -> list[dict]:
    """Generate one daily stats record per campaign for a given date."""
    stats = []
    for cid in campaign_ids:
        impressions = random.randint(500, 20_000)
        clicks = int(impressions * random.uniform(0.01, 0.08))  # 1-8% CTR
        conversions = int(clicks * random.uniform(0.02, 0.12))   # 2-12% CVR
        spend = round(clicks * random.uniform(5, 50), 2)          # CPC 5-50 rub
        stats.append({
            "campaign_id": cid,
            "stat_date": stat_date,
            "impressions": impressions,
            "clicks": clicks,
            "spend": spend,
            "conversions": conversions,
        })
    return stats


# ===================================================================
# Products & WMS products
# ===================================================================

def generate_products(category_ids: list[int], n: int) -> list[dict]:
    """Generate n products spread across the given category IDs."""
    products = []
    leaf_categories = [cid for cid in category_ids if cid in PRODUCT_TEMPLATES]
    if not leaf_categories:
        leaf_categories = category_ids

    for _ in range(n):
        cat_id = random.choice(leaf_categories)
        templates = PRODUCT_TEMPLATES.get(cat_id, [])
        if templates:
            name, price, cost = random.choice(templates)
            # add slight price variation (+/-15%)
            price = round(price * random.uniform(0.85, 1.15), -1)
            cost = round(cost * random.uniform(0.90, 1.10), -1)
        else:
            name = _fake.word().capitalize() + " " + _fake.word()
            price = round(random.uniform(500, 50_000), 2)
            cost = round(price * random.uniform(0.40, 0.70), 2)

        products.append({
            "category_id": cat_id,
            "name": name,
            "price": float(price),
            "cost_price": float(cost),
            "is_active": random.random() > 0.05,  # 95% active
        })
    return products


def generate_wms_products(web_product_ids: list[int]) -> list[dict]:
    """Create one WMS product row per web product ID."""
    seen_skus = set()
    result = []
    for pid in web_product_ids:
        while True:
            sku = f"SKU-{random.randint(10000, 99999)}"
            if sku not in seen_skus:
                seen_skus.add(sku)
                break
        result.append({
            "web_product_id": pid,
            "sku": sku,
            "unit_cost": round(random.uniform(200, 40_000), 2),
        })
    return result


def generate_inventory_record(wms_product_id: int) -> dict:
    on_hand = random.randint(0, 500)
    reserved = random.randint(0, on_hand)
    return {
        "wms_product_id": wms_product_id,
        "quantity_on_hand": on_hand,
        "quantity_reserved": reserved,
        "reorder_point": random.choice([5, 10, 15, 20, 25]),
    }


def generate_inventory_movement(wms_product_id: int) -> dict:
    return {
        "wms_product_id": wms_product_id,
        "movement_type": random.choice(["inbound", "outbound", "adjustment", "return"]),
        "quantity": random.randint(1, 50),
    }


def generate_picking_task(oms_order_id: int, wms_product_id: int) -> dict:
    # 96% accuracy, 5% substitution
    is_accurate = random.random() < 0.96
    is_substituted = (not is_accurate) and (random.random() < 0.50)
    return {
        "oms_order_id": oms_order_id,
        "wms_product_id": wms_product_id,
        "quantity": random.randint(1, 5),
        "is_accurate": is_accurate,
        "is_substituted": is_substituted,
        "completed_at": _random_ts(hours_back=2),
    }


# ===================================================================
# Users & Sessions (web schema)
# ===================================================================

def generate_users(n: int) -> list[dict]:
    seen_emails: set[str] = set()
    users = []
    for _ in range(n):
        while True:
            email = _fake.email()
            if email not in seen_emails:
                seen_emails.add(email)
                break
        users.append({
            "email": email,
            "first_name": _fake.first_name(),
            "last_name": _fake.last_name(),
            "city": random.choice(CITIES),
            "country": "Россия",
            "registered_at": _random_ts(days_back=365),
        })
    return users


def generate_sessions(user_ids: list[int], source_ids: list[int], n: int) -> list[dict]:
    sessions = []
    utm_sources = ["google", "yandex", "vk", "email", "direct", None]
    for _ in range(n):
        started = _random_ts(hours_back=24)
        duration = random.randint(30, 1800)  # 30s – 30min
        sessions.append({
            "user_id": random.choice(user_ids + [None]),
            "utm_source": random.choice(utm_sources),
            "utm_campaign": f"camp_{random.randint(1,10)}" if random.random() > 0.5 else None,
            "device_type": random.choices(["mobile", "desktop", "tablet"], weights=[55, 40, 5])[0],
            "started_at": started,
            "ended_at": started + timedelta(seconds=duration),
            "page_views": random.randint(1, 20),
        })
    return sessions


# ===================================================================
# Cart & Order (web schema)
# ===================================================================

def generate_cart_and_items(
    user_id: int,
    session_id: int,
    product_ids: list[int],
    product_prices: Optional[dict] = None,
) -> tuple[dict, list[dict]]:
    """
    Generate a cart with 1-5 items.
    Status distribution: ~35% abandoned, ~55% converted, ~10% active.
    product_prices: {product_id: (price, cost_price)} – if None, random prices used.
    """
    status = random.choices(
        ["abandoned", "converted", "active"],
        weights=[35, 55, 10],
    )[0]
    created = _random_ts(hours_back=48)
    cart = {
        "user_id": user_id,
        "session_id": session_id,
        "status": status,
        "created_at": created,
        "updated_at": created + timedelta(minutes=random.randint(1, 60)),
    }

    n_items = random.randint(1, 5)
    chosen = random.sample(product_ids, min(n_items, len(product_ids)))
    items = []
    for pid in chosen:
        if product_prices and pid in product_prices:
            price, cost = product_prices[pid]
        else:
            price = round(random.uniform(500, 50_000), 2)
            cost = round(price * random.uniform(0.40, 0.70), 2)
        items.append({
            "product_id": pid,
            "quantity": random.randint(1, 3),
            "price_at_time": float(price),
            "cost_price": float(cost),  # convenience field for order generation
        })
    return cart, items


def generate_order_from_cart(cart: dict, cart_items: list[dict]) -> tuple[dict, list[dict]]:
    """Create an order (+ order_items) from a converted cart."""
    total = sum(i["quantity"] * i["price_at_time"] for i in cart_items)
    order = {
        "user_id": cart["user_id"],
        "cart_id": cart.get("id"),
        "total_amount": round(total, 2),
        "status": random.choices(
            ["paid", "processing", "shipped", "delivered"],
            weights=[10, 20, 30, 40],
        )[0],
        "created_at": cart.get("created_at", _random_ts(hours_back=24)),
    }
    order_items = []
    for ci in cart_items:
        cost = ci.get("cost_price", round(ci["price_at_time"] * 0.55, 2))
        order_items.append({
            "product_id": ci["product_id"],
            "quantity": ci["quantity"],
            "unit_price": ci["price_at_time"],
            "unit_cost": float(cost),
        })
    return order, order_items


# ===================================================================
# OMS
# ===================================================================

def generate_oms_order(web_order_id: int) -> dict:
    received = _random_ts(hours_back=72)
    status = random.choices(
        ["received", "confirmed", "dispatched", "delivered", "cancelled"],
        weights=[5, 10, 20, 60, 5],
    )[0]
    confirmed = received + timedelta(minutes=random.randint(10, 120)) \
        if status not in ("received",) else None
    dispatched = (confirmed + timedelta(hours=random.randint(2, 24))) \
        if confirmed and status in ("dispatched", "delivered") else None
    return {
        "web_order_id": web_order_id,
        "status": status,
        "received_at": received,
        "confirmed_at": confirmed,
        "dispatched_at": dispatched,
    }


def generate_shipment(oms_order_id: int) -> dict:
    # OTIF: 88% on time, 92% complete
    is_on_time = random.random() < 0.88
    is_complete = random.random() < 0.92
    planned = date.today() + timedelta(days=random.randint(1, 5))
    if is_on_time:
        actual = planned
    else:
        actual = planned + timedelta(days=random.randint(1, 5))
    return {
        "oms_order_id": oms_order_id,
        "carrier_id": random.choice(["CDEK", "BoxBerry", "DHL", "RuPost"]),
        "tracking_number": f"TRK{random.randint(1_000_000, 9_999_999)}",
        "planned_delivery": planned,
        "actual_delivery": actual if random.random() > 0.1 else None,  # 10% not yet delivered
        "is_on_time": is_on_time,
        "is_complete": is_complete,
    }


def generate_return(oms_order_id: int) -> dict:
    return {
        "oms_order_id": oms_order_id,
        "reason": random.choice(RETURN_REASONS),
        "status": random.choices(
            ["pending", "approved", "rejected", "completed"],
            weights=[20, 40, 10, 30],
        )[0],
    }


# ===================================================================
# Marketing
# ===================================================================

def generate_visit(user_ids: list[int], source_ids: list[int]) -> dict:
    # 25% of visits have 1 page view (single-page sessions)
    page_views = random.choices(range(1, 16), weights=[25] + [5] * 14)[0]
    duration = random.randint(0, 1800)
    # 80% of single-page visits are bounces (realistic e-commerce: ~20-25% overall bounce rate)
    is_bounce = (page_views == 1) and (random.random() < 0.85)
    return {
        "user_id": random.choice(user_ids + [None, None]),  # ~33% anonymous
        "source_id": random.choice(source_ids),
        "utm_campaign": f"camp_{random.randint(1, 10)}" if random.random() > 0.6 else None,
        "duration_sec": duration,
        "page_views": page_views,
        "is_bounce": is_bounce,
        "visited_at": _random_ts(hours_back=1),
    }


def generate_page_events(visit_id: int, n_events: int = 3) -> list[dict]:
    base_time = _random_ts(hours_back=1)
    event_types = random.choices(
        ["pageview", "product_view", "add_to_cart", "checkout", "purchase"],
        weights=[40, 30, 15, 10, 5],
        k=n_events,
    )
    events = []
    for i, etype in enumerate(event_types):
        events.append({
            "visit_id": visit_id,
            "event_type": etype,
            "page_url": f"/{'products' if 'product' in etype else 'checkout'}/{random.randint(1, 200)}",
            "event_at": base_time + timedelta(seconds=i * random.randint(5, 60)),
        })
    return events


# ===================================================================
# Internal helpers
# ===================================================================

def _random_ts(days_back: int = 0, hours_back: int = 0) -> datetime:
    """Return a random datetime within the given look-back window."""
    max_seconds = days_back * 86_400 + hours_back * 3_600
    if max_seconds <= 0:
        return datetime.now()
    delta = timedelta(seconds=random.randint(0, max_seconds))
    return datetime.now() - delta
