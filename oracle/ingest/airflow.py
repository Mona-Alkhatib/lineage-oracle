"""Static AST parser for Airflow DAG files.

We never import these files. We parse them with `ast` and pull out:
- The DAG id and schedule (from the DAG(...) constructor call).
- The set of task_ids (from operator constructor calls).
- The set of tables a DAG writes to, declared via `# writes to: <table>` comments.

Reading-from-tables is harder to extract statically (it depends on operator
internals), so we leave it for v2. The comment convention is explicit and
sufficient for v1.
"""
from __future__ import annotations

import ast
import re
from dataclasses import dataclass, field
from pathlib import Path

WRITES_RE = re.compile(r"#\s*writes to:\s*([\w\.]+)")


@dataclass
class Task:
    task_id: str


@dataclass
class AirflowDag:
    dag_id: str
    schedule: str
    file_path: Path
    tasks: list[Task] = field(default_factory=list)
    writes: list[str] = field(default_factory=list)


def _kw(call: ast.Call, name: str) -> ast.expr | None:
    for kw in call.keywords:
        if kw.arg == name:
            return kw.value
    return None


def _str(node: ast.expr | None) -> str:
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    return ""


def parse_dag_file(path: Path) -> AirflowDag:
    source = Path(path).read_text()
    tree = ast.parse(source)

    dag_id = ""
    schedule = ""
    task_ids: list[Task] = []

    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        name = func.attr if isinstance(func, ast.Attribute) else getattr(func, "id", "")
        if name == "DAG":
            dag_id = _str(_kw(node, "dag_id"))
            schedule = _str(_kw(node, "schedule"))
        elif name.endswith("Operator"):
            tid = _str(_kw(node, "task_id"))
            if tid:
                task_ids.append(Task(task_id=tid))

    writes = WRITES_RE.findall(source)

    return AirflowDag(
        dag_id=dag_id,
        schedule=schedule,
        file_path=Path(path),
        tasks=task_ids,
        writes=writes,
    )
