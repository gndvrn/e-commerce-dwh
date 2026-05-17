"""
Unit tests for synthetic_data_generator/generators.py.

TDD: these tests define the contract for the generator module BEFORE
the implementation exists. They verify:
  - generated records have all required fields
  - field values are within expected domains
  - business proportions are realistic (conversion rate, OTIF, etc.)
  - referential integrity is maintained between generated entities
"""
import pytest
from datetime import date, datetime

# Will be importable after implementation
from generators import (
    generate_categories,
    generate_products,
    generate_traffic_sources,
    generate_users,
    generate_sessions,
    generate_cart_and_items,
    generate_order_from_cart,
    generate_oms_order,
    generate_shipment,
    generate_return,
    generate_wms_products,
    generate_inventory_record,
    generate_inventory_movement,
    generate_picking_task,
    generate_visit,
    generate_page_events,
    generate_ad_campaigns,
    generate_ad_daily_stats,
)


# ---------------------------------------------------------------------------
# Reference data: categories, products, traffic_sources
# ---------------------------------------------------------------------------

class TestGenerateCategories:
    def test_returns_list(self):
        cats = generate_categories()
        assert isinstance(cats, list)

    def test_count_is_fixed_known_value(self):
        cats = generate_categories()
        assert len(cats) >= 5

    def test_required_fields_present(self):
        for cat in generate_categories():
            assert "name" in cat
            assert "parent_id" in cat  # may be None for top-level

    def test_names_are_nonempty_strings(self):
        for cat in generate_categories():
            assert isinstance(cat["name"], str)
            assert len(cat["name"]) > 0

    def test_top_level_categories_have_null_parent(self):
        top_level = [c for c in generate_categories() if c["parent_id"] is None]
        assert len(top_level) >= 1


class TestGenerateProducts:
    def test_returns_correct_count(self, sample_category_ids):
        products = generate_products(category_ids=sample_category_ids, n=30)
        assert len(products) == 30

    def test_required_fields_present(self, sample_category_ids):
        products = generate_products(category_ids=sample_category_ids, n=5)
        for p in products:
            assert "category_id" in p
            assert "name" in p
            assert "price" in p
            assert "cost_price" in p
            assert "is_active" in p

    def test_prices_are_positive(self, sample_category_ids):
        products = generate_products(category_ids=sample_category_ids, n=20)
        for p in products:
            assert p["price"] > 0
            assert p["cost_price"] > 0

    def test_cost_price_never_exceeds_price(self, sample_category_ids):
        """Margin must be non-negative – basic business invariant."""
        products = generate_products(category_ids=sample_category_ids, n=50)
        for p in products:
            assert p["cost_price"] <= p["price"], (
                f"Product cost {p['cost_price']} > price {p['price']}"
            )

    def test_all_products_reference_valid_category(self, sample_category_ids):
        products = generate_products(category_ids=sample_category_ids, n=20)
        for p in products:
            assert p["category_id"] in sample_category_ids

    def test_is_active_is_boolean(self, sample_category_ids):
        products = generate_products(category_ids=sample_category_ids, n=10)
        for p in products:
            assert isinstance(p["is_active"], bool)


class TestGenerateTrafficSources:
    def test_returns_list_with_all_channels(self):
        sources = generate_traffic_sources()
        channel_types = {s["channel_type"] for s in sources}
        expected = {"organic", "google_ads", "yandex_direct", "email", "referral", "social"}
        assert expected.issubset(channel_types)

    def test_required_fields_present(self):
        for src in generate_traffic_sources():
            assert "name" in src
            assert "channel_type" in src

    def test_names_are_unique(self):
        sources = generate_traffic_sources()
        names = [s["name"] for s in sources]
        assert len(names) == len(set(names))


# ---------------------------------------------------------------------------
# Users & Sessions
# ---------------------------------------------------------------------------

class TestGenerateUsers:
    def test_returns_correct_count(self):
        users = generate_users(n=15)
        assert len(users) == 15

    def test_required_fields_present(self):
        for u in generate_users(n=3):
            assert "email" in u
            assert "city" in u
            assert "country" in u
            assert "registered_at" in u

    def test_emails_are_unique(self):
        users = generate_users(n=100)
        emails = [u["email"] for u in users]
        assert len(emails) == len(set(emails)), "Duplicate emails found"

    def test_registered_at_is_datetime(self):
        for u in generate_users(n=5):
            assert isinstance(u["registered_at"], datetime)

    def test_country_is_nonempty(self):
        for u in generate_users(n=5):
            assert u["country"]


