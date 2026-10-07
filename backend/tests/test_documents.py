from datetime import datetime

import pytest

from app.services.document_service import sanitize_display_name
from tests.conftest import MINIMAL_PDF, upload, upload_fields


def stored_files(settings):
    return sorted(p.name for p in settings.documents_dir.iterdir())


# --- Upload ---------------------------------------------------------------


def test_upload_pdf_succeeds_and_stores_file(client, settings):
    response = upload(client)

    assert response.status_code == 201
    body = response.json()
    stored = settings.documents_dir / body["stored_filename"]
    assert stored.read_bytes() == MINIMAL_PDF


def test_upload_returns_correct_metadata(client):
    body = upload(client, filename="Quarterly Report.pdf").json()

    assert set(body) == {
        "document_id", "original_filename", "stored_filename",
        "file_type", "file_size", "status", "created_at",
        "page_count", "chunk_count", "processing_error",
    }
    assert len(body["document_id"]) == 32
    assert body["original_filename"] == "Quarterly Report.pdf"
    assert body["stored_filename"] == f"{body['document_id']}.pdf"
    assert body["file_type"] == "pdf"
    assert body["file_size"] == len(MINIMAL_PDF)
    assert body["status"] == "uploaded"
    assert body["page_count"] is None
    assert body["chunk_count"] is None
    assert body["processing_error"] is None
    assert datetime.fromisoformat(body["created_at"]).tzinfo is not None


def test_upload_accepts_uppercase_extension_and_octet_stream(client):
    response = upload(client, filename="SCAN.PDF", content_type="application/octet-stream")

    assert response.status_code == 201


def test_storage_directory_is_created_on_startup(make_client, settings):
    assert not settings.documents_dir.exists()

    make_client()

    assert settings.documents_dir.is_dir()


# --- Listing and persistence ----------------------------------------------


def test_list_is_empty_initially(client):
    response = client.get("/api/documents")

    assert response.status_code == 200
    assert response.json() == {"documents": []}


def test_list_returns_uploaded_documents_newest_first(client):
    first = upload(client, filename="a.pdf").json()
    second = upload(client, filename="b.pdf").json()

    documents = client.get("/api/documents").json()["documents"]

    assert [d["document_id"] for d in documents] == [second["document_id"], first["document_id"]]
    assert upload_fields(documents[1]) == upload_fields(first)


def test_list_order_is_stable_for_identical_timestamps(client, monkeypatch):
    import app.services.document_service as document_service

    fixed = datetime(2026, 1, 1, tzinfo=document_service.UTC)

    class FrozenDatetime(datetime):
        @classmethod
        def now(cls, tz=None):
            return fixed

    monkeypatch.setattr(document_service, "datetime", FrozenDatetime)
    ids = [upload(client, filename=f"{n}.pdf").json()["document_id"] for n in range(3)]

    documents = client.get("/api/documents").json()["documents"]

    assert [d["document_id"] for d in documents] == ids[::-1]


def test_documents_persist_after_restart(make_client):
    uploaded = upload(make_client()).json()

    restarted = make_client()
    documents = restarted.get("/api/documents").json()["documents"]

    assert [upload_fields(doc) for doc in documents] == [upload_fields(uploaded)]


def test_corrupt_metadata_returns_safe_error_and_is_not_overwritten(client, settings):
    settings.metadata_file.write_text("{not json", encoding="utf-8")

    list_response = client.get("/api/documents")
    upload_response = upload(client)

    assert list_response.status_code == 500
    assert list_response.json() == {"detail": "The document library could not be loaded."}
    assert upload_response.status_code == 500
    assert settings.metadata_file.read_text(encoding="utf-8") == "{not json"
    assert stored_files(settings) == []


# --- Validation -----------------------------------------------------------


@pytest.mark.parametrize(
    ("filename", "content", "content_type"),
    [
        ("notes.txt", b"hello", "text/plain"),
        ("image.png", b"\x89PNG\r\n", "image/png"),
        ("report.pdf", b"not a pdf at all", "application/pdf"),
        ("report.pdf", MINIMAL_PDF, "text/html"),
        ("report.pdf.exe", MINIMAL_PDF, "application/pdf"),
        ("report", MINIMAL_PDF, "application/pdf"),
    ],
)
def test_unsupported_files_are_rejected(client, settings, filename, content, content_type):
    response = upload(client, filename=filename, content=content, content_type=content_type)

    assert response.status_code == 415
    assert isinstance(response.json()["detail"], str)
    assert stored_files(settings) == []
    assert client.get("/api/documents").json()["documents"] == []


def test_empty_file_is_rejected(client, settings):
    response = upload(client, content=b"")

    assert response.status_code == 400
    assert response.json() == {"detail": "The file is empty."}
    assert stored_files(settings) == []


def test_oversized_file_rejected_before_body_is_read(make_client, settings):
    client = make_client(max_upload_size_mb=1)
    content = MINIMAL_PDF + b"0" * (2 * 1024 * 1024)

    response = upload(client, content=content)

    assert response.status_code == 413
    assert response.json() == {"detail": "The file is larger than the 1 MB limit."}
    assert stored_files(settings) == []


def test_oversized_file_rejected_while_streaming(make_client, settings):
    # Just over the limit, so it passes the Content-Length pre-check and hits the exact check.
    client = make_client(max_upload_size_mb=1)
    content = MINIMAL_PDF + b"0" * (1024 * 1024 - len(MINIMAL_PDF) + 1)

    response = upload(client, content=content)

    assert response.status_code == 413
    assert stored_files(settings) == []


