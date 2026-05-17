{{ config(materialized='view', schema='staging') }}

SELECT
    id,
    email,
    coalesce(first_name, '')    AS first_name,
    coalesce(last_name, '')     AS last_name,
    coalesce(city, 'Unknown')   AS city,
    country,
    toDateTime(registered_at)   AS registered_at
FROM staging.raw_web_users
FINAL
