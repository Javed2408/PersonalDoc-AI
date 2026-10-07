"""Retrieval end to end with the real embedding model: PDF -> ... -> ChromaDB -> top-k."""

import pytest
from chromadb.api.shared_system_client import SharedSystemClient

from tests.conftest import upload, wait_for_processing
from tests.pdf_factory import build_pdf
from tests.test_indexing_e2e import CountingEmbedder

pytestmark = pytest.mark.model

ML_TEXT = [
    "Machine learning models learn patterns from training data. The more varied the examples, the better the model generalises.",
    "Evaluation uses a held-out test set to estimate accuracy on unseen examples.",
]
COOKING_TEXT = [
    "To make pizza dough, mix flour, water, yeast and salt, then knead for ten minutes.",
    "Bake the pizza on a hot stone at the highest oven temperature for about eight minutes.",
]
NETWORK_TEXT = [
    "A router forwards packets between networks using routing tables.",
    "Firewalls filter incoming connections according to security rules.",
]


@pytest.fixture
def indexed(make_client, real_embedder):
    counting = CountingEmbedder(real_embedder)
    client = make_client(embedder_override=counting)
    ids = {
        name: upload(client, filename=f"{name}.pdf", content=build_pdf(pages)).json()["document_id"]
        for name, pages in (("ml", ML_TEXT), ("cooking", COOKING_TEXT), ("network", NETWORK_TEXT))
    }
    wait_for_processing(client)
    return client, ids, counting


def search(client, query, **body):
    response = client.post("/api/retrieval/search", json={"query": query, **body})
    assert response.status_code == 200, response.text
    return response.json()["results"]


def test_expected_chunk_ranks_first(indexed):
    client, ids, _ = indexed

    found = search(client, "What do machine learning models learn from?")

    assert (found[0]["document_id"], found[0]["page_number"]) == (ids["ml"], 1)
    assert found[0]["text"].startswith("Machine learning models learn patterns")


@pytest.mark.parametrize(
    ("query", "topic", "page"),
    [
        ("How long should I knead pizza dough?", "cooking", 1),
        ("At what temperature should pizza be baked?", "cooking", 2),
        ("What device forwards packets between networks?", "network", 1),
        ("How are incoming connections blocked?", "network", 2),
        ("How is a model's accuracy estimated?", "ml", 2),
    ],
)
def test_each_question_finds_its_page(indexed, query, topic, page):
    client, ids, _ = indexed

    found = search(client, query, k=6)

    assert (found[0]["document_id"], found[0]["page_number"]) == (ids[topic], page)
    # Relative ranking: the right chunk is clearly closer than anything from other topics.
    other_topics = [r["distance"] for r in found if r["document_id"] != ids[topic]]
    assert found[0]["distance"] < min(other_topics)


def test_filter_keeps_results_inside_selected_documents(indexed):
    client, ids, _ = indexed

    found = search(client, "What do machine learning models learn from?", k=4, document_ids=[ids["cooking"]])

    assert {r["document_id"] for r in found} == {ids["cooking"]}
    assert len(found) == 2


def test_unrelated_question_matches_poorly(indexed):
    client, _, _ = indexed

    related = search(client, "What do machine learning models learn from?", k=1)[0]["distance"]
    unrelated = search(client, "Who painted the Mona Lisa?", k=1)[0]["distance"]

    assert unrelated > related + 0.3


def test_retrieval_after_restart_reuses_stored_vectors(indexed, make_client):
    client, ids, counting = indexed
    query = "How long should I knead pizza dough?"
    before = search(client, query, k=6)

    SharedSystemClient.clear_system_cache()  # Reconnect to ChromaDB from scratch
    restarted = make_client(embedder_override=counting)
    wait_for_processing(restarted)
    embedded_before = counting.texts
    after = search(restarted, query, k=6)

    assert [r["chunk_id"] for r in after] == [r["chunk_id"] for r in before]
    assert [r["distance"] for r in after] == pytest.approx([r["distance"] for r in before], abs=1e-6)
    assert counting.texts == embedded_before + 1  # Only the question was embedded
