"""
Master runner — executes the whole pipeline end to end:

    generate_data  ->  ddl  ->  extract  ->  transform  ->  data_quality
                                                        ->  KPI summary

Each step is timed. If the quality gate fails, the run stops with a
non-zero exit code.

The step functions are also imported by dags/ecommerce_etl_dag.py so
Airflow runs exactly the same code.

Run:  python run_pipeline.py
"""
import os
import time

import generate_data
import extract
import transform
import data_quality
from db import get_conn

BASE_DIR = os.path.dirname(os.path.abspath(__file__))


def step_generate():
    generate_data.main()


def step_ddl():
    """Create the database (if needed) and (re)build schemas + tables."""
    sql_path = os.path.join(BASE_DIR, "sql", "ddl.sql")
    with open(sql_path, encoding="utf-8") as f:
        content = f.read()
    marker = "-- __PART2_BELOW__"  # unique marker line in sql/ddl.sql
    if marker not in content:
        raise RuntimeError("sql/ddl.sql is missing the part-2 marker line")
    # Drop the marker line itself; execute everything after it.
    part2 = content.split(marker, 1)[1].split("\n", 1)[1]

    admin = get_conn(dbname="postgres")  # maintenance database
    admin.autocommit = True
    with admin.cursor() as cur:
        cur.execute("SELECT 1 FROM pg_database WHERE datname = 'ecommerce';")
        if cur.fetchone() is None:
            print("creating database ecommerce ...")
            cur.execute("CREATE DATABASE ecommerce;")
    admin.close()

    conn = get_conn()  # now connects to ecommerce
    conn.autocommit = True
    with conn.cursor() as cur:
        cur.execute(part2)  # schemas + tables (idempotent)
    conn.close()
    print("ddl applied: schemas raw / staging / marts rebuilt.")


def step_extract():
    extract.main()


def step_transform():
    transform.main()


def step_quality():
    data_quality.main()  # exits non-zero if any check fails


# ------------------------------------------------------------------ KPIs ----
def inr_crore(x):
    return f"\u20b9{x / 1e7:,.2f} Cr"


def get_kpis():
    """Return the headline business metrics as a dict."""
    conn = get_conn()
    conn.autocommit = True
    k = {}
    with conn.cursor() as cur:
        cur.execute("SELECT COUNT(*) FROM marts.fact_order_items;")
        k["fact_rows"] = cur.fetchone()[0]
        cur.execute("SELECT COUNT(DISTINCT order_id) "
                    "FROM marts.fact_order_items;")
        k["total_orders"] = cur.fetchone()[0]
        cur.execute("SELECT COALESCE(SUM(net_amount_inr), 0) "
                    "FROM marts.fact_order_items "
                    "WHERE order_status = 'Delivered';")
        k["revenue_inr"] = float(cur.fetchone()[0])
        cur.execute("SELECT COUNT(DISTINCT order_id) "
                    "FROM marts.fact_order_items "
                    "WHERE order_status = 'Delivered';")
        k["delivered_orders"] = cur.fetchone()[0]
        k["aov_inr"] = (k["revenue_inr"] / k["delivered_orders"]
                        if k["delivered_orders"] else 0)
        cur.execute("SELECT order_status, COUNT(DISTINCT order_id) "
                    "FROM marts.fact_order_items GROUP BY 1;")
        k["status_counts"] = dict(cur.fetchall())
        cur.execute("""
            SELECT p.category, SUM(f.net_amount_inr)
            FROM marts.fact_order_items f
            JOIN marts.dim_products p ON p.product_key = f.product_key
            WHERE f.order_status = 'Delivered'
            GROUP BY 1 ORDER BY 2 DESC LIMIT 3;""")
        k["top_categories"] = [(r[0], float(r[1])) for r in cur.fetchall()]
        cur.execute("""
            SELECT shipping_city, SUM(net_amount_inr)
            FROM marts.fact_order_items
            WHERE order_status = 'Delivered'
            GROUP BY 1 ORDER BY 2 DESC LIMIT 3;""")
        k["top_cities"] = [(r[0], float(r[1])) for r in cur.fetchall()]
        cur.execute("""
            SELECT COUNT(*) FROM (
                SELECT customer_key
                FROM marts.fact_order_items
                WHERE order_status = 'Delivered'
                GROUP BY customer_key
                HAVING COUNT(DISTINCT order_id) > 1
            ) t;""")
        k["repeat_buyers"] = cur.fetchone()[0]
        cur.execute("SELECT COUNT(DISTINCT customer_key) "
                    "FROM marts.fact_order_items "
                    "WHERE order_status = 'Delivered';")
        k["buyers"] = cur.fetchone()[0]
    conn.close()
    k["repeat_rate_pct"] = (100.0 * k["repeat_buyers"] / k["buyers"]
                            if k["buyers"] else 0)
    return k


def print_kpi_summary():
    k = get_kpis()
    total = sum(k["status_counts"].values()) or 1
    print("\n================ KPI SUMMARY ================")
    print(f"  Total revenue (delivered) : {inr_crore(k['revenue_inr'])}")
    print(f"  Total orders              : {k['total_orders']:,}")
    print(f"  Delivered orders          : {k['delivered_orders']:,}")
    print(f"  Average order value (AOV) : \u20b9{k['aov_inr']:,.0f}")
    for status in ("Delivered", "Cancelled", "Returned"):
        n = k["status_counts"].get(status, 0)
        print(f"  {status:<24}: {n:>7,} ({100.0 * n / total:4.1f}%)")
    print("  Top 3 categories by revenue:")
    for cat, rev in k["top_categories"]:
        print(f"    - {cat:<16} {inr_crore(rev)}")
    print("  Top 3 cities by revenue:")
    for city, rev in k["top_cities"]:
        print(f"    - {city:<16} {inr_crore(rev)}")
    print(f"  Repeat-purchase rate      : {k['repeat_rate_pct']:.1f}% "
          f"({k['repeat_buyers']:,} of {k['buyers']:,} buyers)")
    print("=============================================")
    return k


def main():
    steps = [
        ("generate_data", step_generate),
        ("ddl", step_ddl),
        ("extract", step_extract),
        ("transform", step_transform),
        ("data_quality", step_quality),
    ]
    for name, fn in steps:
        print(f"\n===== STEP: {name} =====")
        t0 = time.perf_counter()
        fn()
        print(f"----- {name} done in {time.perf_counter() - t0:.1f}s -----")
    print_kpi_summary()
    print("\nPipeline finished successfully.")


if __name__ == "__main__":
    main()
