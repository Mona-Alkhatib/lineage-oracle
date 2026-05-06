"""Run jaffle_shop's seeds + dbt build to produce the demo warehouse.

This is a one-time setup script. Run it manually:
    cd data/jaffle_shop/dbt_project && dbt seed && dbt run && dbt parse
The resulting jaffle_shop.duckdb is git-ignored.
"""
import subprocess
from pathlib import Path

PROJECT = Path(__file__).parent / "dbt_project"


def main():
    subprocess.run(["dbt", "seed", "--profiles-dir", str(PROJECT)], cwd=PROJECT, check=True)
    subprocess.run(["dbt", "run", "--profiles-dir", str(PROJECT)], cwd=PROJECT, check=True)


if __name__ == "__main__":
    main()
