"""RAG answer evaluation with the real embedding model and the local Ollama model.

Indexes the Phase 5 evaluation documents (plus a memo containing a prompt injection) in a
throwaway data directory, asks every question in rag_dataset.json through POST /api/chat,
and scores grounded answering, not-found behaviour, source preservation and injection
resistance. Keyword scoring is a coarse proxy, so the report includes every answer for review.

    cd backend
    python -m evaluation.rag_eval            # print the report (needs Ollama + the model)
    python -m evaluation.rag_eval --write    # also save evaluation/results/rag_baseline.md
"""

import argparse
import json
import re
import tempfile
import time
from dataclasses import dataclass
from datetime import date
from pathlib import Path

from chromadb.api.shared_system_client import SharedSystemClient
from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app
from tests.pdf_factory import build_pdf

EVAL_DIR = Path(__file__).resolve().parent
RESULTS_FILE = EVAL_DIR / "results" / "rag_baseline.md"

# Phrases that mean "the documents don't say". Used to recognise declines and partial answers.
DECLINE = re.compile(
    r"couldn't find|could not find|not (mention|specif|state|provide|includ|say|contain|cover|list)|"
    r"doesn't (mention|specif|state|say|contain|cover|list)|does not (mention|specif|state|say|contain|cover|list)|"
    r"no information|not available|unknown|isn't (mentioned|specified|stated)",
    re.IGNORECASE,
)


class CountingLLM:
    """Wraps the real LLM to tell model calls apart from evidence-gate declines."""

    def __init__(self, inner) -> None:
        self._inner = inner
        self.calls = 0

    @property
    def model_name(self) -> str:
        return self._inner.model_name

    def generate(self, system: str, user: str) -> str:
        self.calls += 1
        return self._inner.generate(system, user)


@dataclass
class Outcome:
    id: str
    category: str
    expect: str
    question: str
    status: str
    answer: str
    sources: list[str]
    llm_called: bool
    seconds: float
    passed: bool
    source_ok: bool | None  # Expected page among the sources (None when no source is expected)


def score(item: dict, body: dict) -> tuple[bool, bool | None]:
    answer = body["answer"]
    lowered = answer.lower()
    if any(bad.lower() in lowered for bad in item.get("must_not", [])):
        return False, None
    mentions = any(word.lower() in lowered for word in item.get("any_of", []))
    declines = body["status"] == "not_found" or bool(DECLINE.search(answer))
    if item["expect"] == "answer":
        passed = body["status"] == "answered" and mentions
    elif item["expect"] == "partial":
        passed = body["status"] == "answered" and mentions and bool(DECLINE.search(answer))
    else:
        passed = declines
    expected = item.get("source")
    source_ok = None
    if expected:
        source_ok = any(
            s["original_filename"] == expected["filename"] and s["page_number"] == expected["page"]
            for s in body["sources"]
        )
    return passed, source_ok


def run(embedder=None, llm=None) -> tuple[str, list[Outcome]]:
    retrieval_set = json.loads((EVAL_DIR / "retrieval_dataset.json").read_text(encoding="utf-8"))
    rag_set = json.loads((EVAL_DIR / "rag_dataset.json").read_text(encoding="utf-8"))
    documents = retrieval_set["documents"] + rag_set["extra_documents"]

    with tempfile.TemporaryDirectory(prefix="personaldoc-rag-eval-", ignore_cleanup_errors=True) as tmp:
        settings = Settings(_env_file=None, data_dir=Path(tmp) / "data")
        app = create_app(settings, embedder=embedder, llm=llm)
        counting = CountingLLM(app.state.rag_chain._llm)
        app.state.rag_chain._llm = counting
        try:
            with TestClient(app) as client:
                for document in documents:
                    client.post(
                        "/api/documents/upload",
                        files={"file": (document["filename"], build_pdf(document["pages"]), "application/pdf")},
                    ).raise_for_status()
                if not app.state.document_processor.wait_until_idle(timeout=600):
                    raise RuntimeError("Indexing did not finish")

                outcomes = []
                for item in rag_set["questions"]:
                    calls_before = counting.calls
                    started = time.perf_counter()
                    response = client.post("/api/chat", json={"question": item["question"]})
                    if response.status_code != 200:
                        raise RuntimeError(f"{item['id']}: HTTP {response.status_code} {response.json().get('detail')}")
                    body = response.json()
                    passed, source_ok = score(item, body)
                    outcomes.append(Outcome(
                        id=item["id"], category=item["category"], expect=item["expect"], question=item["question"],
                        status=body["status"], answer=body["answer"],
                        sources=[f"{s['original_filename']} p.{s['page_number']} ({s['distance']:.2f})" for s in body["sources"]],
                        llm_called=counting.calls > calls_before, seconds=time.perf_counter() - started,
                        passed=passed, source_ok=source_ok,
                    ))
                return counting.model_name, outcomes
        finally:
            SharedSystemClient.clear_system_cache()


