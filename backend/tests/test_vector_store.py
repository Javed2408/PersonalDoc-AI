"""ChromaDB vector store, using temporary directories and deterministic fake vectors."""

import pytest
from chromadb.api.shared_system_client import SharedSystemClient

from app.models.schemas import Chunk
from app.retrieval.vector_store import ChromaVectorStore, EmbeddingModelMismatchError, VectorStoreError
from tests.fakes import FakeEmbedder

MODEL = "test/fake-embedder"
DOC_A = "a" * 32
DOC_B = "b" * 32
fake = FakeEmbedder()


def make_chunks(document_id, count, prefix="text"):
    return [
        Chunk(
            chunk_id=f"{document_id}-{i:05d}", document_id=document_id, original_filename=f"{document_id[:4]}.pdf",
            page_number=i // 2 + 1, chunk_index=i, start_char=10 * i, char_count=len(f"{prefix} {i}"),
            text=f"{prefix} {i}",
        )
        for i in range(count)
    ]


def vectors(chunks):
    return [fake.vector(chunk.text) for chunk in chunks]


@pytest.fixture
def chroma_dir(tmp_path):
    yield tmp_path / "chroma"
    SharedSystemClient.clear_system_cache()


@pytest.fixture
def store(chroma_dir):
    return ChromaVectorStore(chroma_dir, "test_chunks", MODEL)


def reopen(chroma_dir, model=MODEL):
    """A fresh store, as after a backend restart (drops ChromaDB's in-process cache)."""
    SharedSystemClient.clear_system_cache()
    return ChromaVectorStore(chroma_dir, "test_chunks", model)


def test_opening_creates_persistent_collection(store, chroma_dir):
    store.open()

    assert (chroma_dir / "chroma.sqlite3").exists()
    assert store.stats() == {"collection": "test_chunks", "embedding_model": MODEL, "vector_count": 0}


def test_adds_vectors_with_text_and_metadata(store):
    chunks = make_chunks(DOC_A, 3)

    store.upsert_chunks(chunks, vectors(chunks))

    records = store.get_document_records(DOC_A)
    assert sorted(records) == [c.chunk_id for c in chunks]
    text, metadata = records[chunks[2].chunk_id]
    assert text == "text 2"
    assert metadata == {
        "document_id": DOC_A, "original_filename": "aaaa.pdf", "page_number": 2,
        "chunk_index": 2, "start_char": 20, "char_count": 6,
    }


def test_vectors_persist_after_reinitialization(store, chroma_dir):
    chunks = make_chunks(DOC_A, 4)
    store.upsert_chunks(chunks, vectors(chunks))

    reopened = reopen(chroma_dir)

    assert reopened.count_document(DOC_A) == 4
    assert reopened.stats()["vector_count"] == 4
    assert sorted(reopened.get_document_records(DOC_A)) == [c.chunk_id for c in chunks]


def test_identifies_documents_by_their_vectors(store):
    chunks = make_chunks(DOC_A, 2)
    store.upsert_chunks(chunks, vectors(chunks))

    assert store.has_document(DOC_A)
    assert store.count_document(DOC_A) == 2
    assert not store.has_document(DOC_B)
    assert store.count_document(DOC_B) == 0


def test_repeated_upserts_never_duplicate(store):
    chunks = make_chunks(DOC_A, 5)

    for _ in range(3):
        store.upsert_chunks(chunks, vectors(chunks))

    assert store.count_document(DOC_A) == 5
    assert store.stats()["vector_count"] == 5


def test_upsert_replaces_changed_content(store):
    chunks = make_chunks(DOC_A, 2)
    store.upsert_chunks(chunks, vectors(chunks))
    changed = make_chunks(DOC_A, 2, prefix="revised")

    store.upsert_chunks(changed, vectors(changed))

    texts = sorted(text for text, _ in store.get_document_records(DOC_A).values())
    assert texts == ["revised 0", "revised 1"]
    assert store.count_document(DOC_A) == 2


def test_delete_document_removes_only_that_document(store):
    a, b = make_chunks(DOC_A, 3), make_chunks(DOC_B, 2)
    store.upsert_chunks(a, vectors(a))
    store.upsert_chunks(b, vectors(b))

    store.delete_document(DOC_A)

    assert store.count_document(DOC_A) == 0
    assert store.count_document(DOC_B) == 2
    assert store.stats()["vector_count"] == 2


def test_deleting_missing_vectors_is_safe(store):
    store.delete_document(DOC_A)
    store.delete_ids([])
    store.delete_ids([f"{DOC_A}-00007"])

    assert store.stats()["vector_count"] == 0


def test_delete_ids_removes_specific_vectors(store):
    chunks = make_chunks(DOC_A, 3)
    store.upsert_chunks(chunks, vectors(chunks))

    store.delete_ids([chunks[1].chunk_id])

    assert sorted(store.get_document_records(DOC_A)) == [chunks[0].chunk_id, chunks[2].chunk_id]


def test_stats_count_all_vectors(store):
    a, b = make_chunks(DOC_A, 3), make_chunks(DOC_B, 4)
    store.upsert_chunks(a, vectors(a))
    store.upsert_chunks(b, vectors(b))

    assert store.stats() == {"collection": "test_chunks", "embedding_model": MODEL, "vector_count": 7}


def test_reopening_with_a_different_model_is_refused(store, chroma_dir):
    store.open()

    with pytest.raises(EmbeddingModelMismatchError, match="was built with embedding model 'test/fake-embedder'"):
        reopen(chroma_dir, model="other/model").open()


def test_wrong_vector_dimension_is_rejected(store):
    chunks = make_chunks(DOC_A, 1)
    store.upsert_chunks(chunks, vectors(chunks))

    with pytest.raises(VectorStoreError):
        store.upsert_chunks(make_chunks(DOC_B, 1), [[0.1, 0.2, 0.3]])


def test_mismatched_lengths_are_rejected(store):
    with pytest.raises(ValueError):
        store.upsert_chunks(make_chunks(DOC_A, 2), [fake.vector("only one")])
