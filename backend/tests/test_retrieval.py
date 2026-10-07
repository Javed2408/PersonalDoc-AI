"""Retrieval through the API, with the deterministic keyword embedder (TopicEmbedder).

Semantic ranking with the real model is covered in test_retrieval_e2e.py.
"""

import pytest
from chromadb.api.shared_system_client import SharedSystemClient

from app.models.schemas import Chunk
from app.retrieval.embeddings import EmbeddingError
from tests.conftest import upload, wait_for_processing
from tests.fakes import TopicEmbedder
from tests.pdf_factory import build_pdf
from tests.test_processing import CORRUPTED_PDF, add_record

ML_PAGES = [
    "Machine learning models learn patterns from training data.",
    "Gradient descent updates neural model weights during training.",
]
COOKING_PAGES = [
    "Knead the bread dough until the yeast and flour come together.",
    "Bake the bread in a hot oven and follow the recipe closely.",
]
NETWORK_PAGES = [
    "Routers forward packets using the TCP protocol.",
    "DNS lookups add latency; more bandwidth does not remove it.",
]

ML_QUERY = "How do machine learning models use training data?"
COOKING_QUERY = "How long should bread dough rise with yeast?"
NETWORK_QUERY = "How do routers forward packets?"
OFF_TOPIC_QUERY = "What is the capital of Australia?"


@pytest.fixture
def topic_embedder():
    return TopicEmbedder()


@pytest.fixture
def library(make_client, topic_embedder):
    """A client with three processed single-topic documents (2 pages / 2 chunks each)."""
    client = make_client(embedder_override=topic_embedder)
    ids = {
        name: upload(client, filename=f"{name}.pdf", content=build_pdf(pages)).json()["document_id"]
        for name, pages in (("ml", ML_PAGES), ("cooking", COOKING_PAGES), ("network", NETWORK_PAGES))
    }
    wait_for_processing(client)
    topic_embedder.calls.clear()
    return client, ids


def search(client, query, **body):
    return client.post("/api/retrieval/search", json={"query": query, **body})


def results(client, query, **body):
    response = search(client, query, **body)
    assert response.status_code == 200, response.text
    return response.json()["results"]


# --- Ranking ----------------------------------------------------------------


@pytest.mark.parametrize(
    ("query", "topic", "best_page"),
    [(ML_QUERY, "ml", 1), (COOKING_QUERY, "cooking", 1), (NETWORK_QUERY, "network", 1)],
)
def test_matching_topic_ranks_first(library, query, topic, best_page):
    client, ids = library

    found = results(client, query, k=6)

    assert (found[0]["document_id"], found[0]["page_number"]) == (ids[topic], best_page)
    # Both chunks of the matching document rank above every unrelated chunk.
    assert {r["document_id"] for r in found[:2]} == {ids[topic]}
    assert all(r["distance"] < other["distance"] for r in found[:2] for other in found[2:])


def test_results_are_ordered_by_distance_with_consistent_scores(library):
    client, _ = library

    found = results(client, ML_QUERY, k=6)

    assert [r["rank"] for r in found] == [1, 2, 3, 4, 5, 6]
    distances = [r["distance"] for r in found]
    assert distances == sorted(distances)  # Lower distance = more similar = earlier
    for r in found:
        assert r["similarity"] == pytest.approx(1 - r["distance"], abs=1e-12)
        assert 0 <= r["distance"] <= 2


def test_off_topic_query_is_far_from_everything(library):
    client, _ = library

    on_topic = results(client, ML_QUERY, k=1)[0]["distance"]
    off_topic = results(client, OFF_TOPIC_QUERY, k=4)

    # Plain top-k still returns the nearest chunks (no threshold by default),
    # but their distances show they are unrelated.
    assert len(off_topic) == 4
    assert min(r["distance"] for r in off_topic) > on_topic + 0.5


def test_optional_distance_threshold_drops_unrelated_chunks(make_client, topic_embedder):
    client = make_client(embedder_override=topic_embedder, retrieval_max_distance=0.5)
    upload(client, content=build_pdf(ML_PAGES))
    wait_for_processing(client)

    assert results(client, OFF_TOPIC_QUERY) == []
    found = results(client, ML_QUERY)
    assert [r["page_number"] for r in found] == [1]  # Page 2 shares only "training": too far
    assert all(r["distance"] <= 0.5 for r in found)


# --- Top-k ------------------------------------------------------------------


@pytest.mark.parametrize("k", [1, 2, 4])
def test_returns_exactly_k_results(library, k):
    client, _ = library

    response = search(client, ML_QUERY, k=k).json()

    assert response["k"] == k
    assert response["result_count"] == len(response["results"]) == k


def test_default_k_is_four(library):
    client, _ = library

    response = search(client, ML_QUERY).json()

    assert response["k"] == 4
    assert response["result_count"] == 4