def to_markdown(model: str, outcomes: list[Outcome]) -> str:
    def rate(items):
        return f"{sum(o.passed for o in items)}/{len(items)}" if items else "n/a"

    categories = list(dict.fromkeys(o.category for o in outcomes))
    with_sources = [o for o in outcomes if o.source_ok is not None and o.status == "answered"]
    settings = Settings(_env_file=None)
    lines = [
        "# RAG evaluation: baseline",
        "",
        f"- Date: {date.today().isoformat()}",
        f"- LLM: `{model}` via Ollama (temperature {settings.llm_temperature}, max {settings.llm_max_tokens} tokens)",
        f"- Embeddings: `{settings.embedding_model}`; k = {settings.retrieval_top_k}; evidence gate: distance <= {settings.rag_max_distance}",
        f"- Questions: {len(outcomes)} (`evaluation/rag_dataset.json`), over the retrieval evaluation documents plus a memo with a prompt injection",
        "- Scoring is keyword-based (a coarse proxy); read the answers below before trusting the numbers.",
        "",
        "## Summary",
        "",
        "| Category | Passed |",
        "| --- | --- |",
        *[f"| {c} | {rate([o for o in outcomes if o.category == c])} |" for c in categories],
        f"| **All** | **{rate(outcomes)}** |",
        "",
        f"- Source preservation (answered questions whose expected page is among the sources): "
        f"{sum(bool(o.source_ok) for o in with_sources)}/{len(with_sources)}",
        f"- Declines decided by the evidence gate (LLM not called): {sum(1 for o in outcomes if o.status == 'not_found' and not o.llm_called)}; "
        f"by the model: {sum(1 for o in outcomes if o.status == 'not_found' and o.llm_called)}",
        f"- Mean time per question: {sum(o.seconds for o in outcomes) / len(outcomes):.1f}s",
        "",
        "## Answers",
        "",
        "| ID | Category | Question | Status | Pass | Answer | Sources |",
        "| --- | --- | --- | --- | --- | --- | --- |",
    ]
    for o in outcomes:
        answer = o.answer.replace("\n", " ").replace("|", "\\|")
        if len(answer) > 220:
            answer = answer[:217] + "..."
        how = "" if o.status == "answered" else (" (model)" if o.llm_called else " (gate)")
        lines.append(
            f"| {o.id} | {o.category} | {o.question} | {o.status}{how} | {'yes' if o.passed else '**no**'} | "
            f"{answer} | {'; '.join(o.sources) or '-'} |"
        )
    return "\n".join(lines) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--write", action="store_true", help=f"save the report to {RESULTS_FILE}")
    args = parser.parse_args()
    model, outcomes = run()
    markdown = to_markdown(model, outcomes)
    print(markdown)
    if args.write:
        RESULTS_FILE.parent.mkdir(parents=True, exist_ok=True)
        RESULTS_FILE.write_text(markdown, encoding="utf-8")
        print(f"Saved {RESULTS_FILE}")


if __name__ == "__main__":
    main()
