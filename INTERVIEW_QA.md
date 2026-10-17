# Interview Q&A — E-Commerce ETL Pipeline

Short, plain answers. Say them in your own words — interviewers can tell
when an answer is memorised.

## 1. Walk me through your pipeline.

I generate 50,000 synthetic Indian e-commerce orders, bulk-load the CSVs into
a `raw` schema with Postgres COPY, clean and type them into `staging`, then
build a star schema in `marts` — customer, product and date dimensions plus
one fact table at line-item grain. 38 data-quality checks gate the run, and
an Airflow DAG orchestrates it daily.

## 2. ETL vs ELT — which did you use and why?

ETL: I transform *before* loading into the final tables (cleaning in
staging, then marts). ELT loads raw data first and transforms inside the
warehouse. I used ETL because the transforms are light and I wanted bad rows
rejected before they ever reach the marts.

## 3. Why three layers — raw, staging, marts?

Raw is the untouched audit trail: if a transform has a bug, I can rebuild
everything from raw without re-generating data. Staging is where cleaning
happens. Marts is the stable, analytics-ready contract that dashboards and
queries read — downstream never breaks when I change cleaning logic.

## 4. Why a star schema instead of one wide table?

A star schema separates *descriptive* attributes (dimensions) from
*measurable* facts. Queries get simpler — one fact table, a few joins —
aggregations are fast, and dimensions are reusable across many fact tables.
A single wide table duplicates customer data on every row and becomes a
nightmare to update.

## 5. Why surrogate keys (customer_key) instead of just customer_id?

Natural keys can change format or get reused. A surrogate key is a stable
internal ID I control, so the fact table never breaks if the source system
renames a customer ID. It also makes slowly-changing-dimension handling
possible later.

## 6. What are slowly changing dimensions? Do you handle them?

SCDs track how dimension attributes change over time — e.g. a customer moves
cities. Type 1 overwrites, Type 2 keeps history with a new row per change.
My dims are currently Type 1 (rebuild each run), but the surrogate keys mean
I can switch to Type 2 later without touching the fact table.

## 7. How is your pipeline idempotent?

Every step truncates its target before loading, so running it twice gives
the same result as running it once — no duplicates. The DDL drops and
rebuilds objects, and the data generator is seeded, so even the source data
is identical every run.

## 8. Why COPY instead of INSERT for loading CSVs?

COPY streams the file directly into Postgres in one operation — orders of
magnitude faster than row-by-row INSERTs. For 85,000 line items it finishes
in a fraction of a second.

## 9. TRUNCATE vs DELETE — why truncate?

TRUNCATE is faster (it deallocates pages instead of deleting row by row)
and resets identity columns. DELETE is for removing *some* rows with a
WHERE clause and keeps a row-level log. Since I reload whole tables, TRUNCATE
is the right tool.

## 10. Explain your data-quality strategy.

Fail fast, fail loud. 38 checks run after every transform: tables non-empty,
no null or duplicate keys, no orphan foreign keys, discounts within [0,1],
dates inside the expected window, and a revenue reconciliation — the rupee
total in staging must equal the total in marts. Any failure exits non-zero
so the orchestrator stops the run instead of publishing bad data.

## 11. What is a DAG in Airflow?

A Directed Acyclic Graph — the workflow definition. "Directed" because tasks
run in dependency order, "acyclic" because there are no loops. My DAG is
`generate → ddl → extract → transform → data_quality → kpi_summary`.

## 12. What is an operator? Which ones did you use?

An operator is a single unit of work — a task template. I used
`PythonOperator` for each pipeline step, calling the same Python functions
the local runner uses, so demo code and production code can't drift apart.

## 13. What does the Airflow scheduler do?

It watches all DAGs, triggers task instances when their schedule and
dependencies are met, and hands them to executors/workers. The web UI shows
every run, task state, logs and retries.

## 14. How do retries work in your DAG?

`retries=2` with a 5-minute `retry_delay`: a failed task is automatically
retried twice before it's marked failed. Transient issues (a DB blip) heal
themselves; persistent ones hit the `on_failure_callback`, which is where
I'd wire email or Slack alerts.

## 15. What is backfilling, and why is catchup=False?

Backfilling runs the DAG for past dates it missed. `catchup=False` means
Airflow only runs from now onward — I don't want it suddenly replaying 18
months of history the first time the DAG is deployed.

## 16. How would you handle late-arriving data?

For a daily batch: re-run the affected date's partition — idempotent loads
make that safe. Longer term, I'd add a watermark (max processed timestamp)
and a late-data task that reprocesses the last N days, plus an alert if
lateness exceeds a threshold.

## 17. How did you compute net_amount_inr?

`quantity × unit_price_inr × (1 − discount_rate)` per line item, computed in
the transform. Doing it once in the pipeline means every downstream query
agrees on revenue — nobody recomputes it differently in five dashboards.

## 18. What does the revenue reconciliation check prove?

That no rows were lost or duplicated between staging and marts. If a join in
the fact build silently dropped line items, the totals would differ and the
run would fail. It's the single most valuable check in the suite.

## 19. How would this scale to 10x the data?

COPY and set-based SQL already scale well into the tens of millions of rows.
Beyond that: partition the fact table by month, index the foreign keys,
run the transform as parallel per-partition tasks, and move the raw files to
object storage (S3) with a distributed engine like Spark for the heavy
transforms. The layered design wouldn't change.

## 20. A DAG task failed at 3 AM. How do you debug it?

Open the Airflow UI, find the failed task instance, read its logs — the
quality-gate output names the exact check that failed. Fix the root cause
(a bad source file, a schema change), clear the failed task so it reruns
from that point, and confirm the downstream tasks go green. Retries may have
already fixed it if it was transient.
