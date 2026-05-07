# Eval Harness

The eval harness is what turns Lineage Oracle from a *demo that produces plausible answers* into a *system that produces measurably correct ones*. It runs every question in `evals/eval_set.json` through the live agent and asserts on three metrics.

## Why evals matter for AI engineering

Building an LLM-backed system without evals is like building a database without tests. The model **looks** like it works because most outputs are plausible — but plausible isn't the same as correct, and you have no way to know whether a prompt change made things better or worse.

For Lineage Oracle specifically, the failure modes that evals catch are:

- **Hallucinated table or column names** — the model invents `fct_user_revenue` when no such table exists.
- **Missing facts** — the answer is grammatical but skips an upstream model that the user needed to see.
- **Lost citations** — the model gives the right answer but doesn't say where it came from.
- **Tool misuse** — the model ignores `get_lineage` for a lineage question and tries to answer from memory.

A regression in any of these is silent without evals. With evals, it shows up as a failed pytest case in CI.

## Format

Each case in `evals/eval_set.json` is a JSON object:

```json
{
  "id": "lineage_001",
  "category": "lineage",
  "question": "What feeds fct_orders?",
  "expected_facts": ["stg_orders"],
  "must_cite": ["stg_orders.sql"],
  "must_not_invent": true
}
```

Fields:

| Field | Meaning |
|---|---|
| `id` | Stable identifier (used as the pytest case name) |
| `category` | One of `lineage` / `impact` / `schema` / `semantic` — for grouped reporting |
| `question` | Natural-language input fed to `agent.ask()` |
| `expected_facts` | Substrings every correct answer must contain (e.g. an upstream model name) |
| `must_cite` | Substrings that must appear verbatim — typically file paths |
| `must_not_invent` | If true, the answer must not mention any table or column that doesn't exist in the warehouse |

The set is intentionally small (10 cases for v1) and grows as we discover new failure modes. Each new failure becomes a new case.

## The three metrics

### 1. Fact recall

> *Of the facts the answer should contain, how many actually appear?*

```
recall = matched_expected_facts / total_expected_facts
```

Initial threshold: **≥ 0.85**. A drop here means the agent is missing real upstream/downstream artifacts — usually a sign of a retrieval gap or a too-shallow `get_lineage` depth.

### 2. Citation precision

> *Of the citations the answer makes, how many resolve to real files?*

```
precision = real_paths_in_answer / total_paths_in_answer
```

Initial threshold: **1.00**. Anything less means the agent is fabricating file paths — a hard correctness failure.

### 3. No-invention rate

> *Across all cases, how many answers stayed inside the real schema?*

```
no_invention = answers_with_zero_inventions / total_answers
```

Initial threshold: **1.00**. Inventing table or column names is the single worst failure mode for a lineage tool — every answer becomes untrustworthy.

## How to run

The harness is plain pytest:

```bash
uv run pytest evals/ -v
```

It auto-skips when `ANTHROPIC_API_KEY` or `VOYAGE_API_KEY` are missing in the environment, so unit-test runs in CI don't burn money.

To run a single case:

```bash
uv run pytest evals/test_evals.py -v -k lineage_001
```

To run only one category:

```bash
uv run pytest evals/test_evals.py -v -k semantic
```

## Sample output

```
evals/test_evals.py::test_eval_case[lineage_001] PASSED
evals/test_evals.py::test_eval_case[lineage_002] PASSED
evals/test_evals.py::test_eval_case[lineage_003] PASSED
evals/test_evals.py::test_eval_case[impact_001]  PASSED
evals/test_evals.py::test_eval_case[impact_002]  FAILED
  AssertionError: missing expected facts: ['fct_orders']
  answer: stg_orders is referenced by several models...
evals/test_evals.py::test_eval_case[schema_001]  PASSED
...

7 passed, 1 failed
```

A failure shows the missing/invented facts and the actual answer, so debugging usually reduces to: was the question malformed, was the prompt under-specified, was retrieval insufficient, or did the agent loop terminate too early?

## Where it fits in the workflow

Evals run on three moments:

1. **Local development** — when changing the system prompt, tools, or retrieval logic, rerun before committing.
2. **CI** — fail the build if any threshold drops. (Not yet wired up; v2.)
3. **After model upgrades** — when bumping Claude versions, evals are how you know the new model didn't regress.

## What's intentionally simple

- **No LLM-as-judge.** v1 uses substring matching because the questions are factual ("what feeds X?") and the ground truth is a finite set of artifact names. LLM-judging is reserved for cases where the answer is open-ended.
- **No automatic eval-set generation.** The set is hand-curated. As the system grows, automated case generation from the warehouse + manifest becomes worth building.
- **No latency / cost tracking.** Worth adding — the runner could log tokens and wall time per case to detect slow drift.

## Future work

- Expand the seed set from 10 to 30+ cases, with deliberate adversarial cases (questions referencing nonexistent tables, ambiguous names, multi-hop lineage).
- Add latency and token-cost assertions per case.
- Track eval scores in a JSON history file so we can plot accuracy over time.
- Wire up CI to run the full eval suite on every push to `main`.