def test_file_exactly_at_limit_is_accepted(make_client):
    client = make_client(max_upload_size_mb=1)
    content = MINIMAL_PDF + b"0" * (1024 * 1024 - len(MINIMAL_PDF))

    assert upload(client, content=content).status_code == 201


def test_missing_file_field_is_rejected(client):
    response = client.post("/api/documents/upload", data={"something": "else"})

    assert response.status_code == 422


def test_malformed_multipart_is_rejected(client, settings):
    response = client.post(
        "/api/documents/upload",
        content=b"--boundary\r\nnot really multipart",
        headers={"Content-Type": "multipart/form-data; boundary=boundary"},
    )

    assert 400 <= response.status_code < 500
    assert stored_files(settings) == []


# --- Duplicates -----------------------------------------------------------


def test_duplicate_filenames_coexist(client, settings):
    first = upload(client, filename="report.pdf", content=MINIMAL_PDF).json()
    second = upload(client, filename="report.pdf", content=MINIMAL_PDF + b"% v2\n").json()

    assert first["document_id"] != second["document_id"]
    assert first["stored_filename"] != second["stored_filename"]
    assert (settings.documents_dir / first["stored_filename"]).read_bytes() == MINIMAL_PDF
    assert (settings.documents_dir / second["stored_filename"]).read_bytes() == MINIMAL_PDF + b"% v2\n"
    names = [d["original_filename"] for d in client.get("/api/documents").json()["documents"]]
    assert names == ["report.pdf", "report.pdf"]


# --- Deletion -------------------------------------------------------------


def test_delete_removes_file_and_metadata(client, settings):
    keep = upload(client, filename="report.pdf").json()
    remove = upload(client, filename="report.pdf").json()

    response = client.delete(f"/api/documents/{remove['document_id']}")

    assert response.status_code == 200
    assert response.json() == {"document_id": remove["document_id"], "deleted": True}
    assert stored_files(settings) == [keep["stored_filename"]]
    remaining = client.get("/api/documents").json()["documents"]
    assert [upload_fields(doc) for doc in remaining] == [upload_fields(keep)]


def test_delete_nonexistent_document_returns_404(client):
    response = client.delete("/api/documents/0123456789abcdef0123456789abcdef")

    assert response.status_code == 404
    assert response.json() == {"detail": "Document not found."}


def test_delete_succeeds_when_physical_file_is_missing(client, settings):
    document = upload(client).json()
    (settings.documents_dir / document["stored_filename"]).unlink()

    response = client.delete(f"/api/documents/{document['document_id']}")

    assert response.status_code == 200
    assert client.get("/api/documents").json()["documents"] == []


def test_deleted_document_stays_deleted_after_restart(make_client):
    client = make_client()
    document = upload(client).json()
    client.delete(f"/api/documents/{document['document_id']}")

    assert make_client().get("/api/documents").json()["documents"] == []


# --- Path traversal / unsafe names ----------------------------------------


@pytest.mark.parametrize(
    ("filename", "expected_display_name"),
    [
        ("../../evil.pdf", "evil.pdf"),
        ("..\\..\\windows\\evil.pdf", "evil.pdf"),
        ("/etc/passwd.pdf", "passwd.pdf"),
        ("C:\\Users\\victim\\secret.pdf", "secret.pdf"),
    ],
)
def test_unsafe_filenames_never_reach_the_filesystem(client, settings, filename, expected_display_name):
    response = upload(client, filename=filename)

    assert response.status_code == 201
    body = response.json()
    assert body["original_filename"] == expected_display_name
    assert stored_files(settings) == [f"{body['document_id']}.pdf"]
    # Nothing was written outside the storage directories (only the metadata file).
    assert sorted(p.name for p in settings.data_dir.iterdir()) == ["chroma", "chunks", "documents", "documents.json"]


@pytest.mark.parametrize("filename", ["evil.pdf\x00.exe", "evil.pdf%00.exe", "../"])
def test_names_that_are_not_pdf_after_sanitizing_are_rejected(client, settings, filename):
    response = upload(client, filename=filename)

    assert response.status_code == 415
    assert stored_files(settings) == []


@pytest.mark.parametrize("document_id", ["..%2Fdocuments.json", "..%5C..%5Cmain.py", "%2E%2E"])
def test_delete_with_traversal_id_touches_nothing(client, settings, document_id):
    document = upload(client).json()

    response = client.delete(f"/api/documents/{document_id}")

    assert response.status_code == 404
    assert settings.metadata_file.exists()
    assert stored_files(settings) == [document["stored_filename"]]


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("bad\x00name\r\n.pdf", "badname.pdf"),
        ("evil.pdf\x00.exe", "evil.pdf.exe"),
        ("‮gpj.pdf", "gpj.pdf"),  # right-to-left override (format char)
        ("../../", ""),
        (None, ""),
    ],
)
def test_sanitize_display_name_strips_control_and_path_characters(raw, expected):
    assert sanitize_display_name(raw) == expected


def test_long_filenames_are_truncated_keeping_extension():
    name = sanitize_display_name("a" * 500 + ".pdf")

    assert len(name) == 200
    assert name.endswith(".pdf")
