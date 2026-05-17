{{
    config(
        materialized='table',
        schema='datamart',
        engine="MergeTree()",
        order_by='(report_date, channel_name)',
        partition_by='toYYYYMM(report_date)'
    )
}}

/*
  mart_marketing: marketing performance KPI mart.

  Metrics exposed:
    - site_traffic (unique visits), bounce_rate, avg_session_duration
    - impressions, clicks, ctr, cpc, total_spend
    - conversions, cost_per_conversion
    - romi: (attributed_revenue - spend) / spend * 100
    - cac: spend / new_customers (customers with first_order in period)
*/
WITH daily_visits AS (
    SELECT
        toDate(s.session_date)              AS report_date,
        ch.channel_name,
        ch.channel_type,
        count(*)                            AS site_traffic,
        countDistinct(s.customer_sk)        AS unique_visitors,
        round(avg(s.duration_sec), 0)       AS avg_session_duration_sec,
        round(avg(s.is_bounce) * 100, 2)    AS bounce_rate,
        sum(s.converted)                    AS converted_visits
    FROM {{ ref('fact_sessions') }} s
    LEFT JOIN {{ ref('dim_channel') }} ch ON s.channel_sk = ch.channel_sk
    GROUP BY toDate(s.session_date), ch.channel_name, ch.channel_type
),

daily_ad_stats AS (
    SELECT
        a.stat_date                         AS report_date,
        ch.channel_name,
        sum(a.impressions)                  AS impressions,
        sum(a.clicks)                       AS clicks,
        round(sum(a.spend), 2)              AS total_spend,
        sum(a.conversions)                  AS ad_conversions,
        if(sum(a.impressions) > 0,
           round(sum(a.clicks) / sum(a.impressions) * 100, 2), 0) AS ctr,
        if(sum(a.clicks) > 0,
           round(sum(a.spend) / sum(a.clicks), 2), 0)             AS cpc,
        if(sum(a.conversions) > 0,
           round(sum(a.spend) / sum(a.conversions), 2), 0)        AS cost_per_conversion
    FROM {{ ref('fact_ad_stats') }} a
    LEFT JOIN {{ ref('dim_channel') }} ch ON a.channel_sk = ch.channel_sk
    GROUP BY a.stat_date, ch.channel_name
),

daily_revenue AS (
    SELECT
        toDate(f.order_date)                AS report_date,
        ch.channel_name,
        sum(f.revenue)                      AS attributed_revenue,
        countIf(f.is_first_order = 1)       AS new_customers
    FROM {{ ref('fact_order_items') }} f
    LEFT JOIN {{ ref('fact_sessions') }} s  ON f.customer_sk = s.customer_sk
         AND toDate(f.order_date) = toDate(s.session_date)
    LEFT JOIN {{ ref('dim_channel') }} ch   ON s.channel_sk = ch.channel_sk
    GROUP BY toDate(f.order_date), ch.channel_name
)

SELECT
    report_date,
    channel_name,
    channel_type,
    site_traffic,
    unique_visitors,
    avg_session_duration_sec,
    bounce_rate,
    converted_visits,
    impressions,
    clicks,
    total_spend,
    ctr,
    cpc,
    cost_per_conversion,
    attributed_revenue,
    new_customers,
    romi,
    cac
FROM (
    SELECT
        v.report_date AS report_date,
        v.channel_name AS channel_name,
        v.channel_type AS channel_type,
        v.site_traffic AS site_traffic,
        v.unique_visitors AS unique_visitors,
        v.avg_session_duration_sec AS avg_session_duration_sec,
        v.bounce_rate AS bounce_rate,
        v.converted_visits AS converted_visits,
        coalesce(a.impressions, 0) AS impressions,
        coalesce(a.clicks, 0) AS clicks,
        coalesce(a.total_spend, 0) AS total_spend,
        coalesce(a.ctr, 0) AS ctr,
        coalesce(a.cpc, 0) AS cpc,
        coalesce(a.cost_per_conversion, 0) AS cost_per_conversion,
        coalesce(r.attributed_revenue, 0) AS attributed_revenue,
        coalesce(r.new_customers, 0) AS new_customers,
        if(coalesce(a.total_spend, 0) > 0,
           round((coalesce(r.attributed_revenue, 0) - coalesce(a.total_spend, 0))
                 / coalesce(a.total_spend, 0) * 100, 2), 0) AS romi,
        if(coalesce(r.new_customers, 0) > 0,
           round(coalesce(a.total_spend, 0) / coalesce(r.new_customers, 1), 2), 0) AS cac
    FROM daily_visits v
    LEFT JOIN daily_ad_stats a ON v.report_date = a.report_date AND v.channel_name = a.channel_name
    LEFT JOIN daily_revenue r ON v.report_date = r.report_date AND v.channel_name = r.channel_name
) AS mart_marketing_rows
