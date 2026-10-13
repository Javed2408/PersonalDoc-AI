"""Retrying failed documents: POST /api/documents/{document_id}/reindex."""

import threading
from types import SimpleNamespace

import pytest

import app.services.processing_service as processing_service
from app.ingestion.loader import ExtractionError
from app.models.schemas import Chunk
from app.retrieval.embeddings import EmbeddingError
from app.retrieval.vector_store import VectorStoreError
from app.services.chunk_store import ChunkStoreError
from app.services.document_store import JsonDocumentStore
from tests.conftest import get_document, upload, upload_fields, wait_for_processing
from tests.test_processing import CORRUPTED_PDF, QUALITY_PDF, add_record, upload_and_process
from tests.test_vector_indexing import LONG_PDF, vector_store

EMBEDDING_DOWN = "The embedding model could not be loaded. Check the backend logs."
ALREADY_PROCESSING = {"detail": "This document is already being processed."}


def reindex(client, document_id):
    return client.post(f"/api/documents/{document_id}/reindex")


def failed_document(client, embedder, content=QUALITY_PDF):
    """A document that failed because the embedding model was unavailable, a cause that can be fixed."""
    embedder.fail_with = EMBEDDING_DOWN
    document = upload_and_process(client, content=content)
    embedder.fail_with = None
    assert document["status"] == "failed"
    return document


def chunk_file(settings, document_id):
    return settings.chunks_dir / f"{document_id}.json"


def assert_nothing_left(client, settings, document_id):
    assert all(doc["document_id"] != document_id for doc in client.get("/api/documents").json()["documents"])
    assert not chunk_file(settings, document_id).exists()
    assert not (settings.documents_dir / f"{document_id}.pdf").exists()
    assert vector_store(client).count_document(document_id) == 0


@pytest.fixture
def hold_worker(client, monkeypatch):
    """hold() keeps the worker inside extraction until the gate is released, so documents
    stay queued or processing. Depends on `client` so the gates open before the app shuts down."""
    gates = []

    def hold():
        gate = SimpleNamespace(started=threading.Event(), release=threading.Event(), calls=[])
        real_process_pdf = processing_service.process_pdf

        def held(path, document_id, *args, **kwargs):
            gate.calls.append(document_id)
            gate.started.set()
            gate.release.wait(timeout=10)
            return real_process_pdf(path, document_id, *args, **kwargs)

        monkeypatch.setattr(processing_service, "process_pdf", held)
        gates.append(gate)
        return gate

    yield hold
    for gate in gates:
        gate.release.set()


# --- Accepted retries -------------------------------------------------------


def test_failed_document_is_accepted_and_keeps_its_identity(client, embedder):
    document = failed_document(client, embedder)

    response = reindex(client, document["document_id"])

    assert response.status_code == 202
    body = response.json()
    assert upload_fields(body) == upload_fields(document)  # Same ID, stored file, name and upload time
    assert body["status"] == "processing"
    assert body["processing_error"] is None
    assert set(body) == set(document)  # The usual document schema


def test_failed_document_reaches_processed_once_the_cause_is_fixed(client, embedder):
    document = failed_document(client, embedder)
    document_id = document["document_id"]

    assert reindex(client, document_id).status_code == 202
    wait_for_processing(client)

    retried = get_document(client, document_id)
    assert retried["status"] == "processed"
    assert upload_fields(retried) == upload_fields(document)
    assert (retried["page_count"], retried["chunk_count"], retried["processing_error"]) == (2, 2, None)
    assert len(client.get("/api/documents").json()["documents"]) == 1  # No second document
    assert vector_store(client).count_document(document_id) == 2
    chunks = client.get(f"/api/documents/{document_id}/chunks").json()["chunks"]
    assert [c["chunk_id"] for c in chunks] == [f"{document_id}-00000", f"{document_id}-00001"]

    search = client.post("/api/retrieval/search", json={"query": "extraction test", "document_ids": [document_id]})
    assert search.status_code == 200
    assert search.json()["result_count"] == 2  # Searchable again


