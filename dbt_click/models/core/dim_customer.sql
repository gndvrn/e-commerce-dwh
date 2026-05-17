{{
    config(
        materialized='table',
        schema='core',
        engine='ReplacingMergeTree()',
        order_by='customer_sk'
    )
}}

/*
  dim_customer: denormalized customer profile.
  SCD Type 1 – latest record wins (ReplacingMergeTree).
*/
SELECT
    id                                        AS customer_sk,
    id                                        AS customer_id,
    email,
    first_name,
    last_name,
    city,
    country,
    toDate(registered_at)                     AS registration_date,
    toYear(registered_at)                     AS registration_year,
    toMonth(registered_at)                    AS registration_month
FROM {{ ref('stg_web_users') }}
