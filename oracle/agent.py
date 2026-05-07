"""Claude tool-use agent loop.

Stays small on purpose: one class, one method. The agent receives a
question, calls the model in a loop, runs whatever tool the model asks
for, and stops when the model returns end_turn (or the cap is hit).
"""
from __future__ import annotations

from typing import Any, Callable

from oracle.tools.definitions import TOOL_DEFINITIONS

SYSTEM_PROMPT = """You answer questions about a data warehouse.

You have four tools. Decide which to call based on the question:
- search_artifacts: find an artifact by description (use when name is unknown)
- get_lineage: trace upstream or downstream from a known node
- get_schema: read a table's columns and row count
- find_references: find code that references a column or table

Rules:
- Always cite the file path or DAG name behind each claim.
- Never invent table or column names. If unsure, call search_artifacts first.
- If you cannot answer with grounded evidence, say so.
"""


class Agent:
    def __init__(
        self,
        *,
        client: Any,
        tool_runner: Callable[[str, dict], Any],
        model: str = "claude-sonnet-4-6",
        max_tool_calls: int = 6,
    ) -> None:
        self.client = client
        self.tool_runner = tool_runner
        self.model = model
        self.max_tool_calls = max_tool_calls

    def ask(self, question: str) -> str:
        messages: list[dict[str, Any]] = [{"role": "user", "content": question}]

        for _ in range(self.max_tool_calls + 1):
            response = self.client.messages.create(
                model=self.model,
                max_tokens=2048,
                system=SYSTEM_PROMPT,
                tools=TOOL_DEFINITIONS,
                messages=messages,
            )

            if response.stop_reason == "end_turn":
                return _extract_text(response)

            if response.stop_reason == "tool_use":
                messages.append({"role": "assistant", "content": response.content})
                tool_results = []
                for block in response.content:
                    if getattr(block, "type", None) != "tool_use":
                        continue
                    output = self.tool_runner(block.name, dict(block.input))
                    tool_results.append(
                        {
                            "type": "tool_result",
                            "tool_use_id": block.id,
                            "content": str(output),
                        }
                    )
                messages.append({"role": "user", "content": tool_results})
                continue

            return _extract_text(response)

        return "I couldn't answer this confidently within the tool-call budget."


def _extract_text(response: Any) -> str:
    parts = [b.text for b in response.content if getattr(b, "type", None) == "text"]
    return "".join(parts) or "(no response)"
