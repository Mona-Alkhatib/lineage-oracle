"""search_artifacts tool: vector search over the embeddings index."""
from __future__ import annotations

from typing import Any, Callable


def search_artifacts(
    query: str,
    k: int,
    store: Any,
    embed_fn: Callable[..., list[list[float]]],
) -> list[dict[str, Any]]:
    [vector] = embed_fn([query], input_type="query")
    return store.search(vector, k=k)
