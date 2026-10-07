"""End-to-end document processing through the API: status flow, chunks, failures."""

import threading
from datetime import UTC, datetime

import pytest

import app.services.processing_service as processing_service
from app.models.schemas import DocumentMetadata
from app.services.document_store import JsonDocumentStore
from tests.conftest import get_document, upload, wait_for_processing
from tests.pdf_factory import DRAWING_ONLY, build_pdf, paragraph

QUALITY_PDF = build_pdf([
    "PersonalDoc AI extraction test.\nThis text lives on the first page.",
    "Second page extraction test.\nThis text lives on the second page.",
])
CORRUPTED_PDF = b"%PDF-1.4\n" + b"\x00this is not a real pdf body\n" * 20


def upload_and_process(client, content=QUALITY_PDF, filename="quality.pdf"):
    document = upload(client, filename=filename, content=content).json()
    wait_for_processing(client)
    return get_document(client, document["document_id"])


def add_record(settings, document_id, status, content=None):
    """Write a document record directly, as if left behind by an earlier run."""
    settings.documents_dir.mkdir(parents=True, exist_ok=True)
    if content is not None:
        (settings.documents_dir / f"{document_id}.pdf").write_bytes(content)
    JsonDocumentStore(settings.metadata_file).add(DocumentMetadata(
        document_id=document_id, original_filename="left-over.pdf", stored_filename=f"{document_id}.pdf",
        file_type="pdf", file_size=len(content or b""), status=status, created_at=datetime.now(UTC),
    ))


# --- Happy path -------------------------------------------------------------


def test_uploaded_pdf_is_processed(client):
    document = upload_and_process(client)

    assert document["status"] == "processed"
    assert document["page_count"] == 2
    assert document["chunk_count"] == 2
    assert document["processing_error"] is None


def test_chunks_endpoint_returns_traceable_chunks(client):
    document = upload_and_process(client)

    response = client.get(f"/api/documents/{document['document_id']}/chunks")

    assert response.status_code == 200
    body = response.json()
    assert body["document_id"] == document["document_id"]
    assert (body["chunk_size"], body["chunk_overlap"], body["chunk_count"]) == (1000, 150, 2)
    first, second = body["chunks"]
    assert first == {
        "chunk_id": f"{document['document_id']}-00000",
        "document_id": document["document_id"],
        "original_filename": "quality.pdf",
        "page_number": 1,
        "chunk_index": 0,
        "start_char": 0,
        "char_count": len(first["text"]),
        "text": "PersonalDoc AI extraction test.\nThis text lives on the first page.",
    }
    assert (second["page_number"], second["chunk_index"]) == (2, 1)
    assert second["text"].startswith("Second page extraction test.")


def test_long_document_chunk_ids_are_unique_and_pages_preserved(client):
    document = upload_and_process(client, content=build_pdf([paragraph("P1", 80), None, paragraph("P3", 80)]))

    chunks = client.get(f"/api/documents/{document['document_id']}/chunks").json()["chunks"]

    assert document["page_count"] == 3
    assert document["chunk_count"] == len(chunks) > 4
    assert len({c["chunk_id"] for c in chunks}) == len(chunks)
    assert {c["page_number"] for c in chunks} == {1, 3}
    assert all(c["document_id"] == document["document_id"] for c in chunks)


def test_chunk_settings_come_from_configuration(make_client):
    client = make_client(chunk_size=300, chunk_overlap=30)

    document = upload_and_process(client, content=build_pdf([paragraph("Config", 40)]))
    body = client.get(f"/api/documents/{document['document_id']}/chunks").json()

    assert (body["chunk_size"], body["chunk_overlap"]) == (300, 30)
    assert all(c["char_count"] <= 300 for c in body["chunks"])


def test_duplicate_filenames_are_processed_independently(client):
    first = upload_and_process(client, filename="report.pdf")
    second = upload_and_process(client, filename="report.pdf", content=build_pdf(["Different content."]))

    first_chunks = client.get(f"/api/documents/{first['document_id']}/chunks").json()["chunks"]
    second_chunks = client.get(f"/api/documents/{second['document_id']}/chunks").json()["chunks"]

    assert first_chunks[0]["text"].startswith("PersonalDoc AI")
    assert [c["text"] for c in second_chunks] == ["Different content."]


