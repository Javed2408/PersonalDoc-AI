"""End to end with the real model: PDF -> extract -> chunk -> embed -> ChromaDB.

Reads the stored records back to prove they exist; no similarity queries (Phase 5).
"""

import math

import chromadb
import pytest
from chromadb.api.shared_system_client import SharedSystemClient
from chromadb.config import Settings as ChromaSettings

from tests.conftest import get_document, upload, wait_for_processing
from tests.pdf_factory import build_pdf, paragraph

pytestmark = pytest.mark.model

QUALITY_PAGES = [
    "PersonalDoc AI extraction test.\nThis text lives on the first page.",
    "Second page extraction test.\nThis text lives on the second page.",
]


class CountingEmbedder:
    """Wraps the real embedder to count how many texts get embedded."""

    def __init__(self, inner):
        self._inner = inner
        self.texts = 0

    @property
    def model_name(self):
        return self._inner.model_name

    @property
    def dimension(self):
        return self._inner.dimension

    def embed(self, texts):
        self.texts += len(texts)
        return self._inner.embed(texts)


def read_collection(settings):
    """Open the persisted collection with a brand-new ChromaDB client."""
    SharedSystemClient.clear_system_cache()
    client = chromadb.PersistentClient(
        path=str(settings.chroma_dir), settings=ChromaSettings(anonymized_telemetry=False)
    )
    return client.get_collection(settings.chroma_collection)


def test_pdf_is_indexed_into_chromadb_end_to_end(make_client, settings, real_embedder):
    counting = CountingEmbedder(real_embedder)
    client = make_client(embedder_override=counting)

    quality = upload(client, filename="quality.pdf", content=build_pdf(QUALITY_PAGES)).json()
    long_doc = upload(client, filename="long.pdf", content=build_pdf([paragraph("Alpha", 60), paragraph("Beta", 30)])).json()
    wait_for_processing(client)

    quality = get_document(client, quality["document_id"])
    long_doc = get_document(client, long_doc["document_id"])
    assert quality["status"] == long_doc["status"] == "processed"
    assert quality["chunk_count"] == 2
    expected_ids = {
        doc["document_id"]: [c["chunk_id"] for c in client.get(f"/api/documents/{doc['document_id']}/chunks").json()["chunks"]]
        for doc in (quality, long_doc)
    }
    total_chunks = quality["chunk_count"] + long_doc["chunk_count"]
    assert counting.texts == total_chunks

    # Read the records straight from disk with a fresh client.
    collection = read_collection(settings)
    assert collection.count() == total_chunks
    assert collection.metadata["embedding_model"] == "sentence-transformers/all-MiniLM-L6-v2"

    records = collection.get(
        where={"document_id": quality["document_id"]}, include=["documents", "metadatas", "embeddings"]
    )
    by_id = dict(zip(records["ids"], zip(records["documents"], records["metadatas"], records["embeddings"])))
    assert sorted(by_id) == sorted(expected_ids[quality["document_id"]])

    text, metadata, embedding = by_id[f"{quality['document_id']}-00001"]
    assert text == QUALITY_PAGES[1]
    assert metadata == {
        "document_id": quality["document_id"], "original_filename": "quality.pdf",
        "page_number": 2, "chunk_index": 1, "start_char": 0, "char_count": len(QUALITY_PAGES[1]),
    }
    assert len(embedding) == 384
    assert math.sqrt(sum(float(v) ** 2 for v in embedding)) == pytest.approx(1.0, abs=1e-4)
    # The stored vector is exactly what the model produces for that chunk.
    assert [float(v) for v in embedding] == pytest.approx(real_embedder.embed([text])[0], abs=1e-5)

    long_records = collection.get(where={"document_id": long_doc["document_id"]}, include=["metadatas"])
    assert sorted(long_records["ids"]) == sorted(expected_ids[long_doc["document_id"]])
    assert {m["page_number"] for m in long_records["metadatas"]} == {1, 2}

    # Restart the app: nothing is re-embedded and nothing is duplicated.
    restarted = make_client(embedder_override=counting)
    wait_for_processing(restarted)
    assert counting.texts == total_chunks
    assert read_collection(settings).count() == total_chunks

    # Delete one document: its vectors go, the other's stay.
    assert restarted.delete(f"/api/documents/{long_doc['document_id']}").status_code == 200
    collection = read_collection(settings)
    assert collection.count() == quality["chunk_count"]
    assert collection.get(where={"document_id": long_doc["document_id"]})["ids"] == []
