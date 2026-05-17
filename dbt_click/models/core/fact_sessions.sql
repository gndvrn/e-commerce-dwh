{{
    config(
        materialized='table',
        schema='core',
        engine="MergeTree()",
        order_by='(session_date, customer_sk, channel_sk)',
        partition_by='toYYYYMM(session_date)'
    )
}}

/*
  fact_sessions: grain = one web session / visit.
  Source for Site Traffic, Conversion Rate, Cart Abandon Rate, Avg Time on Site.
*/
WITH cart_status AS (
    SELECT
        session_id,
        max(if(status = 'converted', 1, 0))   AS has_order,
        max(if(status = 'abandoned', 1, 0))   AS was_abandoned
    FROM {{ ref('stg_web_carts') }}
    GROUP BY session_id
)

SELECT
    s.id                                            AS session_sk,
    toInt32(formatDateTime(s.started_at, '%Y%m%d')) AS date_sk,
    toDate(s.started_at)                            AS session_date,
    s.user_id                                       AS customer_sk,
    -- Map utm_source to channel dimension
    coalesce(ch.channel_sk, 0)              AS channel_sk,
    s.page_views,
    dateDiff('second', s.started_at, s.ended_at)   AS duration_sec,
    s.device_type,
    coalesce(cs.has_order, 0)                       AS converted,
    coalesce(cs.was_abandoned, 0)                   AS cart_abandoned,
    if(s.page_views = 1, 1, 0)                     AS is_bounce
FROM {{ ref('stg_web_sessions') }} s
LEFT JOIN cart_status cs ON s.id = cs.session_id
LEFT JOIN {{ ref('dim_channel') }} ch
       ON lower(s.utm_source) = lower(ch.channel_name)
          OR lower(s.utm_source) = lower(ch.channel_type)
