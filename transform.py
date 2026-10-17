"""
Step 3 — TRANSFORM: raw → staging (clean) → marts (star schema).

Staging cleaning rules:
  * strip leading/trailing whitespace everywhere
  * cast text to proper types (dates, numbers); blanks become NULL
  * normalise status / payment_method casing to canonical labels
  * drop exact-duplicate rows (keep one per business key)
  * discount_pct (e.g. "15.0" meaning 15%) -> discount_rate (0.15)

Marts: dimension tables with surrogate keys + a date dimension built
with generate_series, and one fact table at line-item grain.

Idempotent: truncates staging + marts (RESTART IDENTITY) before loading.

Run:  python transform.py
"""
from db import get_conn

TRUNCATE_SQL = """
TRUNCATE
    marts.fact_order_items,
    marts.dim_dates,
    marts.dim_products,
    marts.dim_customers,
    staging.order_items,
    staging.orders,
    staging.products,
    staging.customers
RESTART IDENTITY;
"""

STAGING_SQL = """
-- ---------------- customers ----------------
INSERT INTO staging.customers
    (customer_id, first_name, last_name, email, phone, city, state, signup_date)
SELECT DISTINCT ON (TRIM(customer_id))
    TRIM(customer_id),
    INITCAP(TRIM(first_name)),
    INITCAP(TRIM(last_name)),
    NULLIF(LOWER(TRIM(email)), ''),
    TRIM(phone),
    INITCAP(TRIM(city)),
    INITCAP(TRIM(state)),
    NULLIF(TRIM(signup_date), '')::DATE
FROM raw.customers;

-- ---------------- products -----------------
INSERT INTO staging.products
    (product_id, product_name, category, brand, price_inr, cost_inr)
SELECT DISTINCT ON (TRIM(product_id))
    TRIM(product_id),
    TRIM(product_name),
    INITCAP(TRIM(category)),
    TRIM(brand),
    NULLIF(TRIM(price_inr), '')::NUMERIC(12, 2),
    NULLIF(TRIM(cost_inr), '')::NUMERIC(12, 2)
FROM raw.products;

-- ---------------- orders -------------------
INSERT INTO staging.orders
    (order_id, customer_id, order_date, status,
     payment_method, shipping_city, shipping_state)
SELECT DISTINCT ON (TRIM(order_id))
    TRIM(order_id),
    TRIM(customer_id),
    NULLIF(TRIM(order_date), '')::DATE,
    CASE LOWER(TRIM(status))
        WHEN 'delivered' THEN 'Delivered'
        WHEN 'cancelled' THEN 'Cancelled'
        WHEN 'returned'  THEN 'Returned'
        ELSE INITCAP(TRIM(status))
    END,
    CASE LOWER(TRIM(payment_method))
        WHEN 'upi'         THEN 'UPI'
        WHEN 'cod'         THEN 'COD'
        WHEN 'credit card' THEN 'Credit Card'
        WHEN 'debit card'  THEN 'Debit Card'
        WHEN 'netbanking'  THEN 'Netbanking'
        WHEN 'wallet'      THEN 'Wallet'
        ELSE TRIM(payment_method)
    END,
    INITCAP(TRIM(shipping_city)),
    INITCAP(TRIM(shipping_state))
FROM raw.orders;

-- ---------------- order items --------------
INSERT INTO staging.order_items
    (order_item_id, order_id, product_id, quantity,
     unit_price_inr, discount_rate, net_amount_inr)
SELECT DISTINCT ON (TRIM(order_item_id))
    TRIM(order_item_id),
    TRIM(order_id),
    TRIM(product_id),
    NULLIF(TRIM(quantity), '')::INT,
    NULLIF(TRIM(unit_price_inr), '')::NUMERIC(12, 2),
    COALESCE(NULLIF(TRIM(discount_pct), '')::NUMERIC / 100, 0),
    NULLIF(TRIM(quantity), '')::INT
        * NULLIF(TRIM(unit_price_inr), '')::NUMERIC(12, 2)
        * (1 - COALESCE(NULLIF(TRIM(discount_pct), '')::NUMERIC / 100, 0))
FROM raw.order_items;
"""

MARTS_SQL = """
-- ---------------- dimensions ---------------
INSERT INTO marts.dim_customers
    (customer_id, first_name, last_name, email, phone, city, state, signup_date)
SELECT customer_id, first_name, last_name, email, phone, city, state, signup_date
FROM staging.customers;

INSERT INTO marts.dim_products
    (product_id, product_name, category, brand, price_inr, cost_inr)
SELECT product_id, product_name, category, brand, price_inr, cost_inr
FROM staging.products;

-- date dimension: one row per calendar day in the order range
INSERT INTO marts.dim_dates
    (date_key, full_date, year, quarter, month, month_name,
     day, day_of_week, day_name, is_weekend)
SELECT
    TO_CHAR(d, 'YYYYMMDD')::INT,
    d::DATE,
    EXTRACT(YEAR FROM d)::INT,
    EXTRACT(QUARTER FROM d)::INT,
    EXTRACT(MONTH FROM d)::INT,
    TRIM(TO_CHAR(d, 'Month')),
    EXTRACT(DAY FROM d)::INT,
    EXTRACT(DOW FROM d)::INT,            -- 0 = Sunday
    TRIM(TO_CHAR(d, 'Day')),
    EXTRACT(DOW FROM d)::INT IN (0, 6)
FROM generate_series(
        (SELECT MIN(order_date) FROM staging.orders),
        (SELECT MAX(order_date) FROM staging.orders),
        INTERVAL '1 day'
     ) AS d;

-- ---------------- fact (line-item grain) ---
INSERT INTO marts.fact_order_items
    (order_item_id, order_id, customer_key, product_key, date_key,
     quantity, unit_price_inr, discount_rate, net_amount_inr,
     order_status, payment_method, shipping_city)
SELECT
    i.order_item_id,
    i.order_id,
    dc.customer_key,
    dp.product_key,
    dd.date_key,
    i.quantity,
    i.unit_price_inr,
    i.discount_rate,
    i.net_amount_inr,
    o.status,
    o.payment_method,
    o.shipping_city
FROM staging.order_items AS i
JOIN staging.orders        AS o  ON o.order_id   = i.order_id
JOIN marts.dim_customers    AS dc ON dc.customer_id = o.customer_id
JOIN marts.dim_products     AS dp ON dp.product_id  = i.product_id
JOIN marts.dim_dates        AS dd ON dd.full_date   = o.order_date;
"""

COUNT_TABLES = [
    "staging.customers", "staging.products",
    "staging.orders", "staging.order_items",
    "marts.dim_customers", "marts.dim_products",
    "marts.dim_dates", "marts.fact_order_items",
]


def main():
    conn = get_conn()
    conn.autocommit = True
    with conn.cursor() as cur:
        cur.execute(TRUNCATE_SQL)
        cur.execute(STAGING_SQL)
        cur.execute(MARTS_SQL)
        counts = {}
        for table in COUNT_TABLES:
            cur.execute(f"SELECT COUNT(*) FROM {table};")
            counts[table] = cur.fetchone()[0]
    conn.close()

    print("TRANSFORM complete — row counts:")
    for table, n in counts.items():
        print(f"  {table:<24} {n:>10,}")
    return counts


if __name__ == "__main__":
    main()
