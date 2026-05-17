{{
    config(
        materialized='table',
        schema='core',
        engine='ReplacingMergeTree()',
        order_by='campaign_sk'
    )
}}

/*
  dim_campaign: paid advertising campaign dimension.
*/
SELECT
    id                              AS campaign_sk,
    id                              AS campaign_id,
    source_id,
    name                            AS campaign_name,
    coalesce(budget, 0)             AS budget,
    actual_spend,
    coalesce(start_date, toDate('2024-01-01'))   AS start_date,
    coalesce(end_date, toDate('2024-12-31'))      AS end_date
FROM staging.raw_marketing_ad_campaigns
FINAL
