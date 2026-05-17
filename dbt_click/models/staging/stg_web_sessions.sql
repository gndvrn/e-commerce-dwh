{{ config(materialized='view', schema='staging') }}

SELECT
    id,
    coalesce(user_id, 0)       AS user_id,
    coalesce(utm_source, '')   AS utm_source,
    coalesce(utm_campaign, '') AS utm_campaign,
    device_type,
    toDateTime(started_at)     AS started_at,
    toDateTime(coalesce(ended_at, started_at)) AS ended_at,
    page_views
FROM staging.raw_web_sessions
FINAL