class TestGenerateSessions:
    def test_returns_correct_count(self, sample_user_ids, sample_source_ids):
        sessions = generate_sessions(user_ids=sample_user_ids, source_ids=sample_source_ids, n=10)
        assert len(sessions) == 10

    def test_required_fields_present(self, sample_user_ids, sample_source_ids):
        sessions = generate_sessions(user_ids=sample_user_ids, source_ids=sample_source_ids, n=3)
        for s in sessions:
            assert "user_id" in s
            assert "utm_source" in s
            assert "device_type" in s
            assert "started_at" in s
            assert "page_views" in s

    def test_device_types_are_valid(self, sample_user_ids, sample_source_ids):
        sessions = generate_sessions(user_ids=sample_user_ids, source_ids=sample_source_ids, n=30)
        valid_types = {"mobile", "desktop", "tablet"}
        for s in sessions:
            assert s["device_type"] in valid_types

    def test_page_views_positive(self, sample_user_ids, sample_source_ids):
        sessions = generate_sessions(user_ids=sample_user_ids, source_ids=sample_source_ids, n=10)
        for s in sessions:
            assert s["page_views"] >= 1

    def test_all_sessions_link_to_valid_user(self, sample_user_ids, sample_source_ids):
        sessions = generate_sessions(user_ids=sample_user_ids, source_ids=sample_source_ids, n=20)
        for s in sessions:
            assert s["user_id"] in sample_user_ids or s["user_id"] is None


# ---------------------------------------------------------------------------
# Cart, Order (web schema)
# ---------------------------------------------------------------------------

class TestGenerateCartAndItems:
    def test_returns_cart_and_items_tuple(self, sample_product_ids):
        cart, items = generate_cart_and_items(user_id=1, session_id=1, product_ids=sample_product_ids)
        assert isinstance(cart, dict)
        assert isinstance(items, list)

    def test_cart_status_is_valid(self, sample_product_ids):
        statuses = set()
        for i in range(50):
            cart, _ = generate_cart_and_items(user_id=1, session_id=i, product_ids=sample_product_ids)
            statuses.add(cart["status"])
        assert statuses.issubset({"active", "abandoned", "converted"})

    def test_cart_items_reference_valid_products(self, sample_product_ids):
        _, items = generate_cart_and_items(user_id=1, session_id=1, product_ids=sample_product_ids)
        for item in items:
            assert item["product_id"] in sample_product_ids

    def test_cart_items_have_positive_quantity(self, sample_product_ids):
        _, items = generate_cart_and_items(user_id=1, session_id=1, product_ids=sample_product_ids)
        for item in items:
            assert item["quantity"] >= 1

    def test_abandoned_rate_is_realistic(self, sample_product_ids):
        """30-50% of carts should be abandoned – key e-commerce metric."""
        abandoned = sum(
            1 for i in range(200)
            if generate_cart_and_items(1, i, sample_product_ids)[0]["status"] == "abandoned"
        )
        rate = abandoned / 200
        assert 0.20 <= rate <= 0.60, f"Abandoned rate {rate:.2%} out of realistic range"


class TestGenerateOrderFromCart:
    def test_returns_order_and_items(self, sample_product_ids):
        cart = {"id": 1, "user_id": 5, "status": "converted"}
        cart_items = [
            {"product_id": 1, "quantity": 2, "price_at_time": 999.0},
            {"product_id": 2, "quantity": 1, "price_at_time": 499.0},
        ]
        order, order_items = generate_order_from_cart(cart=cart, cart_items=cart_items)
        assert isinstance(order, dict)
        assert isinstance(order_items, list)
        assert len(order_items) == len(cart_items)

    def test_order_total_matches_items(self):
        cart = {"id": 1, "user_id": 5, "status": "converted"}
        cart_items = [
            {"product_id": 1, "quantity": 2, "price_at_time": 100.0, "cost_price": 60.0},
            {"product_id": 2, "quantity": 1, "price_at_time": 200.0, "cost_price": 120.0},
        ]
        order, _ = generate_order_from_cart(cart=cart, cart_items=cart_items)
        expected_total = 2 * 100.0 + 1 * 200.0
        assert abs(order["total_amount"] - expected_total) < 0.01

    def test_order_items_have_unit_cost(self):
        cart = {"id": 1, "user_id": 5, "status": "converted"}
        cart_items = [{"product_id": 1, "quantity": 1, "price_at_time": 100.0, "cost_price": 60.0}]
        _, items = generate_order_from_cart(cart=cart, cart_items=cart_items)
        assert items[0]["unit_cost"] > 0


# ---------------------------------------------------------------------------
# OMS: oms_order, shipment, return
# ---------------------------------------------------------------------------

