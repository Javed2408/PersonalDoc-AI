"""Phase 4 processing through the API: vectors stored, kept consistent, cleaned up."""

import pytest

from app.retrieval.vector_store import ChromaVectorStore, VectorStoreError
from tests.conftest import get_document, upload, wait_for_processing
from tests.pdf_factory import build_pdf, paragraph
from tests.test_processing import CORRUPTED_PDF, QUALITY_PDF, add_record, upload_and_process

LONG_PDF = build_pdf([paragraph("Alpha", 60), None, paragraph("Gamma", 45)])


def vector_store(client) -> ChromaVectorStore:
    return client.app.state.vector_store


def chunk_ids(client, document_id):
    return [c["chunk_id"] for c in client.get(f"/api/documents/{document_id}/chunks").json()["chunks"]]


def test_processed_document_has_one_vector_per_chunk(client):
    document = upload_and_process(client, content=LONG_PDF)
    store = vector_store(client)

    records = store.get_document_records(document["document_id"])

    assert document["status"] == "processed"
    assert len(records) == document["chunk_count"] > 4
    assert sorted(records) == sorted(chunk_ids(client, document["document_id"]))
    text, metadata = records[f"{document['document_id']}-00000"]
    assert text.startswith("Alpha sentence 1")
    assert metadata == {
        "document_id": document["document_id"], "original_filename": "quality.pdf",
        "page_number": 1, "chunk_index": 0, "start_char": 0, "char_count": len(text),
    }


def test_chunks_are_embedded_in_batches(make_client, embedder):
    client = make_client(embedding_batch_size=4)

    document = upload_and_process(client, content=LONG_PDF)

    assert sum(len(call) for call in embedder.calls) == document["chunk_count"]
    assert max(len(call) for call in embedder.calls) == 4


def test_restart_creates_no_duplicates_and_no_reembedding(make_client, embedder):
    first = make_client()
    document = upload_and_process(first, content=LONG_PDF)
    embedded_before = len(embedder.embedded_texts)

    restarted = make_client()
    wait_for_processing(restarted)

    assert len(embedder.embedded_texts) == embedded_before
    assert get_document(restarted, document["document_id"])["status"] == "processed"
    assert vector_store(restarted).stats()["vector_count"] == document["chunk_count"]


def test_missing_vectors_are_rebuilt_on_startup(make_client, embedder):
    client = make_client()
    document = upload_and_process(client)
    vector_store(client).delete_document(document["document_id"])  # e.g. chroma dir wiped

    restarted = make_client()
    wait_for_processing(restarted)

    assert get_document(restarted, document["document_id"])["status"] == "processed"
    assert vector_store(restarted).count_document(document["document_id"]) == document["chunk_count"]


def test_phase3_documents_get_indexed_on_upgrade(make_client, settings):
    # A document processed before vectors existed: status "processed", no vectors.
    add_record(settings, "c" * 32, status="processed", content=QUALITY_PDF)
    from app.services.document_store import JsonDocumentStore
    JsonDocumentStore(settings.metadata_file).update("c" * 32, page_count=2, chunk_count=2)

    client = make_client()
    wait_for_processing(client)

    assert get_document(client, "c" * 32)["status"] == "processed"
    assert vector_store(client).count_document("c" * 32) == 2


def test_duplicate_filenames_get_separate_vectors(client):
    first = upload_and_process(client, filename="report.pdf")
    second = upload_and_process(client, filename="report.pdf", content=build_pdf(["Different content."]))

    store = vector_store(client)
    assert store.count_document(first["document_id"]) == 2
    assert store.count_document(second["document_id"]) == 1
    assert store.stats()["vector_count"] == 3


def test_delete_removes_vectors(client):
    keep = upload_and_process(client)
    remove = upload_and_process(client, content=LONG_PDF)

    assert client.delete(f"/api/documents/{remove['document_id']}").status_code == 200

    store = vector_store(client)
    assert store.count_document(remove["document_id"]) == 0
    assert store.count_document(keep["document_id"]) == keep["chunk_count"]


def test_delete_succeeds_when_vectors_are_already_gone(client):
    document = upload_and_process(client)
    vector_store(client).delete_document(document["document_id"])

    assert client.delete(f"/api/documents/{document['document_id']}").status_code == 200
    assert client.get("/api/documents").json()["documents"] == []


def test_failed_vector_delete_keeps_document_for_retry(client, monkeypatch):
    document = upload_and_process(client)
    store = vector_store(client)
    real_delete = store.delete_document

    def broken(document_id):
        raise VectorStoreError("disk error")

    monkeypatch.setattr(store, "delete_document", broken)
    response = client.delete(f"/api/documents/{document['document_id']}")
    assert response.status_code == 500
    assert response.json() == {"detail": "The document could not be deleted."}
    assert get_document(client, document["document_id"])  # Still listed, so it can be retried

    monkeypatch.setattr(store, "delete_document", real_delete)
    assert client.delete(f"/api/documents/{document['document_id']}").status_code == 200
    assert store.count_document(document["document_id"]) == 0


def test_embedding_failure_marks_document_failed(client, embedder, settings):
    embedder.fail_with = "The embedding model could not be loaded. Check the backend logs."

    document = upload_and_process(client)

    assert document["status"] == "failed"
    assert document["processing_error"] == "The embedding model could not be loaded. Check the backend logs."
    assert (settings.documents_dir / document["stored_filename"]).exists()  # PDF kept
    assert (settings.chunks_dir / f"{document['document_id']}.json").exists()  # Chunks kept
    assert vector_store(client).count_document(document["document_id"]) == 0
    assert client.get("/api/health").status_code == 200


def test_vector_store_failure_marks_document_failed_without_partial_vectors(client, monkeypatch):
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

    document = upload_and_process(client, content=LONG_PDF)

    assert document["status"] == "failed"
    assert document["processing_error"] == (
        "The document could not be saved to the vector index. Check the backend logs."
    )
    assert store.count_document(document["document_id"]) == 0  # First batch rolled back


def test_extraction_failure_stores_no_vectors(client, embedder):
    document = upload_and_process(client, content=CORRUPTED_PDF)

    assert document["status"] == "failed"
    assert embedder.calls == []
    assert vector_store(client).stats()["vector_count"] == 0


def test_delete_during_indexing_leaves_no_vectors(client, embedder, settings):
    real_embed = embedder.embed
    state = {"deleted": False}

    def embed_then_delete(texts):
        vectors = real_embed(texts)
        if not state["deleted"]:
            state["deleted"] = True
            document_id = client.get("/api/documents").json()["documents"][0]["document_id"]
            assert client.delete(f"/api/documents/{document_id}").status_code == 200
        return vectors

    embedder.embed = embed_then_delete
    client.app.state.document_processor._indexer._batch_size = 2

    upload(client, content=LONG_PDF)
    wait_for_processing(client)

    assert client.get("/api/documents").json()["documents"] == []
    assert vector_store(client).stats()["vector_count"] == 0
    assert list(settings.chunks_dir.iterdir()) == []
    assert len(embedder.calls) <= 2  # Stopped early instead of embedding the whole document


def test_startup_refuses_a_collection_built_with_another_model(make_client):
    from tests.fakes import FakeEmbedder

    make_client()  # Creates the collection with the default fake model.

    with pytest.raises(Exception, match="was built with embedding model"):
        make_client(embedder_override=FakeEmbedder(model_name="other/model"))
