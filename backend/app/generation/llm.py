"""Local LLM access. `LLM` is the interface; `OllamaLLM` talks to a local Ollama server.

Nothing here knows about RAG: it turns a system prompt plus a user message into text.
Uses the standard library HTTP client, so no extra dependency is needed.
"""

import json
import logging
import socket
import time
import urllib.error
import urllib.request
from typing import Literal, Protocol

logger = logging.getLogger(__name__)

# The health check must stay fast even when Ollama hangs.
STATUS_TIMEOUT_SECONDS = 2.0


class LLMError(Exception):
    """Generation failed. `message` is safe to show to users."""

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


class LLMUnavailableError(LLMError):
    """The LLM server can't be reached."""


class LLMModelNotFoundError(LLMError):
    """The server is up but the configured model isn't installed."""


class LLMTimeoutError(LLMError):
    """The model didn't answer within the configured timeout."""


# Reported by LLM.status(): can a question be answered right now?
LLMStatus = Literal["ready", "unavailable", "model_missing"]


class LLM(Protocol):
    @property
    def model_name(self) -> str: ...

    def generate(self, system: str, user: str) -> str: ...

    def status(self) -> LLMStatus: ...


class OllamaLLM:
    def __init__(
        self,
        base_url: str,
        model: str,
        temperature: float = 0.0,
        max_tokens: int = 512,
        context_window: int = 4096,
        timeout: float = 120.0,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._model = model
        self._options = {"temperature": temperature, "num_predict": max_tokens, "num_ctx": context_window}
        self._timeout = timeout

    @property
    def model_name(self) -> str:
        return self._model

    def generate(self, system: str, user: str) -> str:
        payload = {
            "model": self._model,
            "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
            "stream": False,
            "options": self._options,
        }
        started = time.perf_counter()
        body = self._post("/api/chat", payload)
        try:
            content = body["message"]["content"]
        except (KeyError, TypeError) as error:
            logger.error("Unexpected Ollama response shape: keys=%s", list(body) if isinstance(body, dict) else type(body))
            raise LLMError("The local language model returned an unexpected response.") from error
        if not isinstance(content, str) or not content.strip():
            raise LLMError("The local language model returned an empty answer.")
        # Log sizes and timing only: prompts and answers may contain private document text.
        logger.info(
            "LLM %s answered in %.1fs (%s prompt tokens, %s output tokens)",
            self._model, time.perf_counter() - started, body.get("prompt_eval_count"), body.get("eval_count"),
        )
        return content.strip()

    def status(self) -> LLMStatus:
        """Cheap availability check for the health endpoint: is Ollama up, and is the model pulled?"""
        try:
            with urllib.request.urlopen(self._base_url + "/api/tags", timeout=STATUS_TIMEOUT_SECONDS) as response:
                body = json.loads(response.read())
            names = {model.get("name") for model in body.get("models", []) if isinstance(model, dict)}
        except (OSError, ValueError, AttributeError) as error:  # URLError and timeouts are OSErrors
            logger.debug("Ollama status check failed: %s", error)
            return "unavailable"
        # Ollama lists untagged pulls as "<name>:latest".
        return "ready" if self._model in names or f"{self._model}:latest" in names else "model_missing"

    def _post(self, path: str, payload: dict) -> dict:
        request = urllib.request.Request(
            self._base_url + path,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=self._timeout) as response:
                raw = response.read()
        except urllib.error.HTTPError as error:
            detail = self._error_detail(error)
            if error.code == 404 and "not found" in detail.lower():
                logger.warning("Ollama model %s not found: %s", self._model, detail)
                raise LLMModelNotFoundError(
                    f"The model '{self._model}' is not installed in Ollama. Run: ollama pull {self._model}"
                ) from error
            logger.error("Ollama returned HTTP %d: %s", error.code, detail)
            raise LLMError("The local language model failed to generate an answer.") from error
        except (TimeoutError, socket.timeout) as error:
            raise LLMTimeoutError(
                f"The local language model did not answer within {self._timeout:g} seconds."
            ) from error
        except urllib.error.URLError as error:
            if isinstance(error.reason, (TimeoutError, socket.timeout)):
                raise LLMTimeoutError(
                    f"The local language model did not answer within {self._timeout:g} seconds."
                ) from error
            logger.warning("Ollama unreachable at %s: %s", self._base_url, error.reason)
            raise LLMUnavailableError(
                f"Can't reach Ollama at {self._base_url}. Make sure Ollama is installed and running."
            ) from error
        except (ConnectionError, OSError) as error:
            logger.warning("Ollama connection failed at %s: %s", self._base_url, error)
            raise LLMUnavailableError(
                f"Can't reach Ollama at {self._base_url}. Make sure Ollama is installed and running."
            ) from error

        try:
            return json.loads(raw)
        except ValueError as error:
            raise LLMError("The local language model returned an unexpected response.") from error

    @staticmethod
    def _error_detail(error: urllib.error.HTTPError) -> str:
        try:
            body = json.loads(error.read() or b"{}")
            return str(body.get("error", "")) if isinstance(body, dict) else ""
        except (ValueError, OSError):
            return ""
