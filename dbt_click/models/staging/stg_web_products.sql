{{ config(materialized='view', schema='staging') }}

SELECT
    id,
    category_id,
    name            AS product_name,
    price,
    cost_price,
    is_active,
    toDateTime(created_at) AS created_at
FROM staging.raw_web_products
FINAL
