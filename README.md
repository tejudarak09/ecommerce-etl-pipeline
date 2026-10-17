# E-Commerce End-to-End Data Engineering Pipeline

A complete, working data pipeline for a fictional Indian e-commerce store:
**generate → extract → transform → data-quality gate → star-schema marts → KPIs**,
orchestrated by a real Apache Airflow DAG.

## Why this project

It answers the classic data-engineer interview question — *"walk me through a
pipeline you built"* — with a real, runnable system instead of slides:

- **Python ETL** (stdlib + `psycopg2` only — installs anywhere)
- **PostgreSQL** as the warehouse, with a proper **raw → staging → marts** layout
- **Star schema** marts (`dim_customers`, `dim_products`, `dim_dates`, `fact_order_items`)
- **38 automated data-quality checks** that fail the run on bad data
- **Airflow DAG** (daily schedule, retries, failure alerts) for production orchestration
- **10 business analysis queries** on top of the marts

## Architecture

```
┌──────────────┐   ┌────────────┐   ┌──────────────┐   ┌───────────────┐   ┌──────────┐
│ generate_    │   │  extract   │   │  transform   │   │ data_quality  │   │  marts   │
│ data.py      │──▶│  (COPY     │──▶│  (clean →    │──▶│ (38 checks,   │──▶│  (star    │
│ 8k customers │   │   CSVs →   │   │   staging →  │   │  FAIL = stop) │   │  schema) │
│ 500 products │   │   raw.*)   │   │   marts)     │   │               │   │          │
│ 50k orders   │   └────────────┘   └──────────────┘   └───────────────┘   └──────────┘
└──────────────┘                                                        │
        ▲                                                               ▼
        │                                                    ┌────────────────────┐
        │                                                    │ analysis/queries   │
   seeded, reproducible                                      │ .sql → KPIs        │
   random.seed(42)                                           └────────────────────┘

   Orchestration:  run_pipeline.py            (local demo / Windows)
                   dags/ecommerce_etl_dag.py  (Airflow scheduler, @daily)
```

### Layer design

| Layer | Schema | Job |
|---|---|---|
| Raw | `raw.*` | Lands CSVs untouched — every column TEXT. Fast, auditable. |
| Staging | `staging.*` | Cleaned + typed: whitespace stripped, casing normalised, blanks → NULL, exact duplicates dropped, discounts converted to a 0–1 rate, `net_amount_inr` computed. |
| Marts | `marts.*` | Star schema with **surrogate keys** + a `dim_dates` calendar table. One fact row per order line item. |

## KPI highlights (verified run)

| Metric | Value |
|---|---|
| Total revenue (delivered orders) | **₹37.95 Cr** |
| Total orders | 50,000 |
| Delivered / Cancelled / Returned | 85.1% / 8.0% / 6.9% |
| Average order value | **₹8,916** |
| Top category | Electronics — ₹21.46 Cr |
| Top city | Mumbai — ₹5.03 Cr |
| Repeat-purchase rate | 97.5% |
| Data-quality checks | **38/38 PASS** |

## Project structure

```
ecommerce-etl-pipeline/
├── generate_data.py        # seeded synthetic data → data/raw/*.csv
├── extract.py              # COPY CSVs into raw.* (idempotent)
├── transform.py            # raw → staging → marts (idempotent)
├── data_quality.py         # 38 hard checks; non-zero exit on failure
├── run_pipeline.py         # master runner: all steps + KPI summary
├── db.py                   # shared DB connection helper (env vars)
├── sql/ddl.sql             # database + schemas + tables (idempotent)
├── dags/ecommerce_etl_dag.py  # real Airflow DAG (@daily, retries=2)
├── analysis/queries.sql    # 10 business queries
├── data/raw/               # generated CSVs (git-ignored)
├── README.md / INTERVIEW_QA.md / SETUP_WINDOWS.md
└── requirements.txt        # psycopg2-binary only
```

## Quickstart (Windows 11, no Docker)

Full click-by-click guide: **[SETUP_WINDOWS.md](SETUP_WINDOWS.md)**.

Short version — PostgreSQL 16 + Python 3.12 installed:

```bat
:: 1. create the database objects
psql -U postgres -f sql\ddl.sql

:: 2. virtual env + driver
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt

:: 3. run the whole pipeline (~15 seconds)
python run_pipeline.py
```

`run_pipeline.py` prints per-step timings, all 38 quality checks, and the KPI
summary. Every script is idempotent — re-run any time.

## The Airflow note (be ready to say this in interviews)

> "Airflow doesn't run natively on Windows, so for the demo I run the same
> step functions through `run_pipeline.py`. The DAG in `dags/` is the
> production artifact — daily schedule, 2 retries with 5-minute backoff,
> and a failure callback. On a Linux host or WSL2 you drop that file into
> Airflow's `dags/` folder and the scheduler takes over. Same code, no drift."

## How to explain it in an interview (30-second story)

1. *"I built an end-to-end ETL pipeline for Indian e-commerce data — 50,000
   orders, 8,000 customers, 500 products, all synthetic but realistic."*
2. *"Raw CSVs land in Postgres via COPY, then I clean and type them into
   staging, then build a star schema with surrogate keys and a date dimension."*
3. *"38 data-quality checks gate the run — nulls, duplicates, orphan keys,
   bad discounts, and a revenue reconciliation between staging and marts.
   Anything fails, the pipeline stops. Airflow orchestrates it daily in
   production; locally I demo with one command."*

Then walk them through one cleaning rule, one quality check, and one KPI.
Details: **[INTERVIEW_QA.md](INTERVIEW_QA.md)**.