def test_retry_replaces_leftover_vectors_without_duplicates(client, embedder):
    document = failed_document(client, embedder)
    document_id = document["document_id"]
    # As if removing a failed attempt's partial vectors had failed too: one outdated, one obsolete.
    leftovers = [
        Chunk(chunk_id=f"{document_id}-{index:05d}", document_id=document_id, original_filename="quality.pdf",
              page_number=1, chunk_index=index, start_char=0, char_count=len(text), text=text)
        for index, text in ((0, "outdated text"), (99, "obsolete text"))
    ]
    store = vector_store(client)
    store.upsert_chunks(leftovers, [embedder.vector(chunk.text) for chunk in leftovers])

    assert reindex(client, document_id).status_code == 202
    wait_for_processing(client)

    chunks = client.get(f"/api/documents/{document_id}/chunks").json()["chunks"]
    records = store.get_document_records(document_id)
    assert sorted(records) == [c["chunk_id"] for c in chunks]
    assert [records[c["chunk_id"]][0] for c in chunks] == [c["text"] for c in chunks]
    assert store.stats()["vector_count"] == len(chunks) == 2


# --- Rejected requests ------------------------------------------------------


@pytest.mark.parametrize("document_id", [
    "123", "0" * 31, "0" * 33, "A" * 32, "g" * 32, "0123456789abcdef0123456789abcde-", "not-an-id",
])
def test_malformed_id_is_rejected(client, embedder, document_id):
    document = failed_document(client, embedder)

    assert reindex(client, document_id).status_code == 422
    assert get_document(client, document["document_id"])["status"] == "failed"  # Untouched


def test_unknown_document_is_not_found(client):
    response = reindex(client, "0123456789abcdef0123456789abcdef")

    assert response.status_code == 404
    assert response.json() == {"detail": "Document not found. It may have been deleted."}


def test_queued_or_processing_document_conflicts(client, hold_worker):
    gate = hold_worker()
    first = upload(client, content=QUALITY_PDF).json()
    assert gate.started.wait(timeout=5)
    second = upload(client, content=QUALITY_PDF).json()  # Queued behind the first

    for document, status in ((first, "processing"), (second, "uploaded")):
        assert get_document(client, document["document_id"])["status"] == status
        response = reindex(client, document["document_id"])
        assert response.status_code == 409
        assert response.json() == ALREADY_PROCESSING

    gate.release.set()
    wait_for_processing(client)
    assert gate.calls == [first["document_id"], second["document_id"]]  # Nothing extra was queued
    assert get_document(client, second["document_id"])["status"] == "processed"


def test_processed_document_is_not_reprocessed(client, embedder):
    document = upload_and_process(client)
    embedded_before = len(embedder.embedded_texts)

    response = reindex(client, document["document_id"])

    assert response.status_code == 409
    assert response.json() == {
        "detail": "This document is already processed. Reprocessing a processed document "
                  "isn't supported in this version."
    }
    wait_for_processing(client)
    assert get_document(client, document["document_id"]) == document
    assert len(embedder.embedded_texts) == embedded_before
    assert vector_store(client).count_document(document["document_id"]) == 2


# --- Duplicate requests -----------------------------------------------------


def test_repeated_retries_queue_one_job(client, embedder, hold_worker):
    document = failed_document(client, embedder)
    gate = hold_worker()

    assert reindex(client, document["document_id"]).status_code == 202
    assert reindex(client, document["document_id"]).json() == ALREADY_PROCESSING  # Before the job starts
    assert gate.started.wait(timeout=5)
    assert reindex(client, document["document_id"]).status_code == 409  # While it runs

    gate.release.set()
    wait_for_processing(client)
    assert gate.calls == [document["document_id"]]
    assert get_document(client, document["document_id"])["status"] == "processed"


def test_simultaneous_retries_queue_exactly_one_job(client, embedder, hold_worker):
    document = failed_document(client, embedder)
    gate = hold_worker()
    barrier = threading.Barrier(8)
    codes = []

    def retry():
        barrier.wait(timeout=5)
        codes.append(reindex(client, document["document_id"]).status_code)

    threads = [threading.Thread(target=retry) for _ in range(8)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=10)

    assert sorted(codes) == [202] + [409] * 7
    gate.release.set()
    wait_for_processing(client)
    assert gate.calls == [document["document_id"]]
    assert vector_store(client).count_document(document["document_id"]) == 2


def test_status_switch_is_atomic_across_threads(settings):
    """The store primitive behind the guard: of many simultaneous switches, exactly one wins."""
    add_record(settings, "d" * 32, status="failed", content=QUALITY_PDF)
    store = JsonDocumentStore(settings.metadata_file)
    barrier = threading.Barrier(16)
    wins = []

    def switch():
        barrier.wait(timeout=5)
        _, changed = store.update_if_status("d" * 32, "failed", status="processing")
        wins.append(changed)

    threads = [threading.Thread(target=switch) for _ in range(16)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=10)

    assert sorted(wins) == [False] * 15 + [True]
    assert store.get("d" * 32).status == "processing"


