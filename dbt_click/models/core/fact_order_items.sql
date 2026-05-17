{{
    config(
        materialized='table',
        schema='core',
        engine="MergeTree()",
        order_by='(order_date, customer_sk, product_sk)',
        partition_by='toYYYYMM(order_date)'
    )
}}

/*
  fact_order_items: grain = one order line item.
  Central sales fact; source for Revenue, COGS, AOV, Conversion Rate.
*/
SELECT
    oi.id                                           AS order_item_sk,
    o.id                                            AS order_id,
    toInt32(formatDateTime(o.created_at, '%Y%m%d')) AS date_sk,
    toDate(o.created_at)                            AS order_date,
    o.user_id                                       AS customer_sk,
    oi.product_id                                   AS product_sk,
    oi.quantity,
    oi.unit_price,
    oi.unit_cost,
    toFloat64(oi.quantity * oi.unit_price)          AS revenue,
    toFloat64(oi.quantity * oi.unit_cost)           AS cogs,
    toFloat64(oi.quantity * oi.unit_price - oi.quantity * oi.unit_cost) AS gross_profit,
    o.status                                        AS order_status,
    -- Flag the first order per customer for CAC/CLTV calculation
    if(o.id = min(o.id) OVER (PARTITION BY o.user_id ORDER BY o.created_at), 1, 0) AS is_first_order
FROM {{ ref('stg_web_order_items') }} oi
INNER JOIN {{ ref('stg_web_orders') }} o ON oi.order_id = o.id
WHERE o.status NOT IN ('cancelled', 'refunded')
