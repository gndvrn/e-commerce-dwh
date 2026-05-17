{{
    config(
        materialized='table',
        schema='core',
        engine='ReplacingMergeTree()',
        order_by='date_sk'
    )
}}

/*
  dim_date: calendar dimension spine covering 3 years.
  Used as the primary date join key across all fact tables.
*/
SELECT
    toInt32(formatDateTime(d, '%Y%m%d'))    AS date_sk,
    d                                        AS date_day,
    toYear(d)                                AS year,
    toQuarter(d)                             AS quarter,
    toMonth(d)                               AS month,
    -- ClickHouse formatDateTime does not support strftime %B / %A
    arrayElement(
        ['January','February','March','April','May','June','July','August','September','October','November','December'],
        toMonth(d)
    )                                        AS month_name,
    toWeek(d)                                AS week_of_year,
    toDayOfWeek(d, 0)                        AS day_of_week,
    arrayElement(
        ['Monday','Tuesday','Wednesday','Thursday','Friday','Saturday','Sunday'],
        toDayOfWeek(d, 0)
    )                                        AS day_name,
    if(toDayOfWeek(d, 0) IN (6, 7), 1, 0)   AS is_weekend,
    concat(toString(toYear(d)), '-Q', toString(toQuarter(d))) AS quarter_label
FROM (
    SELECT
        addDays(toDate('2023-01-01'), number) AS d
    FROM numbers(1095)  -- 3 years
)
