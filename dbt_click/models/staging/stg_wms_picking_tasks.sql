{{ config(materialized='view', schema='staging') }}

SELECT
    id,
    oms_order_id,
    wms_product_id,
    quantity,
    is_accurate,
    is_substituted,
    toDateTime(coalesce(completed_at, created_at)) AS completed_at
FROM staging.raw_wms_picking_tasks
FINAL