def test_fewer_chunks_than_k_returns_what_exists(library):
    client, ids = library

    response = search(client, ML_QUERY, k=10, document_ids=[ids["ml"]]).json()

    assert response["result_count"] == 2  # Not padded to 10


def test_maximum_k_is_accepted(library):
    client, _ = library

    response = search(client, ML_QUERY, k=20).json()

    assert response["result_count"] == 6  # All chunks in the library


@pytest.mark.parametrize("k", [0, -1, 21, 1000, "four", 2.5])
def test_invalid_k_is_rejected(library, k):
    client, _ = library

    assert search(client, ML_QUERY, k=k).status_code == 422


@pytest.mark.parametrize("query", ["", "   ", "\n\t "])
def test_empty_or_whitespace_query_is_rejected(library, topic_embedder, query):
    client, _ = library

    assert search(client, query).status_code == 422
    assert topic_embedder.calls == []


def test_missing_or_oversized_query_is_rejected(library):
    client, _ = library

    assert client.post("/api/retrieval/search", json={"k": 2}).status_code == 422
    assert search(client, "x" * 2001).status_code == 422


def test_query_is_trimmed(library):
    client, _ = library

    assert search(client, f"   {ML_QUERY}  \n").json()["query"] == ML_QUERY


# --- Document filtering -----------------------------------------------------


def test_search_without_filter_covers_all_documents(library):
    client, ids = library

    response = search(client, ML_QUERY, k=6).json()

    assert response["document_ids"] is None
    assert {r["document_id"] for r in response["results"]} == set(ids.values())


def test_empty_filter_means_all_documents(library):
    client, ids = library

    response = search(client, ML_QUERY, k=6, document_ids=[]).json()

    assert response["document_ids"] is None
    assert response["result_count"] == 6


def test_filter_restricts_results_to_one_document(library):
    client, ids = library

    unfiltered = results(client, ML_QUERY, k=2)
    filtered = results(client, ML_QUERY, k=2, document_ids=[ids["cooking"]])

    assert {r["document_id"] for r in unfiltered} == {ids["ml"]}
    assert {r["document_id"] for r in filtered} == {ids["cooking"]}  # Filtering changed the answer set


def test_filter_with_multiple_documents(library):
    client, ids = library

    found = results(client, NETWORK_QUERY, k=6, document_ids=[ids["cooking"], ids["network"]])

    assert {r["document_id"] for r in found} == {ids["cooking"], ids["network"]}
    assert found[0]["document_id"] == ids["network"]
    assert len(found) == 4


def test_duplicate_ids_in_filter_are_collapsed(library):
    client, ids = library

    response = search(client, ML_QUERY, document_ids=[ids["ml"], ids["ml"]]).json()

    assert response["document_ids"] == [ids["ml"]]
    assert response["result_count"] == 2


def test_filter_to_document_without_matching_content_stays_restricted(library):
    client, ids = library

    found = results(client, ML_QUERY, k=4, document_ids=[ids["network"]])

    # Nothing about machine learning there: we get that document's chunks, never others.
    assert {r["document_id"] for r in found} == {ids["network"]}
    assert len(found) == 2
    assert min(r["distance"] for r in found) > 0.5


def test_unknown_document_id_is_a_clear_error(library):
    client, ids = library
    unknown = "f" * 32

    response = search(client, ML_QUERY, document_ids=[ids["ml"], unknown])

    assert response.status_code == 404
    assert response.json() == {"detail": f"Unknown document ID(s): {unknown}."}


@pytest.mark.parametrize("bad_id", ["../documents.json", "ABC", "not-a-uuid", "", "f" * 33])
def test_malformed_document_id_is_rejected(library, bad_id):
    client, _ = library

    assert search(client, ML_QUERY, document_ids=[bad_id]).status_code == 422


def test_unprocessed_documents_cannot_be_targeted(library):
    client, ids = library
    failed = upload(client, filename="broken.pdf", content=CORRUPTED_PDF).json()
    wait_for_processing(client)

    response = search(client, ML_QUERY, document_ids=[ids["ml"], failed["document_id"]])

    assert response.status_code == 409
    assert response.json() == {"detail": "These documents are not processed, so they can't be searched: broken.pdf (failed)."}


def test_documents_still_being_processed_are_never_returned(library, settings):
    client, ids = library
    # Simulate a document mid-indexing: some vectors stored, status still "processing".
    pending_id = "e" * 32
    add_record(settings, pending_id, status="processing", content=None)
    chunk = Chunk(
        chunk_id=f"{pending_id}-00000", document_id=pending_id, original_filename="pending.pdf",
        page_number=1, chunk_index=0, start_char=0, char_count=20, text="machine learning models training data",
    )
    client.app.state.vector_store.upsert_chunks([chunk], [TopicEmbedder().vector(chunk.text)])

    found = results(client, ML_QUERY, k=20)

    assert pending_id not in {r["document_id"] for r in found}


