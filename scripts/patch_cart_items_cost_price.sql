-- One-off patch if the DB was initialized without web.cart_items.cost_price.
-- Example:
--   docker compose exec -T postgres psql -U airflow -d airflow < scripts/patch_cart_items_cost_price.sql

ALTER TABLE web.cart_items
    ADD COLUMN IF NOT EXISTS cost_price NUMERIC(10,2);

UPDATE web.cart_items AS ci
SET cost_price = p.cost_price
FROM web.products AS p
WHERE ci.product_id = p.id
  AND (ci.cost_price IS NULL OR ci.cost_price <= 0);

UPDATE web.cart_items
SET cost_price = price_at_time * 0.5
WHERE cost_price IS NULL OR cost_price <= 0;

ALTER TABLE web.cart_items
    ALTER COLUMN cost_price SET NOT NULL;

ALTER TABLE web.cart_items
    DROP CONSTRAINT IF EXISTS cart_items_cost_price_positive;

ALTER TABLE web.cart_items
    ADD CONSTRAINT cart_items_cost_price_positive CHECK (cost_price > 0);
