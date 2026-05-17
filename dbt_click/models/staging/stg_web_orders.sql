{{ config(materialized='view', schema='staging') }}

SELECT
    id,
    user_id,
    coalesce(cart_id, 0) AS cart_id,
    total_amount,
    status,
    toDateTime(created_at) AS created_at
FROM staging.raw_web_orders
FINAL
