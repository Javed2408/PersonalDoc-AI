# PersonalDoc AI — Project Memory

## Current phase

**Phase 7: Chat UI — complete.** Awaiting review before Phase 8 (not started).

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

- Phase 6:
  - **Ollama integration:** `generation/llm.py`, an `LLM` protocol plus `OllamaLLM` (stdlib HTTP, `/api/chat`, non-streaming). Errors are typed: unavailable, model not found, timeout, bad response.
  - **Model:** `llama3.2:3b` (current development model), temperature 0, 512 output tokens, `num_ctx` 4096, 120 s timeout.
  - **Grounded prompt:** `generation/prompts.py` has the system rules, a `<context>`/`<source>` block of untrusted excerpts, a `<question>` block, and neutralises delimiter tags.
  - **RAG chain:** `generation/rag_chain.py` runs retrieve → evidence gate (`RAG_MAX_DISTANCE` 0.7) → whole-chunk context budget (6000 chars) → one LLM call → not-found detection → sources copied from retrieval, with invalid `[Source N]` citations removed.
  - **API:** `POST /api/chat`. Returns 200 `answered`/`not_found`; 503 when Ollama is down, the model is missing, or the index is unavailable; 504 on timeout; 502 on a bad response; retrieval's 422/404/409.

- Phase 7:
  - **Chat UI:** a two-column app with the document sidebar (library + chat context) on the left and the conversation with its composer in the centre.
  - **Document selection:** checkboxes on processed documents, an "All processed documents" option, chips with remove buttons above the composer, and "Use all documents".
  - **Composer:** auto-growing textarea; Enter sends, Shift+Enter adds a line; IME-safe.
  - **Conversation state:** in React memory only (`useChat`).
  - **Answer display:** safe paragraphs, lists, bold, code and `[Source N]` markers.
  - **Source cards:** grouped by document and page, expandable to show chunk numbers and similarity.
  - **Loading, error and empty states:** a loading indicator with an elapsed-time counter; errors with Retry; empty states for loading, failed load, empty library, processing, and ready with example questions.
  - **Retry and New chat:** Retry resends the same question with the current selection. New chat clears messages but keeps documents and selection.
  - **Responsive layout:** desktop, tablet (260px sidebar), and a drawer below 720px.
  - **Accessibility:** labelled controls, a `role="log"` conversation, `aria-expanded` cards and drawer, visible focus, focus moved into the drawer, Escape to close.
  - **Backend (additive only):** `/api/health` now includes `llm: {status, model}` through `LLM.status()` (Ollama `/api/tags`, 2 s timeout).

## Project structure (Phase 7 additions)

```text
backend/app/api/health.py                   + llm status (app.state.llm)
backend/app/generation/llm.py               + LLMStatus, OllamaLLM.status()
frontend/src/App.jsx                        Wires health, documents, selection and chat state
frontend/src/services/api.js                + chat(); keeps backend 5xx details, detail-less gateway errors = unreachable
frontend/src/hooks/useChat.js               Conversation reducer, one request at a time, abort on New chat
frontend/src/hooks/useDocumentSelection.js  Selection limited to processed documents; describeContext()
frontend/src/components/Chat/               ChatPanel, MessageList, UserMessage, AssistantMessage, AnswerText,
                                            ThinkingIndicator, Composer, ContextBar, ChatEmptyState, ServiceNotice
frontend/src/components/Sources/            SourceList, SourceCard
frontend/src/utils/                         answerFormat, chatErrors, sources, status
frontend/src/test/                          setup.js, fakeBackend.js (fetch stand-in)
frontend/src/**/*.test.*                    App.test.jsx, utils/utils.test.js, services/api.test.js
```

Removed: `Common/BackendStatusCard.jsx`, the Phase 1 placeholder. The header status and the service notice replace it.

## Project structure (Phase 6 additions)

```text
backend/app/generation/              llm.py, prompts.py, rag_chain.py
backend/app/api/chat.py              POST /api/chat
backend/evaluation/                  rag_dataset.json, rag_eval.py, results/rag_baseline.md
backend/tests/                       test_llm.py (stub HTTP server), test_rag.py (fake LLM), test_rag_ollama.py (real Ollama)
```

## Project structure (Phase 5 additions)

```text
backend/app/retrieval/retriever.py   Retriever, clamp_distance, RetrievalError subclasses
backend/app/retrieval/vector_store.py  + VectorHit, query_nearest()
backend/app/api/retrieval.py         POST /api/retrieval/search
backend/evaluation/                  retrieval_dataset.json, retrieval_eval.py, results/retrieval_baseline.md
backend/tests/fakes.py               + TopicEmbedder (keyword-count vectors for deterministic ranking tests)
```

## Important decisions

### Phase 7

