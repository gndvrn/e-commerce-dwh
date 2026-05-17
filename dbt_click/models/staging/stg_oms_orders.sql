{{ config(materialized='view', schema='staging') }}

SELECT
    id,
    web_order_id,
    status,
    toDateTime(received_at)                          AS received_at,
    toDateTime(coalesce(confirmed_at, received_at))  AS confirmed_at,
    toDateTime(coalesce(dispatched_at, received_at)) AS dispatched_at,
    toDateTime(created_at)                           AS created_at
FROM staging.raw_oms_orders
FINAL
