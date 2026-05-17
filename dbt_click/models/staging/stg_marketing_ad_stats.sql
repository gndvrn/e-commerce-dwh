{{ config(materialized='view', schema='staging') }}

SELECT
    id,
    campaign_id,
    toDate(stat_date)   AS stat_date,
    impressions,
    clicks,
    spend,
    conversions
FROM staging.raw_marketing_ad_campaign_daily_stats
FINAL
