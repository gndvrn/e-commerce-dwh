{{
    config(
        materialized='table',
        schema='datamart',
        engine="MergeTree()",
        order_by='(report_date, product_name)',
        partition_by='toYYYYMM(report_date)'
    )
}}

/*
  mart_inventory: warehouse & fulfillment KPI mart.

  Metrics exposed:
    - quantity_on_hand, quantity_available, inventory_value
    - is_out_of_stock, is_below_reorder
    - days_supply (on-hand / avg_daily_outbound)
    - inventory_turns (outbound_units / avg_on_hand)
    - otif_rate, order_accuracy, substitution_rate
    - return_rate
*/
WITH daily_outbound AS (
    -- Aggregate outbound inventory movements per product per day
    SELECT
        toDate(im.created_at)               AS movement_date,
        wp.web_product_id                   AS product_sk,
        sum(if(im.movement_type = 'outbound', im.quantity, 0)) AS outbound_qty,
        sum(im.quantity)                    AS total_movement_qty
    FROM {{ ref('stg_wms_inventory_movements') }} im
    LEFT JOIN staging.raw_wms_products wp   ON im.wms_product_id = wp.id
    GROUP BY toDate(im.created_at), wp.web_product_id
),

fulfillment_daily AS (
    SELECT
        toDate(f.shipment_date)             AS report_date,
        count(*)                            AS total_shipments,
        round(avg(f.is_otif) * 100, 2)     AS otif_rate,
        round(avg(f.picking_accuracy) * 100, 2) AS order_accuracy,
        round(avg(f.substitution_rate) * 100, 2) AS substitution_rate,
        round(avg(f.has_return) * 100, 2)  AS return_rate,
        round(avg(f.lead_time_hours), 1)   AS avg_lead_time_hours
    FROM {{ ref('fact_fulfillment') }} f
    GROUP BY toDate(f.shipment_date)
)

SELECT
    inv.snapshot_date                       AS report_date,
    p.product_name,
    p.category_name,
    p.parent_category_name,
    inv.quantity_on_hand,
    inv.quantity_available,
    inv.quantity_reserved,
    inv.reorder_point,
    inv.inventory_value,
    inv.is_out_of_stock,
    inv.is_below_reorder,
    coalesce(ob.outbound_qty, 0)            AS daily_outbound_qty,
    -- Days' supply: how many days until stock runs out at current sales pace
    if(coalesce(ob.outbound_qty, 0) > 0,
       round(inv.quantity_available / ob.outbound_qty, 1), 999) AS days_supply,
    coalesce(fl.total_shipments, 0)         AS total_shipments,
    coalesce(fl.otif_rate, 0)               AS otif_rate,
    coalesce(fl.order_accuracy, 0)          AS order_accuracy,
    coalesce(fl.substitution_rate, 0)       AS substitution_rate,
    coalesce(fl.return_rate, 0)             AS return_rate,
    coalesce(fl.avg_lead_time_hours, 0)     AS avg_lead_time_hours
FROM {{ ref('fact_inventory_snapshot') }} inv
LEFT JOIN {{ ref('dim_product') }} p      ON inv.product_sk = p.product_sk
LEFT JOIN daily_outbound ob
       ON inv.snapshot_date = ob.movement_date AND inv.product_sk = ob.product_sk
LEFT JOIN fulfillment_daily fl            ON inv.snapshot_date = fl.report_date
