"""
Step 4 — DATA QUALITY: hard gates that FAIL the pipeline on bad data.

Every check prints PASS/FAIL. If any check fails, the script exits
with a non-zero status so an orchestrator (Airflow, CI, run_pipeline)
stops the run instead of publishing bad data.

Checks:
  1. no empty tables
  2. no NULL primary keys
  3. no duplicate primary keys
  4. no orphan foreign keys
  5. discount_rate always within [0, 1]
  6. order dates inside the expected range
  7. revenue reconciliation: staging total == marts total

Run:  python data_quality.py
"""
import sys

from db import get_conn

EXPECTED_MIN_DATE = "2024-01-01"
EXPECTED_MAX_DATE = "2025-06-30"

TABLES = [
    "raw.customers", "raw.products", "raw.orders", "raw.order_items",
    "staging.customers", "staging.products",
    "staging.orders", "staging.order_items",
    "marts.dim_customers", "marts.dim_products",
    "marts.dim_dates", "marts.fact_order_items",
]

# Primary / unique keys that must be NOT NULL and unique.
KEY_COLUMNS = [
    ("staging.customers", "customer_id"),
    ("staging.products", "product_id"),
    ("staging.orders", "order_id"),
    ("staging.order_items", "order_item_id"),
    ("marts.dim_customers", "customer_id"),
    ("marts.dim_products", "product_id"),
    ("marts.dim_dates", "date_key"),
    ("marts.fact_order_items", "order_item_id"),
]

# (check name, child table, child column, parent table, parent column)
FK_CHECKS = [
    ("orders -> customers", "staging.orders", "customer_id",
     "staging.customers", "customer_id"),
    ("order_items -> orders", "staging.order_items", "order_id",
     "staging.orders", "order_id"),
    ("order_items -> products", "staging.order_items", "product_id",
     "staging.products", "product_id"),
    ("fact -> dim_customers", "marts.fact_order_items", "customer_key",
     "marts.dim_customers", "customer_key"),
    ("fact -> dim_products", "marts.fact_order_items", "product_key",
     "marts.dim_products", "product_key"),
    ("fact -> dim_dates", "marts.fact_order_items", "date_key",
     "marts.dim_dates", "date_key"),
]


def run_checks():
    """Return a list of (name, passed: bool, detail: str)."""
    results = []
    conn = get_conn()
    conn.autocommit = True
    with conn.cursor() as cur:
        # 1. no empty tables
        for table in TABLES:
            cur.execute(f"SELECT COUNT(*) FROM {table};")
            n = cur.fetchone()[0]
            results.append((f"non-empty: {table}", n > 0, f"{n:,} rows"))

        # 2 + 3. NULL and duplicate keys
        for table, col in KEY_COLUMNS:
            cur.execute(
                f"SELECT COUNT(*) FROM {table} WHERE {col} IS NULL;")
            n_null = cur.fetchone()[0]
            results.append((f"no NULL key: {table}.{col}",
                            n_null == 0, f"{n_null:,} NULLs"))
            cur.execute(
                f"SELECT COUNT(*) - COUNT(DISTINCT {col}) FROM {table};")
            n_dup = cur.fetchone()[0]
            results.append((f"no duplicate key: {table}.{col}",
                            n_dup == 0, f"{n_dup:,} duplicates"))

        # 4. orphan foreign keys
        for name, child_t, child_c, parent_t, parent_c in FK_CHECKS:
            cur.execute(
                f"""SELECT COUNT(*) FROM {child_t} c
                    LEFT JOIN {parent_t} p ON p.{parent_c} = c.{child_c}
                    WHERE c.{child_c} IS NOT NULL AND p.{parent_c} IS NULL;""")
            n_orphan = cur.fetchone()[0]
            results.append((f"no orphan FK: {name}",
                            n_orphan == 0, f"{n_orphan:,} orphans"))

        # 5. discount_rate in [0, 1]
        for table in ("staging.order_items", "marts.fact_order_items"):
            cur.execute(
                f"""SELECT COUNT(*) FROM {table}
                    WHERE discount_rate < 0 OR discount_rate > 1
                       OR discount_rate IS NULL;""")
            n_bad = cur.fetchone()[0]
            results.append((f"discount in [0,1]: {table}",
                            n_bad == 0, f"{n_bad:,} bad rows"))

        # 6. order dates inside the expected window
        cur.execute(
            f"""SELECT COUNT(*) FROM staging.orders
                WHERE order_date < DATE '{EXPECTED_MIN_DATE}'
                   OR order_date > DATE '{EXPECTED_MAX_DATE}';""")
        n_bad = cur.fetchone()[0]
        results.append(("order_date in range [2024-01-01, 2025-06-30]",
                        n_bad == 0, f"{n_bad:,} out-of-range rows"))

        # 7. revenue reconciliation: staging total == marts total
        cur.execute("SELECT COALESCE(SUM(net_amount_inr), 0) "
                    "FROM staging.order_items;")
        staging_total = float(cur.fetchone()[0])
        cur.execute("SELECT COALESCE(SUM(net_amount_inr), 0) "
                    "FROM marts.fact_order_items;")
        marts_total = float(cur.fetchone()[0])
        diff = abs(staging_total - marts_total)
        results.append(("revenue reconciles staging == marts", diff < 0.01,
                        f"staging={staging_total:,.2f} "
                        f"marts={marts_total:,.2f} diff={diff:.2f}"))
    conn.close()
    return results


def main():
    print("DATA QUALITY checks:")
    results = run_checks()
    failed = 0
    for name, passed, detail in results:
        status = "PASS" if passed else "FAIL"
        if not passed:
            failed += 1
        print(f"  [{status}] {name} ({detail})")
    print(f"{len(results) - failed}/{len(results)} checks passed.")
    if failed:
        print("QUALITY GATE FAILED — stopping the pipeline.")
        sys.exit(1)
    print("All quality checks passed.")
    return results


if __name__ == "__main__":
    main()
