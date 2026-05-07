"""Wrapper over Voyage AI's embeddings client.

Indexing uses input_type="document"; querying uses input_type="query".
Voyage tunes embeddings differently for each so passing the right one
matters for retrieval quality.
"""
from __future__ import annotations

from typing import Any, Literal

InputType = Literal["document", "query"]


def embed_texts(
    texts: list[str],
    *,
    client: Any,
    model: str = "voyage-3",
    input_type: InputType = "document",
) -> list[list[float]]:
    response = client.embed(texts=texts, model=model, input_type=input_type)
    return list(response.embeddings)
