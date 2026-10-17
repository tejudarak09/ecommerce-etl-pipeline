"""
Airflow DAG — production orchestration for the e-commerce ETL pipeline.

Runs daily: generate -> ddl -> extract -> transform -> data_quality -> kpis.
Each task calls the SAME step function that run_pipeline.py uses locally,
so the demo on a laptop and the scheduled run can never drift apart.

Concepts on display (good interview talking points):
  * DAG            - the workflow definition (this file)
  * Operator       - a single unit of work (PythonOperator per step)
  * Scheduler      - the Airflow process that triggers the DAG on schedule
  * retries        - a failed task is retried 2x before alerting
  * catchup=False  - don't backfill missed historical runs
  * XComs / logs   - every task's stdout is captured in the Airflow UI

Demo note: Airflow does not run natively on Windows, so the day-to-day
demo uses `python run_pipeline.py` (the local runner). In production this
DAG file is dropped into Airflow's dags/ folder on a Linux scheduler host
(or run under WSL2 on Windows — see SETUP_WINDOWS.md).
"""
import os
import sys
from datetime import timedelta

from airflow import DAG
from airflow.operators.python import PythonOperator
from airflow.utils.dates import days_ago

# Make the pipeline modules importable (this file lives in dags/, the
# pipeline code lives one level up).
PROJECT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_DIR)

from run_pipeline import (  # noqa: E402  (import after sys.path fix)
    step_generate,
    step_ddl,
    step_extract,
    step_transform,
    step_quality,
    print_kpi_summary,
)


def alert_failure(context):
    """on_failure_callback: stub — wire to email/Slack/PagerDuty in prod."""
    task_id = context["task_instance"].task_id
    dag_id = context["dag"].dag_id
    print(f"ALERT: task '{task_id}' in DAG '{dag_id}' FAILED. "
          f"Check the Airflow UI logs. (Stub: plug in email/Slack here.)")


default_args = {
    "owner": "teju",
    "depends_on_past": False,
    "retries": 2,                                   # retry a failed task 2x
    "retry_delay": timedelta(minutes=5),            # wait 5 min between tries
    "on_failure_callback": alert_failure,           # alert when retries run out
}

with DAG(
    dag_id="ecommerce_etl_pipeline",
    description="Daily e-commerce ETL: generate -> load -> transform -> quality",
    default_args=default_args,
    schedule_interval="@daily",                     # run once a day
    start_date=days_ago(1),
    catchup=False,                                  # no historical backfill
    tags=["ecommerce", "etl", "portfolio"],
) as dag:

    generate = PythonOperator(
        task_id="generate_data",
        python_callable=step_generate,
    )
    ddl = PythonOperator(
        task_id="create_schema",
        python_callable=step_ddl,
    )
    extract = PythonOperator(
        task_id="extract",
        python_callable=step_extract,
    )
    transform = PythonOperator(
        task_id="transform",
        python_callable=step_transform,
    )
    quality = PythonOperator(
        task_id="data_quality",
        python_callable=step_quality,   # raises -> task fails -> retried
    )
    kpis = PythonOperator(
        task_id="kpi_summary",
        python_callable=print_kpi_summary,
    )

    # Task dependencies: each step waits for the previous one.
    generate >> ddl >> extract >> transform >> quality >> kpis
