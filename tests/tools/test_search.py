from unittest.mock import MagicMock

from oracle.tools.search import search_artifacts


def test_search_artifacts_returns_top_k():
    store = MagicMock()
    store.search.return_value = [
        {"id": "model:a", "text": "alpha", "distance": 0.1},
        {"id": "model:b", "text": "beta", "distance": 0.2},
    ]
    embed = MagicMock(return_value=[[0.5, 0.5]])

    result = search_artifacts(
        query="alpha thing",
        k=2,
        store=store,
        embed_fn=embed,
    )

    assert len(result) == 2
    assert result[0]["id"] == "model:a"
    embed.assert_called_once_with(["alpha thing"], input_type="query")
