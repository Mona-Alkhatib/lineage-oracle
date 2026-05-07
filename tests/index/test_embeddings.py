from unittest.mock import MagicMock

from oracle.index.embeddings import embed_texts


def test_embed_texts_calls_voyage_client():
    fake_client = MagicMock()
    fake_client.embed.return_value = MagicMock(embeddings=[[0.1, 0.2], [0.3, 0.4]])

    result = embed_texts(["hello", "world"], client=fake_client, model="voyage-3")

    fake_client.embed.assert_called_once_with(
        texts=["hello", "world"],
        model="voyage-3",
        input_type="document",
    )
    assert result == [[0.1, 0.2], [0.3, 0.4]]


def test_embed_texts_passes_input_type_for_query():
    fake_client = MagicMock()
    fake_client.embed.return_value = MagicMock(embeddings=[[0.1]])

    embed_texts(["q"], client=fake_client, model="voyage-3", input_type="query")

    args = fake_client.embed.call_args.kwargs
    assert args["input_type"] == "query"
