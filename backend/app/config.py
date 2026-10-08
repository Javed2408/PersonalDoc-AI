"""Application configuration loaded from environment variables and `.env`."""

import re
from functools import lru_cache
from pathlib import Path
from typing import Annotated

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parent.parent

# ChromaDB collection name rules.
_COLLECTION_NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{1,510}[A-Za-z0-9]$")


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=BACKEND_DIR / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "PersonalDoc AI"
    app_version: str = "0.1.0"
    environment: str = "development"
    log_level: str = "INFO"
    cors_origins: Annotated[list[str], NoDecode] = [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ]

    # Local runtime data (uploaded files, metadata). Relative paths resolve against backend/.
    data_dir: Path = BACKEND_DIR / "data"
    max_upload_size_mb: int = Field(default=25, gt=0)

    # Text chunking, in characters.
    chunk_size: int = Field(default=1000, gt=0)
    chunk_overlap: int = Field(default=150, ge=0)

    # Local embedding model (sentence-transformers / Hugging Face Hub name or local path).
    # Changing it requires re-indexing: the vector store refuses to mix models.
    embedding_model: str = Field(default="sentence-transformers/all-MiniLM-L6-v2", min_length=1)
    # "cpu", "cuda", "mps"... Empty means let sentence-transformers pick.
    embedding_device: str | None = "cpu"
    embedding_batch_size: int = Field(default=32, gt=0, le=1024)

    # ChromaDB persistence. Defaults to <DATA_DIR>/chroma; relative paths resolve against backend/.
    chroma_dir: Path | None = None
    chroma_collection: str = "personaldoc_chunks"

    # Retrieval. RETRIEVAL_TOP_K is the default number of chunks returned per query;
    # requests may ask for up to RETRIEVAL_MAX_K.
    retrieval_top_k: int = Field(default=4, ge=1)
    retrieval_max_k: int = Field(default=20, ge=1, le=100)
    # Optional cut-off on cosine distance (0 = same direction, 1 = unrelated, 2 = opposite).
    # Off by default: a sensible value must come from evaluation (Phase 9), not a guess.
    retrieval_max_distance: float | None = Field(default=None, gt=0, le=2)

    # Local LLM (Ollama). Nothing is sent anywhere else.
    ollama_base_url: str = "http://127.0.0.1:11434"
    ollama_model: str = Field(default="llama3.2:3b", min_length=1)
    # Factual QA: no creativity wanted.
    llm_temperature: float = Field(default=0.0, ge=0, le=2)
    llm_max_tokens: int = Field(default=512, ge=16, le=8192)
    # Model context window in tokens. Must hold instructions + context + question + answer;
    # Ollama silently truncates prompts that don't fit, which would drop evidence.
    llm_context_window: int = Field(default=4096, ge=1024, le=131072)
    llm_timeout_seconds: float = Field(default=120.0, gt=0, le=600)

    # RAG. Retrieved chunks farther than RAG_MAX_DISTANCE (cosine distance) are not treated
    # as evidence; with none left, the answer is "not found" and the LLM is not called.
    # 0.7 = cosine similarity below 0.3, where all-MiniLM-L6-v2 texts are typically unrelated.
    # Provisional and conservative: tune with the Phase 9 evaluation.
    rag_max_distance: float = Field(default=0.7, gt=0, le=2)
    # Budget for document text in the prompt (complete chunks are kept; see rag_chain.py).
    rag_max_context_chars: int = Field(default=6000, ge=500, le=200_000)

    @field_validator("cors_origins", mode="before")
    @classmethod
    def split_origins(cls, value: object) -> object:
        if isinstance(value, str):
            return [origin.strip() for origin in value.split(",") if origin.strip()]
        return value

    @field_validator("data_dir")
    @classmethod
    def resolve_data_dir(cls, value: Path) -> Path:
        return value if value.is_absolute() else (BACKEND_DIR / value).resolve()

    @field_validator("chroma_dir")
    @classmethod
    def resolve_chroma_dir(cls, value: Path | None) -> Path | None:
        if value is None or value.is_absolute():
            return value
        return (BACKEND_DIR / value).resolve()

    @field_validator("embedding_device", "retrieval_max_distance", mode="before")
    @classmethod
    def blank_means_unset(cls, value: object) -> object:
        return None if isinstance(value, str) and not value.strip() else value

    @field_validator("chroma_collection")
    @classmethod
    def check_collection_name(cls, value: str) -> str:
        if not _COLLECTION_NAME.match(value):
            raise ValueError(
                "CHROMA_COLLECTION must be 3-512 characters of letters, digits, '.', '_' or '-', "
                "starting and ending with a letter or digit"
            )
        return value

    @model_validator(mode="after")
    def check_chunk_overlap(self) -> "Settings":
        if self.chunk_overlap >= self.chunk_size:
            raise ValueError("CHUNK_OVERLAP must be smaller than CHUNK_SIZE")
        return self

    @model_validator(mode="after")
    def check_retrieval_k(self) -> "Settings":
        if self.retrieval_top_k > self.retrieval_max_k:
            raise ValueError("RETRIEVAL_TOP_K must not exceed RETRIEVAL_MAX_K")
        return self

    @field_validator("ollama_base_url")
    @classmethod
    def check_ollama_url(cls, value: str) -> str:
        value = value.strip().rstrip("/")
        if not value.startswith(("http://", "https://")):
            raise ValueError("OLLAMA_BASE_URL must start with http:// or https://")
        return value

    @model_validator(mode="after")
    def default_chroma_dir(self) -> "Settings":
        if self.chroma_dir is None:
            self.chroma_dir = self.data_dir / "chroma"
        return self

    @property
    def documents_dir(self) -> Path:
        return self.data_dir / "documents"

    @property
    def chunks_dir(self) -> Path:
        return self.data_dir / "chunks"

    @property
    def metadata_file(self) -> Path:
        return self.data_dir / "documents.json"

    @property
    def max_upload_bytes(self) -> int:
        return self.max_upload_size_mb * 1024 * 1024


@lru_cache
def get_settings() -> Settings:
    return Settings()
