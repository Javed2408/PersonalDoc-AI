"""Question -> retrieval -> grounded prompt -> local LLM -> answer + sources.

Steps:
  1. Retrieve top-k chunks with the existing Retriever (validation and document filters live there).
  2. Evidence gate: drop chunks with cosine distance above `max_distance`. If none are left,
     answer "not found" without calling the LLM: it is never handed unrelated text as "evidence".
  3. Context budget: keep evidence chunks in rank order while they fit in `max_context_chars`.
     Chunks are kept whole; a chunk that doesn't fit is skipped (a smaller, lower-ranked one may
     still fit). Only if even the best chunk is larger than the whole budget is it shortened,
     at a word boundary.
  4. One LLM call with the grounded prompt.
  5. If the model says the excerpts don't answer the question, report "not found".
     Otherwise return its answer with exactly the chunks it was given as sources.
"""

import logging
import re
from collections.abc import Sequence
from dataclasses import dataclass

from app.generation.llm import LLM
from app.generation.prompts import NOT_FOUND_ANSWER, SYSTEM_PROMPT, build_user_prompt, source_label
from app.models.schemas import ChatSource, RetrievalResult
from app.retrieval.retriever import Retriever

logger = logging.getLogger(__name__)

_CITATION = re.compile(r"\[\s*Source\s+(\d+)\s*\]", re.IGNORECASE)
_NOT_FOUND_CORE = "couldn't find enough information in the selected documents"


@dataclass(frozen=True)
class RagAnswer:
    answer: str
    status: str  # "answered" | "not_found"
    sources: list[ChatSource]
    model: str


def fit_context(results: Sequence[RetrievalResult], max_chars: int) -> list[RetrievalResult]:
    """Pick whole chunks, best first, while their text fits in the budget."""
    selected: list[RetrievalResult] = []
    used = 0
    for result in results:
        if used + len(result.text) <= max_chars:
            selected.append(result)
            used += len(result.text)
    if not selected and results:
        best = results[0]
        cut = best.text[:max_chars]
        if " " in cut:
            cut = cut[: cut.rfind(" ")]
        selected.append(best.model_copy(update={"text": cut.rstrip() + " …"}))
    return selected


def is_not_found(answer: str) -> bool:
    normalized = answer.lower().replace("’", "'").replace("could not", "couldn't")
    return _NOT_FOUND_CORE in normalized


def remove_invalid_citations(answer: str, source_count: int) -> str:
    """Drop [Source N] markers that point at no source the model was given."""
    return _CITATION.sub(lambda m: m.group(0) if 1 <= int(m.group(1)) <= source_count else "", answer).strip()


class RagChain:
    def __init__(self, retriever: Retriever, llm: LLM, max_distance: float, max_context_chars: int) -> None:
        self._retriever = retriever
        self._llm = llm
        self._max_distance = max_distance
        self._max_context_chars = max_context_chars

    @property
    def model_name(self) -> str:
        return self._llm.model_name

    def answer(self, question: str, k: int | None = None, document_ids: Sequence[str] | None = None) -> RagAnswer:
        # RetrievalError (bad input, unknown/unprocessed documents, unavailable index) propagates.
        results = self._retriever.search(question, k=k, document_ids=document_ids)

        evidence = [r for r in results if r.distance <= self._max_distance]
        if not evidence:
            logger.info("RAG: %d retrieved, none within distance %.2f -> not found", len(results), self._max_distance)
            return self._not_found()

        context = fit_context(evidence, self._max_context_chars)
        prompt = build_user_prompt(question, context)
        # LLMError (unavailable, missing model, timeout, bad response) propagates.
        raw_answer = self._llm.generate(SYSTEM_PROMPT, prompt)

        if is_not_found(raw_answer):
            logger.info("RAG: model reported insufficient evidence (%d sources given)", len(context))
            return self._not_found()

        logger.info(
            "RAG: %d retrieved, %d evidence, %d in context (%d chars), answered",
            len(results), len(evidence), len(context), sum(len(r.text) for r in context),
        )
        return RagAnswer(
            answer=remove_invalid_citations(raw_answer, len(context)),
            status="answered",
            sources=[self._source(number, result) for number, result in enumerate(context, start=1)],
            model=self._llm.model_name,
        )

    def _not_found(self) -> RagAnswer:
        return RagAnswer(answer=NOT_FOUND_ANSWER, status="not_found", sources=[], model=self._llm.model_name)

    @staticmethod
    def _source(number: int, result: RetrievalResult) -> ChatSource:
        return ChatSource(
            label=source_label(number),
            chunk_id=result.chunk_id,
            document_id=result.document_id,
            original_filename=result.original_filename,
            page_number=result.page_number,
            chunk_index=result.chunk_index,
            text=result.text,
            distance=result.distance,
            similarity=result.similarity,
        )