# --- Retries that fail again ------------------------------------------------


def test_retry_that_fails_again_is_recorded_and_can_be_retried(client, embedder, settings):
    document = failed_document(client, embedder)
    document_id = document["document_id"]
    embedder.fail_with = EMBEDDING_DOWN

    assert reindex(client, document_id).status_code == 202
    wait_for_processing(client)

    again = get_document(client, document_id)
    assert (again["status"], again["processing_error"], again["chunk_count"]) == ("failed", EMBEDDING_DOWN, None)
    assert vector_store(client).count_document(document_id) == 0
    assert chunk_file(settings, document_id).exists()  # Valid chunks are kept, as after any embedding failure
    assert client.get(f"/api/documents/{document_id}/chunks").status_code == 409

    embedder.fail_with = None
    assert reindex(client, document_id).status_code == 202
    wait_for_processing(client)
    assert get_document(client, document_id)["status"] == "processed"


def test_retry_failing_midway_leaves_no_partial_vectors(client, embedder, monkeypatch):
    document = failed_document(client, embedder, content=LONG_PDF)
    store = vector_store(client)
    real_upsert = store.upsert_chunks
    calls = []

    def fail_second_batch(chunks, embeddings):
        calls.append(1)
        if len(calls) > 1:
            raise VectorStoreError("disk full")
        real_upsert(chunks, embeddings)

    monkeypatch.setattr(store, "upsert_chunks", fail_second_batch)
    client.app.state.document_processor._indexer._batch_size = 2

    assert reindex(client, document["document_id"]).status_code == 202
    wait_for_processing(client)

    again = get_document(client, document["document_id"])
    assert again["status"] == "failed"
    assert again["processing_error"] == "The document could not be saved to the vector index. Check the backend logs."
    assert len(calls) == 2  # The first batch was stored, then removed again
    assert store.stats()["vector_count"] == 0


def test_retry_of_an_unreadable_pdf_fails_the_same_way(client, embedder, settings):
    document = upload_and_process(client, content=CORRUPTED_PDF, filename="broken.pdf")
    assert document["status"] == "failed"

    assert reindex(client, document["document_id"]).status_code == 202
    wait_for_processing(client)

    again = get_document(client, document["document_id"])
    assert (again["status"], again["processing_error"]) == ("failed", document["processing_error"])
    assert upload_fields(again) == upload_fields(document)
    assert not chunk_file(settings, document["document_id"]).exists()
    assert embedder.calls == []


def test_retry_failure_is_recorded_even_if_its_chunks_cannot_be_removed(client, embedder, monkeypatch):
    """Otherwise the document would stay "processing" with no job behind it, and every retry would get 409."""
    document = failed_document(client, embedder)  # Only embedding failed, so its chunks were kept
    document_id = document["document_id"]
    unreadable = "The PDF could not be read. It may be corrupted."

    def fail_extraction(*args, **kwargs):
        raise ExtractionError(unreadable)

    def locked(doc_id):
        raise ChunkStoreError("Chunks could not be deleted")

    monkeypatch.setattr(processing_service, "process_pdf", fail_extraction)
    monkeypatch.setattr(client.app.state.document_processor._chunk_store, "delete", locked)

    assert reindex(client, document_id).status_code == 202
    wait_for_processing(client)

    again = get_document(client, document_id)
    assert (again["status"], again["processing_error"], again["chunk_count"]) == ("failed", unreadable, None)
    assert vector_store(client).count_document(document_id) == 0
    assert client.get(f"/api/documents/{document_id}/chunks").status_code == 409  # Leftover chunks never served

    monkeypatch.undo()
    assert reindex(client, document_id).status_code == 202  # Still recoverable
    wait_for_processing(client)
    assert get_document(client, document_id)["status"] == "processed"


# --- Restart ----------------------------------------------------------------


