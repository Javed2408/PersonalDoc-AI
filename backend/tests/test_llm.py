"""OllamaLLM against a local stub HTTP server that mimics Ollama's /api/chat."""

import json
import socket
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest

from app.generation.llm import (
    LLMError,
    LLMModelNotFoundError,
    LLMTimeoutError,
    LLMUnavailableError,
    OllamaLLM,
)


class StubOllama:
    """Serves one configurable /api/chat behaviour (plus /api/tags) and records requests."""

    def __init__(self) -> None:
        self.requests: list[dict] = []
        self.status = 200
        self.body: object = {"message": {"role": "assistant", "content": "  An answer.  "}, "eval_count": 3}
        self.delay = 0.0
        self.tags: object = {"models": [{"name": "llama3.2:3b"}]}
        stub = self

        class Handler(BaseHTTPRequestHandler):
            def do_GET(self):  # noqa: N802
                time.sleep(stub.delay)
                payload = stub.tags if isinstance(stub.tags, bytes) else json.dumps(stub.tags).encode()
                self.send_response(200 if self.path == "/api/tags" else 404)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(payload)))
                self.end_headers()
                try:
                    self.wfile.write(payload)
                except OSError:
                    pass

            def do_POST(self):  # noqa: N802
                length = int(self.headers.get("Content-Length", 0))
                stub.requests.append({"path": self.path, "json": json.loads(self.rfile.read(length))})
                time.sleep(stub.delay)
                payload = stub.body if isinstance(stub.body, bytes) else json.dumps(stub.body).encode()
                self.send_response(stub.status)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(payload)))
                self.end_headers()
                try:
                    self.wfile.write(payload)
                except OSError:
                    pass  # Client gave up (timeout test)

            def log_message(self, *args):
                pass

        self.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.url = f"http://127.0.0.1:{self.server.server_address[1]}"
        threading.Thread(target=self.server.serve_forever, daemon=True).start()

    def close(self) -> None:
        self.server.shutdown()
        self.server.server_close()


@pytest.fixture
def stub():
    server = StubOllama()
    yield server
    server.close()


def make_llm(url, **kwargs):
    return OllamaLLM(url, "llama3.2:3b", **kwargs)


def free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def test_sends_system_and_user_messages_with_options(stub):
    llm = make_llm(stub.url, temperature=0.0, max_tokens=256, context_window=4096)

    answer = llm.generate("SYSTEM RULES", "CONTEXT AND QUESTION")

    assert answer == "An answer."
    [request] = stub.requests
    assert request["path"] == "/api/chat"
    assert request["json"] == {
        "model": "llama3.2:3b",
        "messages": [
            {"role": "system", "content": "SYSTEM RULES"},
            {"role": "user", "content": "CONTEXT AND QUESTION"},
        ],
        "stream": False,
        "options": {"temperature": 0.0, "num_predict": 256, "num_ctx": 4096},
    }
    assert llm.model_name == "llama3.2:3b"


def test_trailing_slash_in_base_url_is_handled(stub):
    assert make_llm(stub.url + "/").generate("s", "u") == "An answer."
    assert stub.requests[0]["path"] == "/api/chat"


def test_missing_model_gives_pull_instructions(stub):
    stub.status = 404
    stub.body = {"error": "model 'llama3.2:3b' not found, try pulling it first"}

    with pytest.raises(LLMModelNotFoundError, match="Run: ollama pull llama3.2:3b"):
        make_llm(stub.url).generate("s", "u")


def test_server_not_running_is_unavailable():
    with pytest.raises(LLMUnavailableError, match="Make sure Ollama is installed and running"):
        make_llm(f"http://127.0.0.1:{free_port()}", timeout=5).generate("s", "u")


def test_slow_model_times_out(stub):
    stub.delay = 1.5

    with pytest.raises(LLMTimeoutError, match="did not answer within 0.3 seconds"):
        make_llm(stub.url, timeout=0.3).generate("s", "u")


@pytest.mark.parametrize(
    ("status", "body"),
    [
        (500, {"error": "CUDA out of memory"}),
        (200, b"not json"),
        (200, {"unexpected": "shape"}),
        (200, {"message": {"content": "   "}}),
        (200, {"message": {"content": None}}),
    ],
)
def test_bad_responses_raise_safe_errors(stub, status, body):
    stub.status, stub.body = status, body

    with pytest.raises(LLMError) as raised:
        make_llm(stub.url).generate("s", "u")

    assert not isinstance(raised.value, (LLMUnavailableError, LLMModelNotFoundError, LLMTimeoutError))
    assert "CUDA" not in raised.value.message  # Internal details stay in the logs


def test_prompts_and_answers_are_not_logged(stub, caplog):
    stub.body = {"message": {"content": "Secret answer about salaries."}}

    with caplog.at_level("DEBUG", logger="app.generation.llm"):
        make_llm(stub.url).generate("system", "Private document text about salaries")

    assert "salaries" not in caplog.text
    assert "llama3.2:3b answered" in caplog.text


def test_status_ready_when_the_model_is_pulled(stub):
    assert make_llm(stub.url).status() == "ready"


def test_status_accepts_the_implicit_latest_tag(stub):
    stub.tags = {"models": [{"name": "mistral:latest"}]}

    assert OllamaLLM(stub.url, "mistral").status() == "ready"


def test_status_model_missing_when_ollama_runs_without_the_model(stub):
    stub.tags = {"models": [{"name": "mistral:latest"}]}

    assert make_llm(stub.url).status() == "model_missing"


def test_status_unavailable_when_ollama_is_not_running():
    assert make_llm(f"http://127.0.0.1:{free_port()}").status() == "unavailable"


@pytest.mark.parametrize("tags", [b"not json", [1, 2], {"models": "nope"}])
def test_status_unavailable_on_an_unexpected_tags_response(stub, tags):
    stub.tags = tags

    assert make_llm(stub.url).status() in {"unavailable", "model_missing"}


def test_status_check_is_bounded_when_ollama_hangs(stub, monkeypatch):
    monkeypatch.setattr("app.generation.llm.STATUS_TIMEOUT_SECONDS", 0.2)
    stub.delay = 1.5

    started = time.perf_counter()
    assert make_llm(stub.url).status() == "unavailable"
    assert time.perf_counter() - started < 1.0
