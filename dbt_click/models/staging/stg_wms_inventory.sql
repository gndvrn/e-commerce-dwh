{{ config(materialized='view', schema='staging') }}

SELECT
    id,
    wms_product_id,
    quantity_on_hand,
    quantity_reserved,
    reorder_point,
    toDateTime(updated_at) AS updated_at
FROM staging.raw_wms_inventory
FINAL
