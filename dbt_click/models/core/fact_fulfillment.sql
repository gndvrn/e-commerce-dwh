{{
    config(
        materialized='table',
        schema='core',
        engine="MergeTree()",
        order_by='(shipment_date, shipment_sk)',
        partition_by='toYYYYMM(shipment_date)'
    )
}}

/*
  fact_fulfillment: grain = one shipment.
  Source for OTIF, Lead Time, Order Accuracy, Substitution Rate, Returns.
*/
SELECT
    sh.id                                                   AS shipment_sk,
    sh.oms_order_id,
    oo.web_order_id,
    toInt32(formatDateTime(sh.created_at, '%Y%m%d'))       AS date_sk,
    toDate(sh.created_at)                                   AS shipment_date,
    sh.planned_delivery,
    sh.actual_delivery,
    sh.is_on_time,
    sh.is_complete,
    toUInt8(sh.is_on_time AND sh.is_complete)              AS is_otif,
    -- Lead time in hours from order received to dispatched
    dateDiff('hour', oo.received_at, oo.dispatched_at)    AS lead_time_hours,
    -- Picking accuracy aggregated per order
    coalesce(pt.pct_accurate, 1.0)                         AS picking_accuracy,
    coalesce(pt.pct_substituted, 0.0)                      AS substitution_rate,
    -- Return flag
    coalesce(r.has_return, 0)                              AS has_return
FROM {{ ref('stg_oms_shipments') }} sh
INNER JOIN {{ ref('stg_oms_orders') }} oo ON sh.oms_order_id = oo.id
LEFT JOIN (
    SELECT
        oms_order_id,
        avg(is_accurate)    AS pct_accurate,
        avg(is_substituted) AS pct_substituted
    FROM {{ ref('stg_wms_picking_tasks') }}
    GROUP BY oms_order_id
) pt ON oo.id = pt.oms_order_id
LEFT JOIN (
    SELECT oms_order_id, 1 AS has_return
    FROM staging.raw_oms_returns FINAL
    GROUP BY oms_order_id
) r ON oo.id = r.oms_order_id
