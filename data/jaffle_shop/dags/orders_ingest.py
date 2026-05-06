"""Toy Airflow DAG that 'ingests' raw.orders."""
from airflow import DAG
from airflow.operators.python import PythonOperator
from datetime import datetime


def extract_orders():
    # writes to: raw.orders
    pass


with DAG(
    dag_id="orders_ingest",
    schedule="0 3 * * *",
    start_date=datetime(2024, 1, 1),
    catchup=False,
) as dag:
    extract = PythonOperator(
        task_id="extract",
        python_callable=extract_orders,
    )