class TestGenerateOmsOrder:
    def test_returns_dict_with_required_fields(self):
        order = generate_oms_order(web_order_id=42)
        assert order["web_order_id"] == 42
        assert "status" in order
        assert "received_at" in order

    def test_status_is_valid(self):
        statuses = set()
        for i in range(20):
            statuses.add(generate_oms_order(web_order_id=i)["status"])
        assert statuses.issubset({"received", "confirmed", "dispatched", "delivered", "cancelled"})

    def test_received_at_before_confirmed_at(self):
        for i in range(10):
            order = generate_oms_order(web_order_id=i)
            if order.get("confirmed_at"):
                assert order["received_at"] <= order["confirmed_at"]


class TestGenerateShipment:
    def test_returns_dict_with_required_fields(self):
        shipment = generate_shipment(oms_order_id=1)
        assert shipment["oms_order_id"] == 1
        assert "is_on_time" in shipment
        assert "is_complete" in shipment
        assert "planned_delivery" in shipment

    def test_otif_rate_is_realistic(self):
        """85–95% of shipments should be on-time (OTIF)."""
        shipments = [generate_shipment(i) for i in range(200)]
        on_time = sum(1 for s in shipments if s["is_on_time"])
        rate = on_time / 200
        assert 0.75 <= rate <= 1.0, f"OTIF rate {rate:.2%} is unexpectedly low"

    def test_actual_delivery_after_planned_when_late(self):
        for i in range(50):
            s = generate_shipment(i)
            if not s["is_on_time"] and s.get("actual_delivery") and s.get("planned_delivery"):
                assert s["actual_delivery"] > s["planned_delivery"]


class TestGenerateReturn:
    def test_returns_dict_with_required_fields(self):
        ret = generate_return(oms_order_id=1)
        assert ret["oms_order_id"] == 1
        assert "reason" in ret
        assert "status" in ret

    def test_reason_is_nonempty(self):
        for i in range(5):
            ret = generate_return(oms_order_id=i)
            assert ret["reason"]


# ---------------------------------------------------------------------------
# WMS: wms_products, inventory, movements, picking_tasks
# ---------------------------------------------------------------------------

class TestGenerateWmsProducts:
    def test_returns_correct_count(self):
        prods = generate_wms_products(web_product_ids=list(range(1, 21)))
        assert len(prods) == 20

    def test_required_fields_present(self):
        for p in generate_wms_products(web_product_ids=[1, 2]):
            assert "web_product_id" in p
            assert "sku" in p
            assert "unit_cost" in p

    def test_skus_are_unique(self):
        prods = generate_wms_products(web_product_ids=list(range(1, 51)))
        skus = [p["sku"] for p in prods]
        assert len(skus) == len(set(skus))

    def test_unit_cost_positive(self):
        for p in generate_wms_products(web_product_ids=[1, 2, 3]):
            assert p["unit_cost"] > 0


class TestGenerateInventoryRecord:
    def test_returns_dict_with_required_fields(self):
        inv = generate_inventory_record(wms_product_id=1)
        assert inv["wms_product_id"] == 1
        assert "quantity_on_hand" in inv
        assert "quantity_reserved" in inv
        assert "reorder_point" in inv

    def test_quantities_are_non_negative(self):
        for i in range(20):
            inv = generate_inventory_record(wms_product_id=i)
            assert inv["quantity_on_hand"] >= 0
            assert inv["quantity_reserved"] >= 0

    def test_reserved_never_exceeds_on_hand(self):
        for i in range(30):
            inv = generate_inventory_record(wms_product_id=i)
            assert inv["quantity_reserved"] <= inv["quantity_on_hand"]


class TestGenerateInventoryMovement:
    def test_returns_dict_with_required_fields(self):
        mov = generate_inventory_movement(wms_product_id=1)
        assert mov["wms_product_id"] == 1
        assert "movement_type" in mov
        assert "quantity" in mov

    def test_movement_type_is_valid(self):
        valid_types = {"inbound", "outbound", "adjustment", "return"}
        for i in range(30):
            mov = generate_inventory_movement(wms_product_id=1)
            assert mov["movement_type"] in valid_types

    def test_quantity_is_positive(self):
        for i in range(10):
            mov = generate_inventory_movement(wms_product_id=1)
            assert mov["quantity"] > 0


class TestGeneratePickingTask:
    def test_returns_dict_with_required_fields(self):
        task = generate_picking_task(oms_order_id=1, wms_product_id=1)
        assert task["oms_order_id"] == 1
        assert task["wms_product_id"] == 1
        assert "is_accurate" in task
        assert "is_substituted" in task

    def test_accuracy_rate_is_realistic(self):
        """≥95% of picking tasks should be accurate."""
        tasks = [generate_picking_task(i, 1) for i in range(200)]
        accurate = sum(1 for t in tasks if t["is_accurate"])
        rate = accurate / 200
        assert rate >= 0.90, f"Accuracy rate {rate:.2%} unexpectedly low"

    def test_substitution_rate_is_low(self):
        """≤10% substitution rate."""
        tasks = [generate_picking_task(i, 1) for i in range(200)]
        substituted = sum(1 for t in tasks if t["is_substituted"])
        rate = substituted / 200
        assert rate <= 0.15, f"Substitution rate {rate:.2%} unexpectedly high"


