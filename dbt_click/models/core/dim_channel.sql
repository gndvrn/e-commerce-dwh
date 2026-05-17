{{
    config(
        materialized='table',
        schema='core',
        engine='ReplacingMergeTree()',
        order_by='channel_sk'
    )
}}

/*
  dim_channel: traffic / marketing channel dimension.
*/
SELECT
    id         AS channel_sk,
    id         AS source_id,
    name       AS channel_name,
    channel_type
FROM staging.raw_marketing_traffic_sources
FINAL
