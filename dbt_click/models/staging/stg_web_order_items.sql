{{ config(materialized='view', schema='staging') }}

SELECT
    id,
    order_id,
    product_id,
    quantity,
    unit_price,
    unit_cost,
    toDateTime(created_at) AS created_at
FROM staging.raw_web_order_items
FINAL
