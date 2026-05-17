{{
    config(
        materialized='table',
        schema='datamart',
        engine="MergeTree()",
        order_by='(report_date, category_name, product_name)',
        partition_by='toYYYYMM(report_date)'
    )
}}

/*
  mart_sales: sales KPI mart.

  Metrics exposed:
    - total_revenue, total_cogs, gross_profit, gross_margin_pct
    - total_orders, total_units
    - aov (average order value)
    - conversion_rate (sessions that converted)
    - cart_abandon_rate
    - daily_unique_customers
*/
WITH daily_orders AS (
    SELECT
        d.date_day                          AS report_date,
        d.year,
        d.month,
        d.month_name,
        d.quarter_label,
        d.is_weekend,
        p.category_name,
        p.parent_category_name,
        p.product_name,
        -- Revenue metrics
        sum(f.revenue)                      AS total_revenue,
        sum(f.cogs)                         AS total_cogs,
        sum(f.gross_profit)                 AS gross_profit,
        if(sum(f.revenue) > 0,
           round(sum(f.gross_profit) / sum(f.revenue) * 100, 2), 0)  AS gross_margin_pct,
        -- Order metrics
        count(DISTINCT f.order_id)          AS total_orders,
        sum(f.quantity)                     AS total_units,
        if(count(DISTINCT f.order_id) > 0,
           round(sum(f.revenue) / count(DISTINCT f.order_id), 2), 0) AS aov,
        count(DISTINCT f.customer_sk)       AS daily_unique_customers
    FROM {{ ref('fact_order_items') }} f
    INNER JOIN {{ ref('dim_date') }} d    ON f.date_sk = d.date_sk
    INNER JOIN {{ ref('dim_product') }} p ON f.product_sk = p.product_sk
    GROUP BY
        d.date_day, d.year, d.month, d.month_name, d.quarter_label, d.is_weekend,
        p.category_name, p.parent_category_name, p.product_name
),

daily_sessions AS (
    SELECT
        toDate(s.session_date)              AS report_date,
        count(*)                            AS total_sessions,
        sum(s.converted)                    AS converted_sessions,
        sum(s.cart_abandoned)               AS abandoned_sessions,
        if(count(*) > 0,
           round(sum(s.converted) / count(*) * 100, 2), 0)       AS conversion_rate,
        if(count(*) > 0,
           round(sum(s.cart_abandoned) / count(*) * 100, 2), 0)  AS cart_abandon_rate
    FROM {{ ref('fact_sessions') }} s
    GROUP BY toDate(s.session_date)
)

SELECT
    o.report_date,
    o.year,
    o.month,
    o.month_name,
    o.quarter_label,
    o.is_weekend,
    o.category_name,
    o.parent_category_name,
    o.product_name,
    o.total_revenue,
    o.total_cogs,
    o.gross_profit,
    o.gross_margin_pct,
    o.total_orders,
    o.total_units,
    o.aov,
    o.daily_unique_customers,
    coalesce(s.total_sessions, 0)       AS total_sessions,
    coalesce(s.conversion_rate, 0)      AS conversion_rate,
    coalesce(s.cart_abandon_rate, 0)    AS cart_abandon_rate
FROM daily_orders o
LEFT JOIN daily_sessions s ON o.report_date = s.report_date
