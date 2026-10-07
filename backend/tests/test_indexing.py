"""DocumentIndexer: embedding only what changed, never duplicating vectors."""

import pytest
from chromadb.api.shared_system_client import SharedSystemClient

from app.retrieval.vector_store import ChromaVectorStore
from app.services.indexing_service import DocumentIndexer, IndexingCancelled, IndexResult
from tests.fakes import FakeEmbedder
from tests.test_vector_store import DOC_A, DOC_B, make_chunks


@pytest.fixture
def embedder():
    return FakeEmbedder()


@pytest.fixture
def store(tmp_path):
    yield ChromaVectorStore(tmp_path / "chroma", "test_chunks", "test/fake-embedder")
    SharedSystemClient.clear_system_cache()


@pytest.fixture
def indexer(embedder, store):
    return DocumentIndexer(embedder, store, batch_size=4)


def test_first_index_embeds_every_chunk_in_batches(indexer, embedder, store):
    chunks = make_chunks(DOC_A, 10)

    result = indexer.index(DOC_A, chunks)

    assert result == IndexResult(embedded=10, unchanged=0, removed=0)
    assert [len(call) for call in embedder.calls] == [4, 4, 2]
    assert store.count_document(DOC_A) == 10
    # The vector IDs are the Phase 3 chunk IDs.
    assert sorted(store.get_document_records(DOC_A)) == [c.chunk_id for c in chunks]


def test_reindexing_identical_chunks_embeds_nothing(indexer, embedder, store):
    chunks = make_chunks(DOC_A, 6)
    indexer.index(DOC_A, chunks)
    embedder.calls.clear()

    result = indexer.index(DOC_A, chunks)

    assert result == IndexResult(embedded=0, unchanged=6, removed=0)
    assert embedder.calls == []
    assert store.count_document(DOC_A) == 6


def test_changed_chunks_are_reembedded(indexer, embedder, store):
    chunks = make_chunks(DOC_A, 4)
    indexer.index(DOC_A, chunks)
    embedder.calls.clear()
    changed = chunks[:2] + make_chunks(DOC_A, 4, prefix="revised")[2:]

    result = indexer.index(DOC_A, changed)

    assert result == IndexResult(embedded=2, unchanged=2, removed=0)
    assert embedder.embedded_texts == ["revised 2", "revised 3"]
    texts = sorted(text for text, _ in store.get_document_records(DOC_A).values())
    assert texts == ["revised 2", "revised 3", "text 0", "text 1"]


def test_metadata_change_alone_triggers_update(indexer, store):
    chunks = make_chunks(DOC_A, 2)
    indexer.index(DOC_A, chunks)
    renamed = [chunk.model_copy(update={"original_filename": "renamed.pdf"}) for chunk in chunks]

    result = indexer.index(DOC_A, renamed)

    assert result.embedded == 2
    assert {meta["original_filename"] for _, meta in store.get_document_records(DOC_A).values()} == {"renamed.pdf"}


def test_chunks_that_disappear_are_removed(indexer, store):
    indexer.index(DOC_A, make_chunks(DOC_A, 8))

    result = indexer.index(DOC_A, make_chunks(DOC_A, 5))

    assert result == IndexResult(embedded=0, unchanged=5, removed=3)
    assert store.count_document(DOC_A) == 5


def test_other_documents_are_untouched(indexer, store):
    indexer.index(DOC_B, make_chunks(DOC_B, 3))

    indexer.index(DOC_A, make_chunks(DOC_A, 2))
    indexer.index(DOC_A, make_chunks(DOC_A, 1))

    assert store.count_document(DOC_B) == 3


def test_cancellation_stops_between_batches(indexer, embedder):
    checks = []

    def cancelled():
        checks.append(1)
        return len(checks) > 1  # Allow the first batch, then report the document deleted.

    with pytest.raises(IndexingCancelled):
        indexer.index(DOC_A, make_chunks(DOC_A, 10), is_cancelled=cancelled)
    assert len(embedder.calls) == 1


def test_chunks_from_another_document_are_rejected(indexer):
    with pytest.raises(ValueError):
        indexer.index(DOC_A, make_chunks(DOC_B, 1))
