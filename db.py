"""
Shared database connection helper for the e-commerce ETL pipeline.

Connection details come from environment variables so no credentials
are ever hard-coded. Sensible defaults point at a local PostgreSQL.
"""
import os

import psycopg2


def get_conn(dbname=None):
    """Return a new psycopg2 connection (autocommit ON)."""
    return psycopg2.connect(
        host=os.getenv("ECOM_DB_HOST", "localhost"),
        port=int(os.getenv("ECOM_DB_PORT", "5432")),
        dbname=dbname or os.getenv("ECOM_DB_NAME", "ecommerce"),
        user=os.getenv("ECOM_DB_USER", "postgres"),
        password=os.getenv("ECOM_DB_PASSWORD", "postgres"),
    )
