"""Toy Airflow DAG that 'ingests' raw.payments."""
from airflow import DAG
from airflow.operators.python import PythonOperator
from datetime import datetime


def extract_payments():
    # writes to: raw.payments
    pass


with DAG(
    dag_id="payments_ingest",
    schedule="0 4 * * *",
    start_date=datetime(2024, 1, 1),
    catchup=False,
) as dag:
    extract = PythonOperator(
        task_id="extract",
        python_callable=extract_payments,
    )