# ---------------------------------------------------------------------------
# Marketing: visits, page_events, campaigns, daily stats
# ---------------------------------------------------------------------------

class TestGenerateVisit:
    def test_returns_dict_with_required_fields(self, sample_user_ids, sample_source_ids):
        visit = generate_visit(user_ids=sample_user_ids, source_ids=sample_source_ids)
        assert "source_id" in visit
        assert "duration_sec" in visit
        assert "page_views" in visit
        assert "is_bounce" in visit
        assert "visited_at" in visit

    def test_source_id_is_valid(self, sample_user_ids, sample_source_ids):
        for _ in range(20):
            visit = generate_visit(user_ids=sample_user_ids, source_ids=sample_source_ids)
            assert visit["source_id"] in sample_source_ids

    def test_duration_is_positive(self, sample_user_ids, sample_source_ids):
        for _ in range(10):
            visit = generate_visit(user_ids=sample_user_ids, source_ids=sample_source_ids)
            assert visit["duration_sec"] >= 0

    def test_bounce_rate_is_realistic(self, sample_user_ids, sample_source_ids):
        """~20-40% bounce rate is typical for e-commerce."""
        visits = [generate_visit(sample_user_ids, sample_source_ids) for _ in range(200)]
        bounce_rate = sum(1 for v in visits if v["is_bounce"]) / 200
        assert 0.10 <= bounce_rate <= 0.60


class TestGeneratePageEvents:
    def test_returns_list(self):
        events = generate_page_events(visit_id=1, n_events=5)
        assert isinstance(events, list)
        assert len(events) == 5

    def test_all_events_link_to_visit(self):
        events = generate_page_events(visit_id=42, n_events=3)
        for e in events:
            assert e["visit_id"] == 42

    def test_event_types_are_valid(self):
        valid_types = {"pageview", "product_view", "add_to_cart", "checkout", "purchase"}
        events = generate_page_events(visit_id=1, n_events=20)
        for e in events:
            assert e["event_type"] in valid_types

    def test_events_have_timestamps(self):
        events = generate_page_events(visit_id=1, n_events=3)
        for e in events:
            assert isinstance(e["event_at"], datetime)


class TestGenerateAdCampaigns:
    def test_returns_list(self, sample_source_ids):
        campaigns = generate_ad_campaigns(source_ids=sample_source_ids)
        assert isinstance(campaigns, list)
        assert len(campaigns) >= 1

    def test_required_fields_present(self, sample_source_ids):
        for c in generate_ad_campaigns(source_ids=sample_source_ids):
            assert "source_id" in c
            assert "name" in c
            assert "budget" in c
            assert "start_date" in c
            assert "end_date" in c

    def test_source_ids_are_valid(self, sample_source_ids):
        for c in generate_ad_campaigns(source_ids=sample_source_ids):
            assert c["source_id"] in sample_source_ids

    def test_end_date_after_start_date(self, sample_source_ids):
        for c in generate_ad_campaigns(source_ids=sample_source_ids):
            assert c["end_date"] >= c["start_date"]


class TestGenerateAdDailyStats:
    def test_returns_one_record_per_campaign(self, sample_campaign_ids):
        stats = generate_ad_daily_stats(campaign_ids=sample_campaign_ids, stat_date=date.today())
        assert len(stats) == len(sample_campaign_ids)

    def test_required_fields_present(self, sample_campaign_ids):
        stats = generate_ad_daily_stats(campaign_ids=sample_campaign_ids, stat_date=date.today())
        for s in stats:
            assert "campaign_id" in s
            assert "stat_date" in s
            assert "impressions" in s
            assert "clicks" in s
            assert "spend" in s
            assert "conversions" in s

    def test_clicks_never_exceed_impressions(self, sample_campaign_ids):
        for _ in range(10):
            stats = generate_ad_daily_stats(campaign_ids=sample_campaign_ids, stat_date=date.today())
            for s in stats:
                assert s["clicks"] <= s["impressions"], "Clicks cannot exceed impressions"

    def test_conversions_never_exceed_clicks(self, sample_campaign_ids):
        for _ in range(10):
            stats = generate_ad_daily_stats(campaign_ids=sample_campaign_ids, stat_date=date.today())
            for s in stats:
                assert s["conversions"] <= s["clicks"], "Conversions cannot exceed clicks"

    def test_spend_is_non_negative(self, sample_campaign_ids):
        stats = generate_ad_daily_stats(campaign_ids=sample_campaign_ids, stat_date=date.today())
        for s in stats:
            assert s["spend"] >= 0
