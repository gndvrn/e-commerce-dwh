{{ config(materialized='view', schema='staging') }}

SELECT
    id,
    coalesce(parent_id, 0) AS parent_id,
    name
FROM staging.raw_web_categories
FINAL
