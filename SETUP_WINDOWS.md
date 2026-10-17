# Setup Guide — Windows 11 (no Docker)

Follow top to bottom. Every command is copy-paste ready — run them from the
project folder (`ecommerce-etl-pipeline`) in Command Prompt or PowerShell.

## Step 1 — Check what you already have

```bat
psql --version
python --version
```

- If `psql` prints a version (e.g. `psql (PostgreSQL 16.x)`), **PostgreSQL is
  already installed — skip to Step 3.**
- If `python` prints 3.12 (or 3.11+), Python is fine — skip its install too.

## Step 2 — Install PostgreSQL 16 (only if Step 1 failed)

1. Download the installer from
   https://www.postgresql.org/download/windows/ (EDB installer).
2. Run it, keep all defaults. When it asks for a password for the
   `postgres` superuser, set one and **remember it** — you'll need it below.
3. Finish the install, then open a **new** Command Prompt and re-run
   `psql --version` to confirm.

## Step 3 — Create the database objects

Open Command Prompt **inside the project folder** and run:

```bat
psql -U postgres -f sql\ddl.sql
```

It will ask for the `postgres` password you set during install. You should
see a list of `CREATE TABLE` lines and no errors.

> If anything goes wrong later with "password authentication failed", your
> postgres password just needs telling to the scripts (see the box in
> Step 5).

## Step 4 — Python environment

```bat
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

You should see `Successfully installed psycopg2-binary`.

## Step 5 — Run the whole pipeline

```bat
python run_pipeline.py
```

This runs everything end to end (~15 seconds): generates 50,000 orders,
builds the database tables, loads, transforms, runs **38 data-quality
checks**, and prints the KPI summary. Expected tail output:

```
38/38 checks passed.
All quality checks passed.
================ KPI SUMMARY ================
  Total revenue (delivered) : ₹37.95 Cr
  Total orders              : 50,000
  ...
Pipeline finished successfully.
```

> **Password box:** the scripts assume your postgres password is
> `postgres`. If yours is different, tell it to the scripts for that
> terminal session before running:
>
> ```bat
> set ECOM_DB_PASSWORD=your_actual_password
> python run_pipeline.py
> ```

Every script is idempotent — re-run `python run_pipeline.py` any time.

## Step 6 — Verify with 3 queries

```bat
psql -U postgres -d ecommerce
```

Then paste these one by one (expected results in brackets):

```sql
SELECT COUNT(*) FROM marts.fact_order_items;
-- 85010

SELECT SUM(net_amount_inr)/10000000 AS revenue_crore
FROM marts.fact_order_items WHERE order_status = 'Delivered';
-- ~37.95

SELECT order_status, COUNT(DISTINCT order_id) AS orders
FROM marts.fact_order_items GROUP BY 1 ORDER BY 2 DESC;
-- Delivered 42560, Cancelled 3986, Returned 3454
```

Type `\q` to exit psql.

## Step 7 — Run the analysis queries (optional)

```bat
psql -U postgres -d ecommerce -f analysis\queries.sql
```

10 business queries: monthly revenue trend, revenue by category/city,
AOV trend, repeat rate, return rate, discount-vs-margin, payment mix,
top-10% customer share, top products.

## Step 8 — Push to GitHub

1. Go to https://github.com and sign in.
2. Click **+ → New repository**.
   - Name: `ecommerce-etl-pipeline`
   - Visibility: **Public**
   - Leave "Add a README", .gitignore and license **unchecked** (empty repo).
3. Click **Create repository**. Back in your project folder:

```bat
git init
git add .
git commit -m "E-commerce end-to-end ETL pipeline: Python + PostgreSQL + Airflow"
git branch -M main
git remote add origin https://github.com/tejudarak09/ecommerce-etl-pipeline.git
git push -u origin main
```

GitHub will ask you to sign in — approve it in the browser window that pops
up. Refresh the repo page: all files should be there (the CSVs in
`data/raw/` are git-ignored on purpose — anyone can regenerate them with
`python generate_data.py`).

## Optional — run the real Airflow DAG (WSL2)

Airflow doesn't install natively on Windows. If you want the scheduler for
real: install WSL2 + Ubuntu from the Microsoft Store, then inside Ubuntu
install Python, PostgreSQL client tools and Apache Airflow, copy this
project in, and drop `dags/ecommerce_etl_dag.py` into Airflow's `dags/`
folder. The DAG calls the exact same step functions — nothing to rewrite.

## Troubleshooting

| Problem | Fix |
|---|---|
| `psql: command not found` | Reopen the terminal after install; the installer adds it to PATH. If still missing, use the full path `C:\Program Files\PostgreSQL\16\bin\psql`. |
| `password authentication failed` | Wrong postgres password — see the password box in Step 5. |
| `ModuleNotFoundError: psycopg2` | You forgot to activate the venv: run `.venv\Scripts\activate` again, then `pip install -r requirements.txt`. |
| `database "ecommerce" does not exist` | Re-run Step 3 (`psql -U postgres -f sql\ddl.sql`). |
| A quality check FAILs | Read which check failed in the output — the detail in brackets tells you exactly what's wrong (e.g. orphan keys). Fix the cause, re-run. |
