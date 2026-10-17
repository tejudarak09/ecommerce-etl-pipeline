-- =====================================================================
-- Business analysis queries over the marts star schema.
-- Run:  psql -U postgres -d ecommerce -f analysis/queries.sql
-- (Revenue = delivered orders only: cancelled/returned orders earn nothing.)
-- =====================================================================

-- Q1. Monthly revenue trend ------------------------------------------------
SELECT d.year,
       d.month,
       d.month_name,
       COUNT(DISTINCT f.order_id)              AS orders,
       SUM(f.net_amount_inr)                   AS revenue_inr
FROM marts.fact_order_items f
JOIN marts.dim_dates d ON d.date_key = f.date_key
WHERE f.order_status = 'Delivered'
GROUP BY 1, 2, 3
ORDER BY 1, 2;

-- Q2. Revenue by category --------------------------------------------------
SELECT p.category,
       COUNT(DISTINCT f.order_id)              AS orders,
       SUM(f.quantity)                         AS units_sold,
       SUM(f.net_amount_inr)                   AS revenue_inr
FROM marts.fact_order_items f
JOIN marts.dim_products p ON p.product_key = f.product_key
WHERE f.order_status = 'Delivered'
GROUP BY 1
ORDER BY revenue_inr DESC;

-- Q3. Top 10 cities by revenue ---------------------------------------------
SELECT f.shipping_city,
       c.state,
       COUNT(DISTINCT f.order_id)              AS orders,
       SUM(f.net_amount_inr)                   AS revenue_inr
FROM marts.fact_order_items f
JOIN marts.dim_customers c ON c.customer_key = f.customer_key
WHERE f.order_status = 'Delivered'
GROUP BY 1, 2
ORDER BY revenue_inr DESC
LIMIT 10;

-- Q4. Monthly average order value (AOV) trend -------------------------------
SELECT d.year,
       d.month,
       SUM(f.net_amount_inr)
           / NULLIF(COUNT(DISTINCT f.order_id), 0) AS aov_inr
FROM marts.fact_order_items f
JOIN marts.dim_dates d ON d.date_key = f.date_key
WHERE f.order_status = 'Delivered'
GROUP BY 1, 2
ORDER BY 1, 2;

-- Q5. Repeat-purchase rate --------------------------------------------------
-- Share of buyers who placed more than one delivered order.
SELECT COUNT(*) FILTER (WHERE order_cnt > 1) * 100.0
           / NULLIF(COUNT(*), 0)               AS repeat_rate_pct,
       COUNT(*)                                AS buyers,
       COUNT(*) FILTER (WHERE order_cnt > 1)   AS repeat_buyers
FROM (
    SELECT customer_key, COUNT(DISTINCT order_id) AS order_cnt
    FROM marts.fact_order_items
    WHERE order_status = 'Delivered'
    GROUP BY 1
) t;

-- Q6. Return rate by category -----------------------------------------------
-- Returned / (Delivered + Returned): cancelled orders never shipped.
SELECT p.category,
       COUNT(DISTINCT f.order_id)
           FILTER (WHERE f.order_status = 'Returned') * 100.0
           / NULLIF(COUNT(DISTINCT f.order_id)
               FILTER (WHERE f.order_status IN ('Delivered', 'Returned')), 0)
           AS return_rate_pct
FROM marts.fact_order_items f
JOIN marts.dim_products p ON p.product_key = f.product_key
WHERE f.order_status IN ('Delivered', 'Returned')
GROUP BY 1
ORDER BY return_rate_pct DESC;

-- Q7. Discount impact on margin ----------------------------------------------
-- Do deeper discounts actually buy profitable revenue?
SELECT CASE
           WHEN f.discount_rate = 0 THEN '0% (no discount)'
           WHEN f.discount_rate <= 0.10 THEN '1-10%'
           WHEN f.discount_rate <= 0.20 THEN '11-20%'
           ELSE '21-30%'
       END                                   AS discount_bucket,
       SUM(f.net_amount_inr)                 AS revenue_inr,
       SUM(f.net_amount_inr
           - f.quantity * p.cost_inr)        AS margin_inr,
       SUM(f.net_amount_inr
           - f.quantity * p.cost_inr) * 100.0
           / NULLIF(SUM(f.net_amount_inr), 0) AS margin_pct
FROM marts.fact_order_items f
JOIN marts.dim_products p ON p.product_key = f.product_key
WHERE f.order_status = 'Delivered'
GROUP BY 1
ORDER BY MIN(f.discount_rate);

-- Q8. Payment method mix ------------------------------------------------------
SELECT f.payment_method,
       COUNT(DISTINCT f.order_id)              AS orders,
       COUNT(DISTINCT f.order_id) * 100.0
           / SUM(COUNT(DISTINCT f.order_id)) OVER () AS pct_of_orders,
       SUM(f.net_amount_inr)                   AS revenue_inr
FROM marts.fact_order_items f
WHERE f.order_status = 'Delivered'
GROUP BY 1
ORDER BY orders DESC;

-- Q9. Revenue share of the top 10% of customers ---------------------------------
WITH customer_revenue AS (
    SELECT customer_key,
           SUM(net_amount_inr) AS revenue_inr,
           NTILE(10) OVER (ORDER BY SUM(net_amount_inr) DESC) AS decile
    FROM marts.fact_order_items
    WHERE order_status = 'Delivered'
    GROUP BY 1
)
SELECT decile,
       COUNT(*)              AS customers,
       SUM(revenue_inr)      AS revenue_inr,
       SUM(revenue_inr) * 100.0
           / SUM(SUM(revenue_inr)) OVER () AS pct_of_revenue
FROM customer_revenue
GROUP BY 1
ORDER BY 1;

-- Q10. Top 10 products by revenue ----------------------------------------------
SELECT p.product_name,
       p.category,
       p.brand,
       SUM(f.quantity)       AS units_sold,
       SUM(f.net_amount_inr) AS revenue_inr
FROM marts.fact_order_items f
JOIN marts.dim_products p ON p.product_key = f.product_key
WHERE f.order_status = 'Delivered'
GROUP BY 1, 2, 3
ORDER BY revenue_inr DESC
LIMIT 10;