def test_accepted_retry_resumes_after_a_restart(make_client, embedder, monkeypatch):
    """An accepted retry is stored as "processing", which startup recovery queues again."""
    client = make_client()
    document = failed_document(client, embedder)
    monkeypatch.setattr(client.app.state.document_processor, "submit", lambda document_id: None)  # Never ran

    assert reindex(client, document["document_id"]).status_code == 202
    restarted = make_client()
    wait_for_processing(restarted)

    recovered = get_document(restarted, document["document_id"])
    assert recovered["status"] == "processed"
    assert upload_fields(recovered) == upload_fields(document)
    assert vector_store(restarted).count_document(document["document_id"]) == 2


def test_failed_document_is_not_retried_automatically_on_restart(make_client, embedder):
    client = make_client()
    document = failed_document(client, embedder)
    embedded_before = len(embedder.embedded_texts)

    restarted = make_client()
    wait_for_processing(restarted)

    assert get_document(restarted, document["document_id"]) == document
    assert len(embedder.embedded_texts) == embedded_before


# --- Deletion during a retry ------------------------------------------------


def test_delete_while_retry_is_queued_recreates_nothing(client, embedder, settings, hold_worker):
    document = failed_document(client, embedder)
    gate = hold_worker()
    blocker = upload(client, content=QUALITY_PDF).json()
    assert gate.started.wait(timeout=5)

    assert reindex(client, document["document_id"]).status_code == 202  # Queued behind the blocker
    assert client.delete(f"/api/documents/{document['document_id']}").status_code == 200
    gate.release.set()
    wait_for_processing(client)

    assert gate.calls == [blocker["document_id"]]  # The retry found the document gone and did nothing
    assert_nothing_left(client, settings, document["document_id"])


def test_delete_during_retry_indexing_recreates_nothing(client, embedder, settings):
    document = failed_document(client, embedder, content=LONG_PDF)
    real_embed = embedder.embed
    deleted = []

    def embed_then_delete(texts):
        vectors = real_embed(texts)
        if not deleted:
            deleted.append(client.delete(f"/api/documents/{document['document_id']}").status_code)
        return vectors

    embedder.embed = embed_then_delete
    client.app.state.document_processor._indexer._batch_size = 2

    assert reindex(client, document["document_id"]).status_code == 202
    wait_for_processing(client)

    assert deleted == [200]
    assert_nothing_left(client, settings, document["document_id"])
    assert len(embedder.calls) <= 2  # Stopped early instead of embedding the whole document


def test_delete_during_a_retry_that_then_fails_leaves_nothing(client, embedder, settings):
    document = failed_document(client, embedder)

    def delete_then_fail(texts):
        assert client.delete(f"/api/documents/{document['document_id']}").status_code == 200
        raise EmbeddingError(EMBEDDING_DOWN)

    embedder.embed = delete_then_fail

    assert reindex(client, document["document_id"]).status_code == 202
    wait_for_processing(client)

    assert_nothing_left(client, settings, document["document_id"])


def test_delete_finishing_after_the_retry_leaves_nothing(client, embedder, settings, monkeypatch):
    """The narrowest window: the retry writes chunks and vectors after the delete has cleaned up,
    and completes before the delete removes the metadata."""
    document = failed_document(client, embedder)
    document_id = document["document_id"]
    extracted, delete_paused, retry_finished = threading.Event(), threading.Event(), threading.Event()

    real_process_pdf = processing_service.process_pdf

    def extract_then_wait(*args, **kwargs):
        result = real_process_pdf(*args, **kwargs)  # Reads the PDF before the delete removes it
        extracted.set()
        assert delete_paused.wait(timeout=5)
        return result

    store = client.app.state.document_service._store
    real_remove = store.remove

    def remove_after_retry(doc_id):
        delete_paused.set()
        assert retry_finished.wait(timeout=5)
        real_remove(doc_id)

    monkeypatch.setattr(processing_service, "process_pdf", extract_then_wait)
    monkeypatch.setattr(store, "remove", remove_after_retry)

    assert reindex(client, document_id).status_code == 202
    assert extracted.wait(timeout=5)
    responses = []
    deleter = threading.Thread(target=lambda: responses.append(client.delete(f"/api/documents/{document_id}")))
    deleter.start()
    wait_for_processing(client)
    # The retry completed while the delete was still under way, so it saw the document and kept its data.
    assert get_document(client, document_id)["status"] == "processed"
    assert chunk_file(settings, document_id).exists()
    retry_finished.set()
    deleter.join(timeout=10)

    assert [response.status_code for response in responses] == [200]
    assert_nothing_left(client, settings, document_id)
