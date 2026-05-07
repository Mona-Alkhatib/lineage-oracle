"""find_references tool: grep across .sql and .py files for a column or table reference.

Plain text search is sufficient for v1. We could parse SQL ASTs in v2 to
distinguish a column reference from a substring match.
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any

EXTENSIONS = {".sql", ".py"}


def find_references(
    needle: str,
    *,
    search_dirs: list[Path],
) -> list[dict[str, Any]]:
    pattern = re.compile(rf"\b{re.escape(needle)}\b")
    hits: list[dict[str, Any]] = []
    for root in search_dirs:
        for path in Path(root).rglob("*"):
            if path.suffix not in EXTENSIONS or not path.is_file():
                continue
            for lineno, line in enumerate(path.read_text().splitlines(), start=1):
                if pattern.search(line):
                    hits.append(
                        {
                            "file": str(path),
                            "line": lineno,
                            "snippet": line.strip(),
                        }
                    )
    return hits
