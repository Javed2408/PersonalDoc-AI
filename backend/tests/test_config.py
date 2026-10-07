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