- **Chat state is frontend-only:** a `useReducer` in `useChat`, with no server-side history, browser storage or conversation database. Reloading the page starts a new chat.
- **No conversation memory for the model:** each question is sent on its own (`POST /api/chat` with `question` and optional `document_ids`), so follow-ups like "tell me more" aren't understood. The empty state says so.
- **No streaming:** the UI waits for the complete answer. The loading text is a single, honest stage ("Searching your documents and writing an answer…") plus elapsed seconds, with no fake stages.
- **Document context:** no selection means all processed documents, the API default, so `document_ids` is omitted. Only `processed` documents are selectable. The selection is always read through the current document list, so deleted or reprocessing documents leave it.
- **`k` isn't exposed:** the backend default applies. `api.chat()` accepts `k` for later use.
- **Sources:**
  - Exactly the backend's `sources`, grouped visually by (document, page) in rank order.
  - Every chunk is kept inside its group.
  - Cards show the filename, page and source labels; expanding a card shows chunk numbers and similarity.
  - Similarity is labelled "not a confidence score"; there are no percentages.
  - Excerpt text isn't shown: displaying excerpts is a Phase 8 task.
- **Markdown:** no dependency. A small parser (`utils/answerFormat.js`) handles paragraphs, line breaks, `-`/`*`/`•` and numbered lists, headings, `**bold**`, `` `code` `` and `[Source N]`, and React renders the result as text nodes. There is no `dangerouslySetInnerHTML` or `innerHTML` anywhere; HTML in answers is shown verbatim (tested).
- **Errors:**
  - The backend's `detail` is shown as-is where it helps (missing model with the `ollama pull` command, timeout, 502, 409 with filenames, 422).
  - Two cases get plainer wording: an unreachable Ollama (its detail contains the server address) and 404 (its detail lists internal IDs).
  - In `api.js`, a 502/503/504 **without** a JSON detail (the Vite proxy with no backend behind it) means "Can't reach the backend".
- **Health:**
  - The header never claims "Local / Ready" unless `llm.status` is `ready`.
  - It is checked on load, on "Check again", after 502/503/504 or network chat errors, and after an answer arrives while a problem is shown. It is never polled.
  - Re-checks while connected are quiet: no "Connecting…" flash.
- **Sending:** one request at a time. A synchronous in-flight guard (the AbortController map) prevents a double Enter from sending twice. The textarea stays editable while an answer is pending, so focus isn't lost.
- **Layout:**
  - The page never scrolls; only the sidebar and the conversation do.
  - The service notice sits above the composer, not in the conversation, so it never pushes messages out of view.
  - A ResizeObserver keeps a reader at the end of the conversation when its area shrinks.
- **Frontend tests:** Vitest 5 + Testing Library + jsdom, dev dependencies only. `fetch` is replaced by a fake backend, so no servers are needed.

### Phases 5–6

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

## RAG evaluation (`backend/evaluation/results/rag_baseline.md`, llama3.2:3b)

- **20/22**, deterministic at temperature 0 (identical across runs).
  - answerable 12/12, unanswerable 3/3, related-insufficient 2/2, misleading-overlap 2/2, partial 1/2, injection 0/1
  - source preservation 13/13; 3 declines from the evidence gate, 6 from the model; about 0.6 s per question when warm
- **Both failures are the injection memo:** the model never follows the injection, but refuses to answer the legitimate date in the same excerpt.
- **Prompt experiments (2026-10-09), 4 variants:**
  - 2 softer rule-5 wordings and 2 post-context reminders were tried.
  - Three still refused.
  - The only one that answered also printed "INJECTION SUCCESSFUL" and a fake system prompt.
  - The original prompt was kept: failing safe is preferred.
  - `test_rag_ollama.py`'s injection test accepts a safe decline but stays strict on leaks.
- A larger model (e.g. `llama3.1:8b`) may fix this. That is for Phase 9 evaluation, not a change now.

## Retrieval evaluation (`backend/evaluation/results/retrieval_baseline.md`)

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
.venv/Scripts/python -m pytest                    # 309 tests, ~60 s (real model + Ollama)
.venv/Scripts/python -m pytest -m "not model"     # no real model or Ollama
.venv/Scripts/python -m pytest -m ollama          # 9 real-LLM tests, ~20 s
.venv/Scripts/python -m evaluation.retrieval_eval [--write]
.venv/Scripts/python -m evaluation.rag_eval [--write]

