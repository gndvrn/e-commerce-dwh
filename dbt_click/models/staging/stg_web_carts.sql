{{ config(materialized='view', schema='staging') }}

SELECT
    id,
    coalesce(user_id, 0) AS user_id,
    session_id,
    status,
    toDateTime(created_at) AS created_at,
    toDateTime(updated_at) AS updated_at
FROM staging.raw_web_carts
FINAL
