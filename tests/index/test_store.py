from oracle.index.store import VectorStore


def test_save_and_search_returns_nearest(tmp_path):
    store = VectorStore(path=tmp_path / "v.duckdb", dim=2)
    store.upsert(
        [
            {"id": "model:a", "text": "alpha", "vector": [1.0, 0.0]},
            {"id": "model:b", "text": "beta", "vector": [0.0, 1.0]},
            {"id": "model:c", "text": "gamma", "vector": [1.0, 1.0]},
        ]
    )

    hits = store.search([1.0, 0.05], k=2)
    assert hits[0]["id"] == "model:a"
    assert {h["id"] for h in hits} == {"model:a", "model:c"}


def test_count_after_upsert(tmp_path):
    store = VectorStore(path=tmp_path / "v.duckdb", dim=2)
    store.upsert([{"id": "x", "text": "x", "vector": [1.0, 0.0]}])
    assert store.count() == 1