def test_status_moves_through_processing(client, monkeypatch):
    release = threading.Event()
    started = threading.Event()
    real_process_pdf = processing_service.process_pdf

    def slow_process_pdf(*args, **kwargs):
        started.set()
        release.wait(timeout=5)
        return real_process_pdf(*args, **kwargs)

    monkeypatch.setattr(processing_service, "process_pdf", slow_process_pdf)

    uploaded = upload(client, content=QUALITY_PDF).json()
    assert uploaded["status"] == "uploaded"
    assert started.wait(timeout=5)
    assert get_document(client, uploaded["document_id"])["status"] == "processing"
    assert client.get(f"/api/documents/{uploaded['document_id']}/chunks").status_code == 409

    release.set()
    wait_for_processing(client)
    assert get_document(client, uploaded["document_id"])["status"] == "processed"


# --- Failures ---------------------------------------------------------------


def test_corrupted_pdf_fails_but_keeps_the_upload(client, settings):
    document = upload_and_process(client, content=CORRUPTED_PDF, filename="broken.pdf")

    assert document["status"] == "failed"
    assert document["processing_error"] == "The PDF could not be read. It may be corrupted."
    assert (settings.documents_dir / document["stored_filename"]).exists()
    assert not (settings.chunks_dir / f"{document['document_id']}.json").exists()


def test_pdf_without_text_fails_with_explanation(client):
    document = upload_and_process(client, content=build_pdf([None, DRAWING_ONLY]), filename="scan.pdf")

    assert document["status"] == "failed"
    assert document["page_count"] is None
    assert "No extractable text was found" in document["processing_error"]


def test_chunks_of_failed_document_return_conflict(client):
    document = upload_and_process(client, content=CORRUPTED_PDF)

    response = client.get(f"/api/documents/{document['document_id']}/chunks")

    assert response.status_code == 409
    assert response.json() == {"detail": "This document could not be processed, so it has no text chunks."}


def test_chunks_of_unknown_document_return_404(client):
    response = client.get("/api/documents/0123456789abcdef0123456789abcdef/chunks")

    assert response.status_code == 404


def test_unexpected_processing_error_is_contained(client, monkeypatch):
    def explode(*args, **kwargs):
        raise RuntimeError("internal detail that must not leak")

    monkeypatch.setattr(processing_service, "process_pdf", explode)

    document = upload_and_process(client)

    assert document["status"] == "failed"
    assert document["processing_error"] == "The document could not be processed."
    assert client.get("/api/health").status_code == 200


def test_app_keeps_working_after_a_failure(client):
    upload_and_process(client, content=CORRUPTED_PDF)

    document = upload_and_process(client)

    assert document["status"] == "processed"
    statuses = sorted(doc["status"] for doc in client.get("/api/documents").json()["documents"])
    assert statuses == ["failed", "processed"]


def test_missing_stored_file_fails_cleanly(make_client, settings):
    add_record(settings, "a" * 32, status="uploaded", content=None)

    client = make_client()
    wait_for_processing(client)
    document = get_document(client, "a" * 32)

    assert document["status"] == "failed"
    assert document["processing_error"] == "The stored PDF file is missing."


# --- Persistence and lifecycle ----------------------------------------------


@pytest.mark.parametrize("status", ["uploaded", "processing"])
def test_interrupted_processing_resumes_on_startup(make_client, settings, status):
    add_record(settings, "b" * 32, status=status, content=QUALITY_PDF)

    client = make_client()
    wait_for_processing(client)

    assert get_document(client, "b" * 32)["status"] == "processed"


def test_processed_chunks_persist_after_restart(make_client):
    client = make_client()
    document = upload_and_process(client)
    before = client.get(f"/api/documents/{document['document_id']}/chunks").json()

    restarted = make_client()
    wait_for_processing(restarted)

    assert get_document(restarted, document["document_id"])["status"] == "processed"
    assert restarted.get(f"/api/documents/{document['document_id']}/chunks").json() == before


def test_delete_removes_chunks(client, settings):
    document = upload_and_process(client)
    chunk_file = settings.chunks_dir / f"{document['document_id']}.json"
    assert chunk_file.exists()

    assert client.delete(f"/api/documents/{document['document_id']}").status_code == 200

    assert not chunk_file.exists()
    assert client.get(f"/api/documents/{document['document_id']}/chunks").status_code == 404


def test_delete_during_processing_leaves_no_orphans(client, settings, monkeypatch):
    real_process_pdf = processing_service.process_pdf

    def delete_midway(path, document_id, *args, **kwargs):
        result = real_process_pdf(path, document_id, *args, **kwargs)
        assert client.delete(f"/api/documents/{document_id}").status_code == 200
        return result

    monkeypatch.setattr(processing_service, "process_pdf", delete_midway)

    upload(client, content=QUALITY_PDF)
    wait_for_processing(client)

    assert client.get("/api/documents").json()["documents"] == []
    assert list(settings.chunks_dir.iterdir()) == []
    assert list(settings.documents_dir.iterdir()) == []
