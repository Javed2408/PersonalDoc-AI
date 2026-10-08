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


TOPIC_VOCABULARY = (
    # machine learning
    "machine", "learning", "model", "models", "training", "data", "gradient", "neural",
    # cooking
    "bread", "dough", "oven", "flour", "yeast", "bake", "recipe", "knead",
    # networking
    "router", "routers", "packets", "tcp", "dns", "protocol", "latency", "bandwidth",
)


class TopicEmbedder:
    """Deterministic keyword-count embeddings: texts sharing vocabulary end up close.

    Gives ranking tests real meaning without loading the real model.
    """

    model_name = "test/topic-embedder"
    dimension = len(TOPIC_VOCABULARY) + 1

    def __init__(self) -> None:
        self.calls: list[list[str]] = []

    def embed(self, texts: Sequence[str]) -> list[list[float]]:
        items = validate_texts(texts)
        self.calls.append(items)
        return [self.vector(text) for text in items]

    def vector(self, text: str) -> list[float]:
        words = [word.strip(".,;:!?()\"'").lower() for word in text.split()]
        raw = [float(words.count(term)) for term in TOPIC_VOCABULARY]
        raw.append(0.05)  # Never a zero vector, even for off-topic text
        norm = math.sqrt(sum(value * value for value in raw))
        return [value / norm for value in raw]


class FakeLLM:
    """Deterministic stand-in for Ollama. Records every prompt it receives.

    `reply` is a fixed answer or a function (system, user) -> answer; set `error` to make
    every call raise it (e.g. LLMUnavailableError).
    """

    def __init__(self, reply="The documents say so. [Source 1]", model_name: str = "test/fake-llm") -> None:
        self._model_name = model_name
        self.reply = reply
        self.error: Exception | None = None
        self.calls: list[tuple[str, str]] = []
        self.health = "ready"  # What status() reports to the health endpoint

    @property
    def model_name(self) -> str:
        return self._model_name

    def status(self) -> str:
        return self.health

    @property
    def last_user_prompt(self) -> str:
        return self.calls[-1][1]

    def generate(self, system: str, user: str) -> str:
        self.calls.append((system, user))
        if self.error:
            raise self.error
        return self.reply(system, user) if callable(self.reply) else self.reply
