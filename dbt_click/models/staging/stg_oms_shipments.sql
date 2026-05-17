{{ config(materialized='view', schema='staging') }}

SELECT
    id,
    oms_order_id,
    coalesce(carrier_id, 'Unknown')  AS carrier_id,
    coalesce(planned_delivery, toDate(created_at))  AS planned_delivery,
    coalesce(actual_delivery, toDate(created_at))   AS actual_delivery,
    coalesce(is_on_time, 0)    AS is_on_time,
    is_complete,
    toDateTime(created_at)     AS created_at
FROM staging.raw_oms_shipments
FINAL
