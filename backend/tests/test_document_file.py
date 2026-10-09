"""GET /api/documents/{document_id}/file: the original PDF, for preview, and nothing else."""

import json

import pytest

from tests.conftest import MINIMAL_PDF, upload, wait_for_processing
from tests.pdf_factory import build_pdf

PDF = build_pdf(["Page one text.", "Page two text."])


@pytest.fixture
def uploaded(client):
    document = upload(client, filename="Quarterly report.pdf", content=PDF).json()
    wait_for_processing(client)
    return client, document


def file_url(document_id: str) -> str:
    return f"/api/documents/{document_id}/file"


def test_returns_the_stored_pdf_inline_with_safe_headers(uploaded):
    client, document = uploaded

    response = client.get(file_url(document["document_id"]))

    assert response.status_code == 200
    assert response.content == PDF
    assert response.headers["content-type"] == "application/pdf"
    # The original name, percent-encoded (RFC 5987) because it contains a space.
    assert response.headers["content-disposition"] == "inline; filename*=utf-8''Quarterly%20report.pdf"
    assert response.headers["x-content-type-options"] == "nosniff"
    assert response.headers["cache-control"] == "no-store"
    assert response.headers["cross-origin-resource-policy"] == "same-site"


def test_non_ascii_and_quoted_names_are_encoded_not_injected(client):
    document = upload(client, filename='Résumé "final"; x=1.pdf', content=PDF).json()

    disposition = client.get(file_url(document["document_id"])).headers["content-disposition"]

    assert disposition.startswith("inline; filename*=utf-8''")
    assert '"' not in disposition and ";" not in disposition.split("''", 1)[1]


def test_supports_range_requests_for_pdf_viewers(uploaded):
    client, document = uploaded

    response = client.get(file_url(document["document_id"]), headers={"Range": "bytes=0-4"})

    assert response.status_code == 206
    assert response.content == b"%PDF-"


def test_preview_works_before_processing_finishes(client):
    # The PDF exists from the moment it is uploaded; previewing doesn't depend on its chunks.
    document = upload(client, content=MINIMAL_PDF).json()

    assert client.get(file_url(document["document_id"])).content == MINIMAL_PDF


def test_unknown_document_is_a_readable_404(client):
    response = client.get(file_url("0" * 32))

    assert response.status_code == 404
    assert response.json()["detail"] == "Document not found. It may have been deleted."


def test_deleted_document_is_no_longer_served(uploaded):
    client, document = uploaded
    client.delete(f"/api/documents/{document['document_id']}")

    response = client.get(file_url(document["document_id"]))

    assert response.status_code == 404
    assert "deleted" in response.json()["detail"]


def test_missing_file_on_disk_is_a_readable_404(uploaded, settings):
    client, document = uploaded
    (settings.documents_dir / document["stored_filename"]).unlink()

    response = client.get(file_url(document["document_id"]))

    assert response.status_code == 404
    assert response.json()["detail"] == "The original PDF of this document is no longer available."


@pytest.mark.parametrize(
    "document_id",
    ["not-a-document", "A" * 32, "0" * 31, "0" * 33, "g" * 32, "0" * 32 + ".pdf", "..."],
)
def test_malformed_ids_are_rejected_before_any_lookup(client, document_id):
    assert client.get(file_url(document_id)).status_code == 422


@pytest.mark.parametrize(
    "path",
    [
        "/api/documents/../documents.json/file",
        "/api/documents/..%2Fdocuments.json/file",
        "/api/documents/..%2F..%2F..%2Fapp%2Fconfig.py/file",
        "/api/documents/%2e%2e%2f%2e%2e%2fdocuments.json/file",
        "/api/documents/..\\documents.json/file",
    ],
)
def test_path_traversal_never_reaches_a_file(uploaded, path):
    client, _ = uploaded

    response = client.get(path)

    assert response.status_code in (404, 405, 422)
    assert b"%PDF" not in response.content
    assert b"stored_filename" not in response.content  # Not the metadata file either


def test_metadata_cannot_point_one_document_at_another_file(uploaded, settings):
    client, victim = uploaded
    other = upload(client, filename="other.pdf", content=MINIMAL_PDF).json()
    wait_for_processing(client)  # Processing rewrites the metadata; tamper after it settles.
    # Tamper with the metadata so `other` claims the first document's file.
    raw = json.loads(settings.metadata_file.read_text(encoding="utf-8"))
    for entry in raw["documents"]:
        if entry["document_id"] == other["document_id"]:
            entry["stored_filename"] = victim["stored_filename"]
    settings.metadata_file.write_text(json.dumps(raw), encoding="utf-8")

    response = client.get(file_url(other["document_id"]))

    assert response.status_code == 500
    assert response.json()["detail"] == "The document's file could not be opened."


def test_responses_never_reveal_storage_paths(uploaded, settings):
    client, document = uploaded
    data_dir = str(settings.data_dir)

    ok = client.get(file_url(document["document_id"]))
    missing = client.get(file_url("0" * 32))
    invalid = client.get(file_url("nope"))

    for response in (ok, missing, invalid):
        assert data_dir not in str(response.headers)
        assert data_dir not in response.text if response.status_code != 200 else True
        assert "stored_filename" not in str(response.headers)
    assert document["stored_filename"] not in ok.headers["content-disposition"]
