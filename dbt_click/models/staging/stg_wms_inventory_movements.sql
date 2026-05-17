{{ config(materialized='view', schema='staging') }}

SELECT
    id,
    wms_product_id,
    movement_type,
    quantity,
    toDateTime(created_at) AS created_at
FROM staging.raw_wms_inventory_movements
FINAL
