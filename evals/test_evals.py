"""Eval harness: runs each question through the live agent and asserts metrics.

Skipped automatically when API keys are not set so unit-test runs don't pay
for API calls.
"""
from __future__ import annotations

import os

import pytest

from evals.conftest import load_eval_set

EVAL_SET = load_eval_set()
HAS_KEYS = bool(os.environ.get("ANTHROPIC_API_KEY")) and bool(os.environ.get("VOYAGE_API_KEY"))


@pytest.mark.skipif(not HAS_KEYS, reason="API keys not configured")
@pytest.mark.parametrize("case", EVAL_SET, ids=[c["id"] for c in EVAL_SET])
def test_eval_case(case, agent):
    answer = agent.ask(case["question"]).lower()

    # Fact recall: every expected fact appears in the answer.
    missing = [f for f in case["expected_facts"] if f.lower() not in answer]
    assert not missing, f"missing expected facts: {missing}\nanswer: {answer}"

    # Must-cite paths appear verbatim in the answer.
    for cite in case["must_cite"]:
        assert cite.lower() in answer, f"missing required citation: {cite}\nanswer: {answer}"