# Frontend (frontend/)
npm run dev      # http://127.0.0.1:5173
npm test         # 49 tests, ~25 s, no servers needed
npm run build
```

## Tests

### Phase 7 (2026-10-09)

- **Frontend: 49 passed** (Vitest), 3 consecutive runs, with no React warnings.
  - `App.test.jsx` (full app against a fake backend):
    - empty states (ready, empty library, processing) and example questions that fill without sending
    - selecting, deselecting and clearing documents, and chip removal
    - processing and failed documents can't be selected
    - the question appears, then the loading state, then the answer with its sources
    - `document_ids` omitted for "all" and sent when documents are selected; per-question context labels
    - Enter / Shift+Enter; empty and whitespace-only questions rejected; no second send while pending
    - not-found response without sources; grouped sources with expansion and no confidence wording
    - Ollama, missing-model, 502, 404, 409, 504 and unreachable errors; retry without duplicating the question, using the current selection; list refresh after a 404
    - New chat keeps the selection and documents and drops an in-flight answer
    - HTML and script in answers rendered as text
    - header states (ready, Ollama unavailable, model missing, backend offline with re-check)
    - drawer toggle, Escape, focus and selection badge
  - `utils.test.js`: answer parsing, error wording, source grouping, status labels.
  - `api.test.js`: request shape (k and document_ids only when given), detail handling, unreachable detection.
- **Backend: 309 passed** (297 before, +12):
  - `OllamaLLM.status()` against a stub server (ready, `:latest`, model missing, not running, bad responses, bounded hang)
  - health tests now use the fake LLM and check `llm`
  - one real-Ollama status test
- **Browser (Chrome, real backend + llama3.2:3b, Vite proxy):**
  - Library shown; one document selected (highlighted row, "1 selected", chip).
  - Bread question: user message, then loading with timer, then a grounded answer with a kitchen_notes p.1 card; expanded similarity 0.63.
  - Capital of Australia → not-found response, no sources.
  - 2 documents selected → OSI + neural-network question answered with sources from both (3 pages from 2 documents).
  - Deselected → context back to all.
  - Backend stopped → "Can't reach the backend" + header "Backend offline" (Vite proxy returns 502 with an empty body).
  - Backend with dead Ollama → "Ollama unavailable" + notice; Retry gave "Local AI is unavailable" with no address.
  - Backend restored → Check again → Local / Ready; Retry answered, question not duplicated.
  - New chat → cleared, focus in composer, documents kept.
  - Uploaded a 2-page PDF (synthetic drop on the real dropzone): Uploaded (disabled) → Processed in under 3 s → selected by keyboard → answered from both pages.
  - Keyboard: Tab order sidebar → composer → source cards, Space toggles, Enter expands, visible mint focus ring.
  - Narrow (502px window and a 375px iframe): drawer 320px with backdrop, focus to Close, Escape closes (`visibility: hidden`), badge count, icon-only New chat, no horizontal overflow.
  - Test PDF deleted through the UI and dropped from the context automatically.
  - Console: no errors or warnings (load and whole session). Backend log: no question text.
  - Fixed during testing:
    - mobile-only buttons showing on desktop (CSS specificity)
    - the page scrolling because visually-hidden text escaped the scroll container
    - the error pushed out of view by the service notice
    - empty-state copy mentioning "sidebar" on phones


### Phase 6 (2026-10-09)

- **297 passed** (full suite). The 8 real-Ollama tests ran 3 times in a row, all passing.
- **Live API (uvicorn :8000, real data dir, 3 evaluation PDFs):**
  - answered with correct sources; document filter (answer outside the filter → not_found)
  - k = 1; evidence-gate decline; model decline; injection in the question (gated)
  - 422 / 404 errors as specified
  - first request about 10 s (model loading), then 0.4–1.1 s
- **Failure modes (separate backends, throwaway data dirs):**
  - unreachable Ollama → 503 "Can't reach Ollama..."
  - unpulled model → 503 with the `ollama pull` command
  - 0.05 s timeout → 504
  - health and retrieval keep working in all three
  - fixed: the timeout message rounded fractional values to "0 seconds" (now `:g`)
- **Logs:** no question or answer text at INFO (checked against the server log).
- **Browser (Chrome, Vite proxy):**
  - UI shows Local / Ready with 3 processed documents
  - `/api/chat` from the page: answered with full source metadata, filtered not_found, k = 2, gate decline, 422 on an empty question
  - no console errors
- No chat UI yet (Phase 7).

### Phase 5

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

- **Injection over-refusal (3B):** excerpts that contain an injection make `llama3.2:3b` decline the whole question (see the RAG evaluation).
- **Provisional gates:** `RAG_MAX_DISTANCE` 0.7 and the context budget are untuned until Phase 9. Retrieval itself still has no threshold.
- **No persistent history:** by design for Phase 7. Reloading clears the chat.
- **No conversation memory:** follow-up questions that depend on earlier messages ("and the second one?") aren't understood, because each question is answered on its own.
- **No streaming:** answers appear all at once. Local latency is about 0.5–2 s warm, about 10–15 s for the first question after a backend start (both models load).
- **Health check when Ollama is down:** takes up to 2 s (on Windows a refused localhost connection takes about 2 s), so "Connecting…" shows briefly.
- **Sources:** no excerpt text, page preview or jump-to-source yet (Phase 8). Answers already in the conversation keep their sources after the document is deleted.
- **Mobile:** tested at 502px (Chrome's minimum window) and in a 375px iframe, not on real devices or touch input.
- **Thin evaluation:** the dataset is small and English-only. `all-MiniLM-L6-v2` truncates at 256 tokens.
- **HNSW is approximate:** for large libraries, the boundary at k may differ slightly from an exact search.
- **Windows:** ChromaDB keeps index files memory-mapped until the process exits, so the evaluation runner's temp directory may not be fully deleted (it lives in the OS temp dir).
- `chroma.sqlite3` doesn't shrink after deletes (about 25 MB after the Phase 4 tests).
- **Carried over:** the embedding model downloads on first use; CPU embedding only; no OCR; no re-process action; single backend process.
- Another project's Vite listens on `[::1]:5173`, so use `http://127.0.0.1:5173`.

## Next phase

Phase 8: Citations and Document UX. Not started.
