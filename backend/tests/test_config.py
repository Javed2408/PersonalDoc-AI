import pytest
from pydantic import ValidationError

from app.config import BACKEND_DIR, Settings


def test_cors_origins_parsed_from_comma_separated_env(monkeypatch):
    monkeypatch.setenv("CORS_ORIGINS", "http://a.test, http://b.test")

    settings = Settings(_env_file=None)

    assert settings.cors_origins == ["http://a.test", "http://b.test"]


def test_storage_paths_default_under_backend_data():
    settings = Settings(_env_file=None)

    assert settings.documents_dir == BACKEND_DIR / "data" / "documents"
    assert settings.metadata_file == BACKEND_DIR / "data" / "documents.json"


def test_relative_data_dir_resolves_against_backend_dir(monkeypatch):
    monkeypatch.setenv("DATA_DIR", "custom-data")

    settings = Settings(_env_file=None)

    assert settings.data_dir == (BACKEND_DIR / "custom-data").resolve()


def test_max_upload_size_from_env(monkeypatch):
    monkeypatch.setenv("MAX_UPLOAD_SIZE_MB", "5")

    settings = Settings(_env_file=None)

    assert settings.max_upload_bytes == 5 * 1024 * 1024


def test_chunk_settings_from_env(monkeypatch):
    monkeypatch.setenv("CHUNK_SIZE", "800")
    monkeypatch.setenv("CHUNK_OVERLAP", "100")

    settings = Settings(_env_file=None)

    assert (settings.chunk_size, settings.chunk_overlap) == (800, 100)
    assert settings.chunks_dir == settings.data_dir / "chunks"


@pytest.mark.parametrize(("size", "overlap"), [(100, 100), (100, 200), (0, 0)])
def test_invalid_chunk_settings_are_rejected(size, overlap):
    with pytest.raises(ValidationError):
        Settings(_env_file=None, chunk_size=size, chunk_overlap=overlap)


def test_embedding_and_chroma_defaults():
    settings = Settings(_env_file=None)

    assert settings.embedding_model == "sentence-transformers/all-MiniLM-L6-v2"
    assert settings.embedding_device == "cpu"
    assert settings.embedding_batch_size == 32
    assert settings.chroma_dir == BACKEND_DIR / "data" / "chroma"
    assert settings.chroma_collection == "personaldoc_chunks"


def test_chroma_dir_follows_data_dir_unless_set(monkeypatch, tmp_path):
    assert Settings(_env_file=None, data_dir=tmp_path).chroma_dir == tmp_path / "chroma"

    monkeypatch.setenv("CHROMA_DIR", "vectors")
    assert Settings(_env_file=None).chroma_dir == (BACKEND_DIR / "vectors").resolve()


def test_embedding_settings_from_env(monkeypatch):
    monkeypatch.setenv("EMBEDDING_MODEL", "BAAI/bge-small-en-v1.5")
    monkeypatch.setenv("EMBEDDING_DEVICE", "")
    monkeypatch.setenv("EMBEDDING_BATCH_SIZE", "64")
    monkeypatch.setenv("CHROMA_COLLECTION", "bge_chunks")

    settings = Settings(_env_file=None)

    assert settings.embedding_model == "BAAI/bge-small-en-v1.5"
    assert settings.embedding_device is None  # Blank means auto-detect
    assert settings.embedding_batch_size == 64
    assert settings.chroma_collection == "bge_chunks"


@pytest.mark.parametrize(
    "overrides",
    [
        {"chroma_collection": "ab"},
        {"chroma_collection": "has space"},
        {"chroma_collection": "-leading-dash"},
        {"embedding_batch_size": 0},
        {"embedding_model": ""},
    ],
)
def test_invalid_embedding_settings_are_rejected(overrides):
    with pytest.raises(ValidationError):
        Settings(_env_file=None, **overrides)


def test_retrieval_defaults_and_env(monkeypatch):
    settings = Settings(_env_file=None)
    assert (settings.retrieval_top_k, settings.retrieval_max_k, settings.retrieval_max_distance) == (4, 20, None)

    monkeypatch.setenv("RETRIEVAL_TOP_K", "6")
    monkeypatch.setenv("RETRIEVAL_MAX_K", "30")
    monkeypatch.setenv("RETRIEVAL_MAX_DISTANCE", "0.65")
    settings = Settings(_env_file=None)
    assert (settings.retrieval_top_k, settings.retrieval_max_k, settings.retrieval_max_distance) == (6, 30, 0.65)

    monkeypatch.setenv("RETRIEVAL_MAX_DISTANCE", "")
    assert Settings(_env_file=None).retrieval_max_distance is None


@pytest.mark.parametrize(
    "overrides",
    [
        {"retrieval_top_k": 0},
        {"retrieval_top_k": 25, "retrieval_max_k": 20},
        {"retrieval_max_k": 101},
        {"retrieval_max_distance": 0},
        {"retrieval_max_distance": 2.5},
    ],
)
def test_invalid_retrieval_settings_are_rejected(overrides):
    with pytest.raises(ValidationError):
        Settings(_env_file=None, **overrides)
