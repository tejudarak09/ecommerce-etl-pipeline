"""
Step 2 — EXTRACT: bulk-load the raw CSVs into the `raw` schema.

Uses PostgreSQL COPY (via psycopg2 copy_expert) — the fastest way to
load flat files, far quicker than row-by-row INSERTs.

Idempotent: truncates the raw tables before loading, so re-running
never creates duplicates.

Run:  python extract.py
"""
import os

from db import get_conn

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
RAW_DIR = os.path.join(BASE_DIR, "data", "raw")

# (table, csv file)
LOAD_ORDER = [
    ("raw.customers", "customers.csv"),
    ("raw.products", "products.csv"),
    ("raw.orders", "orders.csv"),
    ("raw.order_items", "order_items.csv"),
]


def main():
    missing = [csv for _, csv in LOAD_ORDER
               if not os.path.exists(os.path.join(RAW_DIR, csv))]
    if missing:
        raise SystemExit(
            f"Missing CSV files in data/raw/: {missing}. "
            "Run `python generate_data.py` first.")

    conn = get_conn()
    conn.autocommit = True
    counts = {}
    with conn.cursor() as cur:
        for table, csv_file in LOAD_ORDER:
            path = os.path.join(RAW_DIR, csv_file)
            cur.execute(f"TRUNCATE {table};")          # idempotent reload
            with open(path, "r", encoding="utf-8") as f:
                cur.copy_expert(
                    f"COPY {table} FROM STDIN WITH (FORMAT CSV, HEADER TRUE)",
                    f,
                )
            cur.execute(f"SELECT COUNT(*) FROM {table};")
            counts[table] = cur.fetchone()[0]
    conn.close()

    print("EXTRACT complete — raw row counts:")
    for table, n in counts.items():
        print(f"  {table:<18} {n:>10,}")
    return counts


if __name__ == "__main__":
    main()
