{{
    config(
        materialized='table',
        schema='core',
        engine='ReplacingMergeTree()',
        order_by='product_sk'
    )
}}

/*
  dim_product: denormalized product with category hierarchy.
  Joins product → leaf category → parent category.
*/
WITH categories AS (
    SELECT id, name AS category_name, parent_id
    FROM {{ ref('stg_web_categories') }}
),
parent_categories AS (
    SELECT id, name AS parent_category_name
    FROM {{ ref('stg_web_categories') }}
)

SELECT
    p.id                                            AS product_sk,
    p.id                                            AS product_id,
    p.product_name,
    p.price,
    p.cost_price,
    p.is_active,
    c.category_name,
    c.id                                            AS category_id,
    coalesce(pc.parent_category_name, c.category_name) AS parent_category_name
FROM {{ ref('stg_web_products') }} p
LEFT JOIN categories c       ON p.category_id = c.id
LEFT JOIN parent_categories pc ON c.parent_id = pc.id