def test_deleted_documents_are_no_longer_retrievable(library):
    client, ids = library

    assert client.delete(f"/api/documents/{ids['ml']}").status_code == 200

    found = results(client, ML_QUERY, k=20)
    assert ids["ml"] not in {r["document_id"] for r in found}
    assert len(found) == 4


def test_empty_library_returns_no_results_without_embedding(client, embedder):
    response = search(client, ML_QUERY).json()

    assert response["results"] == []
    assert response["result_count"] == 0
    assert embedder.calls == []


# --- Metadata ---------------------------------------------------------------


def test_results_carry_full_chunk_metadata(library):
    client, ids = library
    chunks = {
        chunk["chunk_id"]: chunk
        for doc_id in ids.values()
        for chunk in client.get(f"/api/documents/{doc_id}/chunks").json()["chunks"]
    }

    found = results(client, COOKING_QUERY, k=6)

    for result in found:
        chunk = chunks[result["chunk_id"]]
        for field in ("chunk_id", "document_id", "original_filename", "page_number",
                      "chunk_index", "start_char", "char_count", "text"):
            assert result[field] == chunk[field], field
    assert set(found[0]) == {
        "rank", "chunk_id", "document_id", "original_filename", "page_number", "chunk_index",
        "start_char", "char_count", "text", "distance", "similarity",
    }


def test_results_expose_no_storage_details(library):
    client, _ = library

    body = search(client, ML_QUERY).text

    for leak in ("stored_filename", "data/documents", "data\\\\documents", ".json", "chroma"):
        assert leak not in body


def test_duplicate_filenames_are_distinguished_by_document_id(make_client, topic_embedder):
    client = make_client(embedder_override=topic_embedder)
    first = upload(client, filename="notes.pdf", content=build_pdf(ML_PAGES[:1])).json()["document_id"]
    second = upload(client, filename="notes.pdf", content=build_pdf(COOKING_PAGES[:1])).json()["document_id"]
    wait_for_processing(client)

    found = results(client, ML_QUERY, k=2)

    assert [r["document_id"] for r in found] == [first, second]
    assert {r["original_filename"] for r in found} == {"notes.pdf"}


# --- Efficiency and failures --------------------------------------------------


def test_equally_distant_chunks_have_a_stable_order(library):
    client, _ = library

    found = results(client, COOKING_QUERY, k=6)

    # Two off-topic chunks (each sharing one keyword-free profile with the query) tie
    # exactly on distance; ties must come back sorted by chunk_id.
    groups = {}
    for r in found:
        groups.setdefault(r["distance"], []).append(r["chunk_id"])
    tied_groups = [ids for ids in groups.values() if len(ids) > 1]
    assert tied_groups
    assert all(ids == sorted(ids) for ids in tied_groups)


def test_one_embedding_and_one_vector_query_per_search(library, topic_embedder, monkeypatch):
    client, _ = library
    store = client.app.state.vector_store
    queries = []
    real_query = store.query_nearest
    monkeypatch.setattr(store, "query_nearest", lambda *a, **kw: queries.append(1) or real_query(*a, **kw))

    results(client, ML_QUERY, k=4)

    assert topic_embedder.calls == [[ML_QUERY]]
    assert len(queries) == 1


def test_embedding_failure_returns_503(library, topic_embedder, monkeypatch):
    client, _ = library

    def broken(texts):
        raise EmbeddingError("model gone")

    monkeypatch.setattr(topic_embedder, "embed", broken)
    response = search(client, ML_QUERY)

    assert response.status_code == 503
    assert response.json() == {"detail": "The embedding model is unavailable. Check the backend logs."}


def test_query_text_is_not_logged_at_info_level(library, caplog):
    client, _ = library
    secret_query = "machine learning salary of Jane Doe"

    with caplog.at_level("INFO", logger="app.retrieval.retriever"):
        results(client, secret_query)

    assert "Retrieval: k=4, filter=all, results=4" in caplog.text
    assert "Jane Doe" not in caplog.text


# --- Persistence --------------------------------------------------------------


def test_retrieval_survives_restart_without_reembedding(library, make_client, topic_embedder):
    client, ids = library
    before = results(client, COOKING_QUERY, k=6)

    SharedSystemClient.clear_system_cache()  # Drop the in-process ChromaDB client
    restarted = make_client(embedder_override=topic_embedder)
    wait_for_processing(restarted)
    topic_embedder.calls.clear()
    after = results(restarted, COOKING_QUERY, k=6)

    assert after == before
    assert topic_embedder.calls == [[COOKING_QUERY]]  # Only the query was embedded


@pytest.mark.parametrize(("raw", "clamped"), [(-2.4e-7, 0.0), (0.3, 0.3), (2.0000001, 2.0)])
def test_float_rounding_is_clamped_to_valid_distance_range(raw, clamped):
    from app.retrieval.retriever import clamp_distance

    assert clamp_distance(raw) == clamped
