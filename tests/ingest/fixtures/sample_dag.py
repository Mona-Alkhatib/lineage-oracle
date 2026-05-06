"""Fixture: a toy DAG used for testing the AST parser."""
from airflow import DAG
from airflow.operators.python import PythonOperator
from datetime import datetime


def extract_users():
    # writes to: raw.users
    pass


with DAG(
    dag_id="users_ingest",
    schedule="0 2 * * *",
    start_date=datetime(2024, 1, 1),
) as dag:
    extract = PythonOperator(
        task_id="extract",
        python_callable=extract_users,
    )
