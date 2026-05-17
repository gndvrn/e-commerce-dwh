{{
    config(
        materialized='table',
        schema='core',
        engine="MergeTree()",
        order_by='(snapshot_date, wms_product_id)',
        partition_by='toYYYYMM(snapshot_date)'
    )
}}

/*
  fact_inventory_snapshot: grain = daily inventory snapshot per WMS product.
  Source for Inventory Turns, Days' Supply, Out-of-Stock events, GMROI.
*/
SELECT
    toInt32(formatDateTime(inv.updated_at, '%Y%m%d'))  AS date_sk,
    toDate(inv.updated_at)                              AS snapshot_date,
    inv.wms_product_id,
    wp.web_product_id                                   AS product_sk,
    inv.quantity_on_hand,
    inv.quantity_reserved,
    greatest(inv.quantity_on_hand - inv.quantity_reserved, 0) AS quantity_available,
    inv.reorder_point,
    if(inv.quantity_on_hand <= 0, 1, 0)                AS is_out_of_stock,
    if(inv.quantity_on_hand <= inv.reorder_point, 1, 0) AS is_below_reorder,
    wp.unit_cost,
    toFloat64(inv.quantity_on_hand * wp.unit_cost)     AS inventory_value
FROM {{ ref('stg_wms_inventory') }} inv
LEFT JOIN staging.raw_wms_products wp ON inv.wms_product_id = wp.id
