"""Retrieval evaluation: does the right source chunk appear in the top-k?

Runs the real pipeline (PDF -> extract -> chunk -> embed -> ChromaDB -> retrieve) over
evaluation/retrieval_dataset.json in a throwaway data directory, so backend/data is
never touched. Answers are not evaluated here; there is no LLM yet.

    cd backend
    python -m evaluation.retrieval_eval            # print the report
    python -m evaluation.retrieval_eval --write    # also save evaluation/results/retrieval_baseline.md
"""

import argparse
import json
import statistics
import tempfile
from dataclasses import dataclass
from datetime import date
from pathlib import Path

from chromadb.api.shared_system_client import SharedSystemClient
from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app
from tests.pdf_factory import build_pdf

EVAL_DIR = Path(__file__).resolve().parent
DATASET = EVAL_DIR / "retrieval_dataset.json"
RESULTS_FILE = EVAL_DIR / "results" / "retrieval_baseline.md"


@dataclass
class QuestionResult:
    id: str
    type: str
    question: str
    expected: str | None  # "filename p.N", or None when unanswerable
    rank: int | None  # 1-based rank of the expected page in the top-k, None if absent
    top: list[tuple[str, float]]  # ("filename p.N", distance) for each result

    @property
    def best_distance(self) -> float:
        return self.top[0][1]


@dataclass
class EvalReport:
    model: str
    k: int
    chunk_count: int
    results: list[QuestionResult]

    @property
    def answerable(self) -> list[QuestionResult]:
        return [r for r in self.results if r.expected]

    @property
    def unanswerable(self) -> list[QuestionResult]:
        return [r for r in self.results if not r.expected]

    def hit_rate(self, at: int) -> float:
        return sum(1 for r in self.answerable if r.rank and r.rank <= at) / len(self.answerable)

    @property
    def mrr(self) -> float:
        return statistics.mean(1 / r.rank if r.rank else 0 for r in self.answerable)


def run(embedder=None, k: int = 4) -> EvalReport:
    dataset = json.loads(DATASET.read_text(encoding="utf-8"))
    # ignore_cleanup_errors: on Windows ChromaDB keeps its index file mapped until the
    # process exits, so the temp dir may only be partly removable (the OS temp dir).
    with tempfile.TemporaryDirectory(prefix="personaldoc-eval-", ignore_cleanup_errors=True) as tmp:
        settings = Settings(_env_file=None, data_dir=Path(tmp) / "data")
        try:
            with TestClient(create_app(settings, embedder=embedder)) as client:
                names = {}
                for document in dataset["documents"]:
                    response = client.post(
                        "/api/documents/upload",
                        files={"file": (document["filename"], build_pdf(document["pages"]), "application/pdf")},
                    )
                    response.raise_for_status()
                    names[response.json()["document_id"]] = document["filename"]
                if not client.app.state.document_processor.wait_until_idle(timeout=600):
                    raise RuntimeError("Indexing did not finish")
                documents = client.get("/api/documents").json()["documents"]
                failed = [d["original_filename"] for d in documents if d["status"] != "processed"]
                if failed:
                    raise RuntimeError(f"Documents failed to process: {failed}")

                results = []
                for item in dataset["questions"]:
                    response = client.post("/api/retrieval/search", json={"query": item["question"], "k": k})
                    response.raise_for_status()
                    top = [
                        (f"{r['original_filename']} p.{r['page_number']}", r["distance"])
                        for r in response.json()["results"]
                    ]
                    expected = item["expected"]
                    label = f"{expected['filename']} p.{expected['page']}" if expected else None
                    rank = next((i for i, (source, _) in enumerate(top, start=1) if source == label), None)
                    results.append(QuestionResult(item["id"], item["type"], item["question"], label, rank, top))
                return EvalReport(
                    model=client.app.state.vector_store.stats()["embedding_model"],
                    k=k,
                    chunk_count=client.app.state.vector_store.stats()["vector_count"],
                    results=results,
                )
        finally:
            SharedSystemClient.clear_system_cache()  # Release the temp ChromaDB before cleanup


def to_markdown(report: EvalReport) -> str:
    answerable_best = [r.best_distance for r in report.answerable]
    unanswerable_best = [r.best_distance for r in report.unanswerable]
    lines = [
        "# Retrieval evaluation: baseline",
        "",
        f"- Date: {date.today().isoformat()}",
        f"- Embedding model: `{report.model}`",
        f"- Corpus: 3 documents, 9 pages, {report.chunk_count} chunks (`evaluation/retrieval_dataset.json`)",
        f"- k = {report.k}; distance = cosine distance (0 = identical direction, 1 = unrelated)",
        "",
        "## Summary",
        "",
        "| Metric | Value |",
        "| --- | --- |",
        f"| Answerable questions | {len(report.answerable)} |",
        f"| Hit@1 (expected page ranked first) | {report.hit_rate(1):.0%} |",
        f"| Hit@{report.k} (expected page in top {report.k}) | {report.hit_rate(report.k):.0%} |",
        f"| Mean reciprocal rank | {report.mrr:.2f} |",
        f"| Best distance, answerable (min / median / max) | {min(answerable_best):.3f} / {statistics.median(answerable_best):.3f} / {max(answerable_best):.3f} |",
        f"| Best distance, unanswerable (min / median / max) | {min(unanswerable_best):.3f} / {statistics.median(unanswerable_best):.3f} / {max(unanswerable_best):.3f} |",
        "",
        "## Per question",
        "",
        "| ID | Type | Question | Expected | Rank | Top result (distance) |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    for r in report.results:
        rank = str(r.rank) if r.rank else ("n/a" if not r.expected else "miss")
        source, distance = r.top[0]
        lines.append(
            f"| {r.id} | {r.type} | {r.question} | {r.expected or '(not in documents)'} | {rank} | {source} ({distance:.3f}) |"
        )
    return "\n".join(lines) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--k", type=int, default=4)
    parser.add_argument("--write", action="store_true", help=f"save the report to {RESULTS_FILE}")
    args = parser.parse_args()

    markdown = to_markdown(run(k=args.k))
    print(markdown)
    if args.write:
        RESULTS_FILE.parent.mkdir(parents=True, exist_ok=True)
        RESULTS_FILE.write_text(markdown, encoding="utf-8")
        print(f"Saved {RESULTS_FILE}")


if __name__ == "__main__":
    main()
