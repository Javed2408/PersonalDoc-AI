"""Embedding service: input validation and loading (fast), plus the real model (marked `model`)."""

import math

import pytest

from app.retrieval.embeddings import EmbeddingError, SentenceTransformerEmbedder, validate_texts


def norm(vector):
    return math.sqrt(sum(value * value for value in vector))


def cosine(a, b):
    return sum(x * y for x, y in zip(a, b)) / (norm(a) * norm(b))


# --- Lightweight unit tests (no model) ---------------------------------------


def test_construction_does_not_load_the_model():
    embedder = SentenceTransformerEmbedder("some/model")

    assert embedder.model_name == "some/model"
    assert embedder._model is None


def test_empty_input_returns_empty_list_without_loading_model():
    embedder = SentenceTransformerEmbedder("some/model")

    assert embedder.embed([]) == []
    assert embedder._model is None


@pytest.mark.parametrize(
    ("texts", "message"),
    [
        ("just a string", "sequence of strings"),
        (["fine", ""], "Item 1 is empty"),
        (["fine", "   \n"], "Item 1 is empty"),
        (["fine", None], "Item 1 is NoneType"),
        ([42], "Item 0 is int"),
    ],
)
def test_invalid_input_is_rejected(texts, message):
    with pytest.raises(ValueError, match=message):
        validate_texts(texts)
    with pytest.raises(ValueError, match=message):
        SentenceTransformerEmbedder("some/model").embed(texts)


def test_model_load_failure_is_readable_and_retried(monkeypatch):
    import sentence_transformers

    attempts = []

    def broken(*args, **kwargs):
        attempts.append(args)
        raise OSError("connection refused while downloading")

    monkeypatch.setattr(sentence_transformers, "SentenceTransformer", broken)
    embedder = SentenceTransformerEmbedder("some/model")

    for _ in range(2):
        with pytest.raises(EmbeddingError, match="embedding model could not be loaded"):
            embedder.embed(["hello"])
    assert len(attempts) == 2  # A failed load isn't cached; the next document tries again.


# --- Real model -------------------------------------------------------------


@pytest.mark.model
def test_model_initializes_with_expected_dimension(real_embedder):
    assert real_embedder.model_name == "sentence-transformers/all-MiniLM-L6-v2"
    assert real_embedder.dimension == 384


@pytest.mark.model
def test_embeds_a_single_text(real_embedder):
    [vector] = real_embedder.embed(["PersonalDoc AI keeps documents on this machine."])

    assert len(vector) == 384
    assert all(isinstance(value, float) for value in vector)
    assert norm(vector) == pytest.approx(1.0, abs=1e-5)  # Normalised


@pytest.mark.model
def test_embeds_a_batch_with_one_vector_per_text(real_embedder):
    texts = [f"Chunk {n} describes local document processing." for n in range(70)]  # > batch size

    vectors = real_embedder.embed(texts)

    assert len(vectors) == 70
    assert {len(vector) for vector in vectors} == {384}


@pytest.mark.model
def test_embeddings_are_deterministic(real_embedder):
    text = "The quarterly report covers revenue and costs."

    first = real_embedder.embed([text])[0]
    again = real_embedder.embed([text])[0]
    in_batch = real_embedder.embed(["Something else entirely.", text])[1]

    assert first == again
    assert in_batch == pytest.approx(first, abs=1e-6)


@pytest.mark.model
def test_model_is_loaded_once(real_embedder):
    model = real_embedder._model
    real_embedder.embed(["one"])
    real_embedder.embed(["two", "three"])

    assert real_embedder._model is model


@pytest.mark.model
def test_embeddings_capture_meaning(real_embedder):
    cat, kitten, invoice = real_embedder.embed([
        "A cat is sleeping on the sofa.",
        "A kitten naps on the couch.",
        "The invoice is due at the end of the month.",
    ])

    assert cosine(cat, kitten) > cosine(cat, invoice) + 0.3
