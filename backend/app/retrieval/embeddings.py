"""Text -> embedding vectors with a local model.

`Embedder` is the interface the rest of the app depends on, so the model (or the
library behind it) can be swapped without touching indexing code.
"""

import logging
import threading
from collections.abc import Sequence
from typing import Protocol

logger = logging.getLogger(__name__)


class EmbeddingError(Exception):
    """Embeddings could not be produced. `message` is safe to show to users."""

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


class Embedder(Protocol):
    @property
    def model_name(self) -> str: ...

    @property
    def dimension(self) -> int: ...

    def embed(self, texts: Sequence[str]) -> list[list[float]]: ...


def validate_texts(texts: Sequence[str]) -> list[str]:
    if isinstance(texts, str):
        raise ValueError("embed() expects a sequence of strings, not a single string")
    items = list(texts)
    for index, text in enumerate(items):
        if not isinstance(text, str):
            raise ValueError(f"Item {index} is {type(text).__name__}, expected str")
        if not text.strip():
            raise ValueError(f"Item {index} is empty or whitespace")
    return items


class SentenceTransformerEmbedder:
    """Embeds text with a sentence-transformers model, loaded once on first use.

    Loading is deferred so the API starts instantly; the first document processed
    pays the load cost (and, on a fresh machine, the model download).
    """

    def __init__(self, model_name: str, device: str | None = "cpu", batch_size: int = 32) -> None:
        self._model_name = model_name
        self._device = device
        self._batch_size = batch_size
        self._model = None
        self._lock = threading.Lock()

    @property
    def model_name(self) -> str:
        return self._model_name

    @property
    def dimension(self) -> int:
        return self._load().get_embedding_dimension()

    def embed(self, texts: Sequence[str]) -> list[list[float]]:
        items = validate_texts(texts)
        if not items:
            return []
        model = self._load()
        try:
            # Normalised vectors make cosine similarity a plain dot product later on.
            vectors = model.encode(
                items,
                batch_size=self._batch_size,
                normalize_embeddings=True,
                convert_to_numpy=True,
                show_progress_bar=False,
            )
        except (RuntimeError, ValueError, MemoryError) as error:
            logger.error("Embedding %d texts with %s failed: %s", len(items), self._model_name, error)
            raise EmbeddingError("The text could not be converted into embeddings.") from error
        return vectors.tolist()

    def _load(self):
        with self._lock:
            if self._model is None:
                logger.info(
                    "Loading embedding model %s on %s (downloads on first use)",
                    self._model_name, self._device or "auto",
                )
                try:
                    # Imported lazily: torch is slow to import and not needed until now.
                    from sentence_transformers import SentenceTransformer

                    self._model = SentenceTransformer(self._model_name, device=self._device)
                except Exception as error:  # noqa: BLE001
                    # Download, cache, device and model-format problems surface as many
                    # different exception types; all mean "no model", and we retry next time.
                    logger.error("Could not load embedding model %s: %s", self._model_name, error)
                    raise EmbeddingError(
                        "The embedding model could not be loaded. Check the backend logs."
                    ) from error
                logger.info(
                    "Embedding model ready: %s (dimension %d)",
                    self._model_name, self._model.get_embedding_dimension(),
                )
            return self._model
