{{ config(materialized='view', schema='staging') }}

SELECT
    id,
    coalesce(user_id, 0)       AS user_id,
    coalesce(source_id, 0)     AS source_id,
    coalesce(utm_campaign, '') AS utm_campaign,
    duration_sec,
    page_views,
    is_bounce,
    toDateTime(visited_at) AS visited_at
FROM staging.raw_marketing_visits
FINAL
