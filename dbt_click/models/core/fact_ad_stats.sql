{{
    config(
        materialized='table',
        schema='core',
        engine="MergeTree()",
        order_by='(stat_date, campaign_sk)',
        partition_by='toYYYYMM(stat_date)'
    )
}}

/*
  fact_ad_stats: grain = one campaign × one day.
  Source for CPC, ROMI, CAC, impressions, click-through rate.
*/
SELECT
    s.id                                            AS ad_stat_sk,
    toInt32(formatDateTime(toDateTime(s.stat_date), '%Y%m%d')) AS date_sk,
    s.stat_date,
    s.campaign_id                                   AS campaign_sk,
    c.source_id                                     AS channel_sk,
    s.impressions,
    s.clicks,
    s.spend,
    s.conversions,
    -- Derived metrics (pre-computed for performance)
    if(s.impressions > 0,
       toFloat64(s.clicks) / s.impressions, 0)      AS ctr,
    if(s.clicks > 0,
       s.spend / s.clicks, 0)                       AS cpc,
    if(s.conversions > 0,
       s.spend / s.conversions, 0)                  AS cost_per_conversion
FROM {{ ref('stg_marketing_ad_stats') }} s
LEFT JOIN {{ ref('dim_campaign') }} c ON s.campaign_id = c.campaign_sk
