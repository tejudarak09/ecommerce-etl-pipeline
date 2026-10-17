-- =====================================================================
-- E-Commerce ETL Pipeline — database objects
--
-- Manual run (psql):   psql -U postgres -f sql/ddl.sql
--   The first block creates the database (psql only); the script then
--   switches to it with \c and builds schemas + tables.
-- Automated run:       run_pipeline.py executes everything after the
--   "\c ecommerce" line on the ecommerce database (it creates the
--   database itself first).
-- Idempotent: safe to re-run; existing objects are dropped and rebuilt.
-- =====================================================================

-- ---- Part 1: database (psql path only) --------------------------------
SELECT 'CREATE DATABASE ecommerce'
WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = 'ecommerce')\gexec

\c ecommerce
-- __PART2_BELOW__ (run_pipeline.py executes everything after this line)

-- ---- Part 2: schemas and tables ---------------------------------------
CREATE SCHEMA IF NOT EXISTS raw;
CREATE SCHEMA IF NOT EXISTS staging;
CREATE SCHEMA IF NOT EXISTS marts;

-- Drop in dependency order (CASCADE keeps it simple and safe).
DROP TABLE IF EXISTS marts.fact_order_items CASCADE;
DROP TABLE IF EXISTS marts.dim_dates CASCADE;
DROP TABLE IF EXISTS marts.dim_products CASCADE;
DROP TABLE IF EXISTS marts.dim_customers CASCADE;
DROP TABLE IF EXISTS staging.order_items CASCADE;
DROP TABLE IF EXISTS staging.orders CASCADE;
DROP TABLE IF EXISTS staging.products CASCADE;
DROP TABLE IF EXISTS staging.customers CASCADE;
DROP TABLE IF EXISTS raw.order_items CASCADE;
DROP TABLE IF EXISTS raw.orders CASCADE;
DROP TABLE IF EXISTS raw.products CASCADE;
DROP TABLE IF EXISTS raw.customers CASCADE;

-- ============================ RAW (landing: everything is TEXT) =======
-- Raw mirrors the CSV files 1:1. No typing, no constraints — the job of
-- this layer is to land the files fast and untouched.

CREATE TABLE raw.customers (
    customer_id TEXT,
    first_name  TEXT,
    last_name   TEXT,
    email       TEXT,
    phone       TEXT,
    city        TEXT,
    state       TEXT,
    signup_date TEXT
);

CREATE TABLE raw.products (
    product_id   TEXT,
    product_name TEXT,
    category     TEXT,
    brand        TEXT,
    price_inr    TEXT,
    cost_inr     TEXT
);

CREATE TABLE raw.orders (
    order_id       TEXT,
    customer_id    TEXT,
    order_date     TEXT,
    status         TEXT,
    payment_method TEXT,
    shipping_city  TEXT,
    shipping_state TEXT
);

CREATE TABLE raw.order_items (
    order_item_id TEXT,
    order_id      TEXT,
    product_id    TEXT,
    quantity      TEXT,
    unit_price_inr TEXT,
    discount_pct  TEXT
);

-- ============================ STAGING (cleaned + typed) ================
-- One row per business entity, properly typed, de-duplicated, normalised.

CREATE TABLE staging.customers (
    customer_id TEXT PRIMARY KEY,
    first_name  TEXT,
    last_name   TEXT,
    email       TEXT,
    phone       TEXT,
    city        TEXT,
    state       TEXT,
    signup_date DATE
);

CREATE TABLE staging.products (
    product_id   TEXT PRIMARY KEY,
    product_name TEXT,
    category     TEXT,
    brand        TEXT,
    price_inr    NUMERIC(12, 2),
    cost_inr     NUMERIC(12, 2)
);

CREATE TABLE staging.orders (
    order_id       TEXT PRIMARY KEY,
    customer_id    TEXT NOT NULL REFERENCES staging.customers (customer_id),
    order_date     DATE NOT NULL,
    status         TEXT NOT NULL,          -- Delivered | Cancelled | Returned
    payment_method TEXT NOT NULL,          -- UPI | COD | Credit Card | ...
    shipping_city  TEXT,
    shipping_state TEXT
);

CREATE TABLE staging.order_items (
    order_item_id  TEXT PRIMARY KEY,
    order_id       TEXT NOT NULL REFERENCES staging.orders (order_id),
    product_id     TEXT NOT NULL REFERENCES staging.products (product_id),
    quantity       INT NOT NULL,
    unit_price_inr NUMERIC(12, 2) NOT NULL,
    discount_rate  NUMERIC(6, 4) NOT NULL, -- 0.00 - 1.00  (0.15 = 15% off)
    net_amount_inr NUMERIC(12, 2) NOT NULL  -- qty * price * (1 - discount_rate)
);

-- ============================ MARTS (star schema) ======================
-- Analytics-ready: skinny dimension tables + one fact table at
-- line-item grain. Surrogate keys keep the model stable if natural
-- keys ever change (SCD-ready).

CREATE TABLE marts.dim_customers (
    customer_key SERIAL PRIMARY KEY,
    customer_id  TEXT NOT NULL UNIQUE,
    first_name   TEXT,
    last_name    TEXT,
    email        TEXT,
    phone        TEXT,
    city         TEXT,
    state        TEXT,
    signup_date  DATE
);

CREATE TABLE marts.dim_products (
    product_key  SERIAL PRIMARY KEY,
    product_id   TEXT NOT NULL UNIQUE,
    product_name TEXT,
    category     TEXT,
    brand        TEXT,
    price_inr    NUMERIC(12, 2),
    cost_inr     NUMERIC(12, 2)
);

CREATE TABLE marts.dim_dates (
    date_key    INT PRIMARY KEY,           -- YYYYMMDD, e.g. 20240115
    full_date   DATE NOT NULL UNIQUE,
    year        INT NOT NULL,
    quarter     INT NOT NULL,
    month       INT NOT NULL,
    month_name  TEXT NOT NULL,
    day         INT NOT NULL,
    day_of_week INT NOT NULL,              -- 0 = Sunday .. 6 = Saturday
    day_name    TEXT NOT NULL,
    is_weekend  BOOLEAN NOT NULL
);

CREATE TABLE marts.fact_order_items (
    fact_key       BIGSERIAL PRIMARY KEY,
    order_item_id  TEXT NOT NULL UNIQUE,
    order_id       TEXT NOT NULL,
    customer_key   INT NOT NULL REFERENCES marts.dim_customers (customer_key),
    product_key    INT NOT NULL REFERENCES marts.dim_products (product_key),
    date_key       INT NOT NULL REFERENCES marts.dim_dates (date_key),
    quantity       INT NOT NULL,
    unit_price_inr NUMERIC(12, 2) NOT NULL,
    discount_rate  NUMERIC(6, 4) NOT NULL,
    net_amount_inr NUMERIC(12, 2) NOT NULL,
    order_status   TEXT NOT NULL,          -- carried from the order header
    payment_method TEXT NOT NULL,
    shipping_city  TEXT
);
