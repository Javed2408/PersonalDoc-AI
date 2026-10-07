"""Test doubles. The real embedding model is exercised in tests marked `model`."""

import hashlib
import math
from collections.abc import Sequence

from app.retrieval.embeddings import EmbeddingError, validate_texts


class FakeEmbedder:
    """Deterministic, instant embeddings derived from a hash of the text."""

    def __init__(self, model_name: str = "test/fake-embedder", dimension: int = 16) -> None:
        self._model_name = model_name
        self._dimension = dimension
        self.calls: list[list[str]] = []
        self.fail_with: str | None = None

    @property
    def model_name(self) -> str:
        return self._model_name

    @property
    def dimension(self) -> int:
        return self._dimension

    @property
    def embedded_texts(self) -> list[str]:
        return [text for call in self.calls for text in call]

    def embed(self, texts: Sequence[str]) -> list[list[float]]:
        items = validate_texts(texts)
        if self.fail_with:
            raise EmbeddingError(self.fail_with)
        self.calls.append(items)
        return [self.vector(text) for text in items]

    def vector(self, text: str) -> list[float]:
        digest = hashlib.sha256(text.encode("utf-8")).digest()
        raw = [digest[i % len(digest)] / 255 - 0.5 for i in range(self._dimension)]
        norm = math.sqrt(sum(value * value for value in raw)) or 1.0
        return [value / norm for value in raw]
