# PersonalDoc AI — Project Memory

## Current phase

**Phase 5: Retrieval — complete.** Awaiting review before Phase 6.

## Completed

- Phase 1: FastAPI + React/Vite foundation, `GET /api/health`.
- Phase 2: PDF upload and validation, local storage, JSON metadata, list and delete, document library UI.
- Phase 3: pypdf page extraction, recursive chunking (1000/150), chunk metadata, background processing and statuses.
- Phase 4: local `all-MiniLM-L6-v2` embeddings (384 dimensions), persistent ChromaDB (`personaldoc_chunks`, cosine), idempotent indexing, delete cleanup.
- Phase 5:
  - **Query embedding:** the existing `Embedder`; the model is loaded once and shared with indexing.
  - **Similarity retrieval:** `ChromaVectorStore.query_nearest`, one ChromaDB query per search on the shared client.
  - **Top-k retrieval:** `retrieval/retriever.py` validates, filters, embeds, queries, clamps and orders scores, and builds results.
  - **Document filtering:** all processed documents, or the listed ones (validated).
  - **Retrieval API:** `POST /api/retrieval/search`.
  - **Structured retrieval results:** `RetrievalRequest`, `RetrievalResult` and `RetrievalResponse` schemas.
  - Evaluation set, runner and baseline report in `backend/evaluation/`.

## Project structure (Phase 5 additions)

```text
backend/app/retrieval/retriever.py   Retriever, clamp_distance, RetrievalError subclasses
backend/app/retrieval/vector_store.py  + VectorHit, query_nearest()
backend/app/api/retrieval.py         POST /api/retrieval/search
backend/evaluation/                  retrieval_dataset.json, retrieval_eval.py, results/retrieval_baseline.md
backend/tests/fakes.py               + TopicEmbedder (keyword-count vectors for deterministic ranking tests)
```

## Important decisions

- **Default k:** 4 (`RETRIEVAL_TOP_K`). Requests may ask for up to `RETRIEVAL_MAX_K` (20, capped at 100). Fewer chunks than k means fewer results; results are never padded.
- **Score semantics:**
  - `distance` is ChromaDB's cosine distance, `1 − cos_sim`, in the range 0..2. Lower is more similar.
  - `similarity` is exactly `1 − distance`.
  - Both are clamped to the valid range, because float32 can return −2e-7 for an identical vector.
  - Results are sorted by (distance, chunk_id), so exact ties are stable across runs.
  - No "confidence" score.
- **Threshold:** off by default (`RETRIEVAL_MAX_DISTANCE` empty). Top-k always returns the nearest chunks; the distance tells callers how relevant they are.
- **Filtering strategy:**
  - Only `processed` documents are ever searched, via a ChromaDB `where` on `document_id` (`$in` for several). This excludes partially indexed, failed and orphaned vectors.
  - With a filter: duplicate IDs are collapsed; unknown IDs give 404; documents that aren't processed give 409; malformed IDs give 422.
- **Result schema:** `rank`, `chunk_id`, `document_id`, `original_filename`, `page_number`, `chunk_index`, `start_char`, `char_count`, `text`, `distance`, `similarity`. No storage paths. The response also echoes `query`, `k`, `document_ids` and `result_count`.
- **No answer generation anywhere.** An empty library returns `[]` without embedding the query.
- **Logging:** INFO shows only k, filter size, result count and best distance. Query text and per-result document, page and chunk are logged at DEBUG only.

## Evaluation (`backend/evaluation/results/retrieval_baseline.md`)

- **Dataset:**
  - 3 documents (ML handbook, kitchen notes, network guide), 9 pages, 9 chunks
  - "layers" appears in all three documents and "training" in two
  - 15 questions: 8 direct or paraphrased, 4 with shared vocabulary, 3 unanswerable (one ML-adjacent)
- **Observed:**
  - **Hit@1 = 100%, Hit@4 = 100%, MRR = 1.00** (12 answerable questions)
  - All shared-vocabulary questions ranked the right document and page first
  - Best distance for answerable questions: 0.23–0.55 (median 0.36). For unanswerable ones: 0.77–0.90.
  - The weakest correct match was 0.55, on a page that mixes cake and mayonnaise.
- **Limitations:**
  - The corpus is tiny, with single-chunk pages, so it's easy.
  - The gap between answerable and unanswerable distances suggests a cut-off around 0.65, but this is not enough evidence. Phase 9 needs a larger set, with multi-chunk pages and near-duplicate content.

## Commands

```bash
# Backend (backend/)
.venv/Scripts/python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
.venv/Scripts/python -m pytest                    # 230 tests, ~31 s
.venv/Scripts/python -m pytest -m "not model"     # 213 tests, no real model
.venv/Scripts/python -m evaluation.retrieval_eval [--write]

# Frontend (frontend/)
npm run dev      # http://127.0.0.1:5173
```

## Tests

- **230 passed.** The full suite ran 3 times in a row with no failures; the retrieval tests alone ran 5 times.
- **Retrieval API tests (50, keyword embedder):**
  - topic ranking and distance ordering, similarity = 1 − distance
  - k = 1, 2 and 4, the default, fewer chunks than k, the maximum, and invalid k
  - empty, whitespace-only, missing and oversized queries
  - filtering: none, one document, several, duplicates, a document with no matching content, unknown, malformed and unprocessed IDs, partially indexed documents excluded, deleted documents gone
  - full metadata, no storage leaks, duplicate filenames
  - one embedding and one vector query per search, 503 on embedding failure, query text not logged
  - restart without re-embedding, stable tie order, distance clamping, the optional threshold
- **Vector store query tests (4)** and **config tests (+6)**.
- **Real model:** e2e retrieval (9 tests, covering ranking, relative distances, filtering, unrelated questions, and restart without re-embedding) plus the evaluation-set test.
- **Regression:** all Phase 1–4 tests unchanged and passing.
- **Browser (Chrome):**
  - uploaded the 3 evaluation PDFs; all went Processing… → Processed (3 pages · 3 chunks each)
  - searched through the API from the page: all documents, k = 2, a document filter, an unknown ID (404), an empty query (422), k = 50 (422), full metadata, 16–19 ms per query
  - deleting a document removed it from the UI and from search results
  - after a backend restart, retrieval used the existing vectors with no re-indexing
  - no console errors; query text absent from the INFO logs

## Known issues

- **No threshold:** questions the documents can't answer still return the k nearest chunks, with large distances. Phase 6 must use the distances, or ignore weak context, and fall back to "not found".
- **Thin evaluation:** the dataset is small and English-only. `all-MiniLM-L6-v2` truncates at 256 tokens.
- **HNSW is approximate:** for large libraries, the boundary at k may differ slightly from an exact search.
- **Windows:** ChromaDB keeps index files memory-mapped until the process exits, so the evaluation runner's temp directory may not be fully deleted (it lives in the OS temp dir).
- `chroma.sqlite3` doesn't shrink after deletes (about 25 MB after the Phase 4 tests).
- **Carried over:** the model downloads on first use; CPU embedding only; header status is checked only on page load; no OCR; no re-process action; single backend process.
- Another project's Vite listens on `[::1]:5173`, so use `http://127.0.0.1:5173`.

## Next phase

Phase 6: Local LLM and RAG Generation. Not started.
