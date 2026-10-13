# PersonalDoc AI — Project Memory

## Current phase

**Phase 8: Citations and Document UX — complete**, plus a follow-up: failed-document recovery. Awaiting review before Phase 9 (not started).

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
- Phase 8:
  - **Source excerpts:** each source card lists every retrieved chunk of its page separately, with the verbatim text as a quote, the chunk number and similarity, and a note that it is an excerpt, not the whole page.
  - **Inline citations:** `[Source N]` becomes a button when the answer has a source labelled "Source N". Clicking it opens the card and focuses and marks that exact chunk.
  - **PDF preview:** "PDF p.N" opens the stored PDF in the browser's own viewer at `#page=N` in a new tab, through the new read-only `GET /api/documents/{id}/file`.
  - **Deleted documents:** existing answers keep their excerpts; the PDF link is replaced by "Deleted" plus an explanation.
- Phase 8 follow-up, failed-document recovery:
  - **API:** `POST /api/documents/{document_id}/reindex` sends a `failed` document back through the existing worker under the same ID, file and name. It returns 202 with the document, now `processing`; 409 for `uploaded`, `processing` or `processed`; 404 if unknown; 422 for a malformed ID.
  - **UI:** "Retry processing" on failed documents only. It is disabled while pending, shows Processing… and then the final result, and shows a readable inline error if the request fails.
  - **Not supported:** re-indexing healthy `processed` documents.

## Project structure (Phase 8 follow-up additions)

```text
backend/app/api/documents.py                 + POST /{document_id}/reindex (DocumentIdPath, 202)
backend/app/services/processing_service.py   + retry_failed(); _fail() records "failed" even if chunk cleanup fails
backend/app/services/document_store.py       + update_if_status(): check + change in one locked step
backend/app/services/document_service.py     + DocumentStateError (409); delete cleans chunks/vectors again after removing metadata
backend/tests/test_document_reindex.py       Retry endpoint, duplicates, failures, delete races, restart
frontend/src/services/api.js                 + reindexDocument(id)
frontend/src/hooks/useDocuments.js           + retries state, retryProcessing() with a synchronous in-flight guard
frontend/src/components/Documents/DocumentItem.jsx  Retry button + inline error on failed documents
frontend/src/test/fakeBackend.js             + reindex route (acceptFailedOnly)
frontend/src/documentRetry.test.jsx          Retry UI tests
```

## Project structure (Phase 8 additions)

```text
backend/app/api/documents.py               + GET /{document_id}/file (FileResponse, safe headers, ID pattern)
backend/app/services/document_service.py   + get_file(): metadata lookup, fixed <id>.pdf name, stored_path() guard
backend/tests/test_document_file.py        PDF endpoint: content, headers, range, 404s, 422s, traversal, tampering, no paths
backend/tests/test_rag.py                  + source text/metadata == stored chunk, response shape unchanged
frontend/src/components/Sources/SourceCard.jsx   Chunks with excerpts, PDF link / Deleted, citation target + focus
frontend/src/components/Chat/AnswerText.jsx      [Source N] -> button only when that label exists, else raw text
frontend/src/components/Chat/AssistantMessage.jsx  Citation target state per answer
frontend/src/utils/sources.js              + citationTargets() (label -> source), sourceElementId()
frontend/src/services/api.js               + documentFileUrl(id, page)
frontend/src/citations.test.jsx            Phase 8 frontend tests
```

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

### Phase 8 follow-up: failed-document recovery

- **Scope:** only `failed -> processing`.
  - Processed documents aren't re-indexed, because a failed run removes the document's vectors (`_fail`), which would make a working document unsearchable.
  - Safe re-indexing of processed documents needs the old vectors kept until a new run succeeds. It remains a future requirement (PRD FR-10).
  - Changing `CHUNK_SIZE`/`CHUNK_OVERLAP` doesn't reprocess processed documents.
- **No second pipeline:** `DocumentProcessor.retry_failed()` calls the existing `submit()`, so a retry runs the same `_process` → `process_pdf` → chunk store → `DocumentIndexer` path as an upload.
  - The indexer diffs against stored vectors (keyed by `chunk_id`), so a retry never duplicates vectors and removes stale leftovers.
  - ID, stored file, name and `created_at` are unchanged.
- **Duplicate guard:** `JsonDocumentStore.update_if_status(id, "failed", status="processing")` checks and switches under the store's lock. Of N simultaneous requests exactly one gets 202 and queues a job; the rest get 409.
  - The single worker thread also means two jobs for one document never overlap.
  - A retry goes straight to `processing`, not `uploaded`, so a retry queued behind another document already shows Processing….
  - Startup recovery re-queues it like any interrupted document; `failed` documents are never retried automatically.
- **Delete during a retry:** delete still removes metadata last, then removes chunks and vectors once more (`_remove_late_writes`).
  - Every worker write (chunk file, each vector batch) is followed by a metadata check: the indexer's per-batch `is_cancelled`, the final `update(processed)`, or `_fail`'s update. If the document is gone, the worker discards its data.
  - `update()` never recreates a record.
  - So a write lands either before the delete's second cleanup (removed by it) or after the metadata is gone (removed by the worker).
- **Failure handling:** `_fail` removes vectors, then the chunk file (unless only embedding or vector storage failed), then records `failed`. A chunk file that can't be removed no longer stops the status update; before, the document stayed `processing` with no job, and every retry got 409.
- **Errors:** `DocumentStateError` → 409, with `DocumentNotProcessedError` as a subclass (its mapping is unchanged). Messages are "This document is already being processed." and "This document is already processed. Reprocessing a processed document isn't supported in this version."
- **Frontend:**
  - `retryProcessing(id)` in `useDocuments` has a synchronous `useRef` guard, and the button is disabled while pending, so a double click sends one request.
  - On 202 the returned document (`processing`) replaces the row, and the existing poll runs until the result. It bumps `mutations`, so an older list response can't overwrite it.
  - On 404/409 the list refreshes to show the real state. Any error shows inline as "Couldn't retry: <detail>" (`role="alert"`), and is dropped once the document leaves `failed`.

### Phase 8

- **API changes (additive only):**
  - `GET /api/documents/{document_id}/file` is the only new endpoint.
  - `/api/chat`, its schema, retrieval, the evidence gate and the prompt are unchanged.
- **Excerpt strategy:**
  - `/api/chat` already returned each source's `text`, copied from retrieval, which reads the chunk stored in ChromaDB at indexing time. It equals the Phase 3 chunk file's text; a test compares them via `/api/documents/{id}/chunks`.
  - So no new storage and no extra request per source.
  - The frontend shows `text` verbatim (`white-space: pre-wrap`, never HTML) and never fills in missing text: an empty `text` shows "No text was returned for this source".
- **Citation mapping:**
  - `citationTargets()` maps N to the source whose backend `label` is "Source N", so it doesn't depend on array position.
  - The backend already strips out-of-range `[Source N]` (`remove_invalid_citations`). The frontend still renders any marker without a matching label, or any malformed variant (`[Source]`, `[Src 1]`, `[Source 1a]`, `[Source 1, 2]`), as the original text.
  - Each chunk's DOM id is `source-<message id>-<chunk_id>`, both stable, so identical chunks in different answers never collide.
  - Citations aren't claimed to prove every sentence; the README says so.
- **Navigation:**
  - A click sets a per-answer `{chunkId, request}` target.
  - The card holding that chunk opens; the chunk is focused (`tabIndex=-1`), then scrolled into view instantly with `block: 'nearest'`.
  - Highlight: a steady outline plus a visible "Selected from the answer" tag, with no animation and not colour alone.
  - Smooth scrolling was dropped: Chrome doesn't animate in a background or occluded window, and the jump never happened in browser testing.
- **Grouping:** cards are grouped by (document, page) in rank order, and every chunk keeps its own row, label, number, similarity and excerpt.
- **PDF preview strategy:**
  - Native browser viewer in a new tab, `href = /api/documents/{id}/file#page=N`, `target=_blank`, `rel="noopener noreferrer"`. No PDF.js or other dependency.
  - Chrome verified to open at page N. Edge and Firefox support `#page`; others may open at page 1, so the page is always printed on the card.
- **PDF endpoint safety:**
  - The ID must match `^[0-9a-f]{32}$` (422), and the document must exist in metadata (404).
  - The stored filename must be exactly `<id>.pdf` (500 if the metadata was tampered with), resolved through `stored_path()`, which refuses anything outside `documents_dir`; a missing file gives 404.
  - Headers: `application/pdf`, `Content-Disposition: inline` with the original name (RFC 5987-encoded when needed), `X-Content-Type-Options: nosniff`, `Cache-Control: no-store`, `Cross-Origin-Resource-Policy: same-site`.
  - No CSP `sandbox`, because it stops built-in PDF viewers. Range requests work (206).
- **Deleted documents:** `App` passes `isDocumentAvailable(id)`, true while the library is loading or failed, false when the loaded list lacks the ID. Unavailable sources show "Deleted" and an explanation instead of the link; their excerpts stay. A stale URL opened directly gets the readable 404 detail.
- **Source list layout:** a vertical stack of compact rows instead of the Phase 7 grid, so excerpts get the full reading width (and the full width on phones).

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
.venv/Scripts/python -m pytest                    # 357 tests, ~60–90 s (real model + Ollama)
.venv/Scripts/python -m pytest -m "not model"     # no real model or Ollama
.venv/Scripts/python -m pytest -m ollama          # 9 real-LLM tests, ~20 s
.venv/Scripts/python -m evaluation.retrieval_eval [--write]
.venv/Scripts/python -m evaluation.rag_eval [--write]

# Frontend (frontend/)
npm run dev      # http://127.0.0.1:5173
npm test         # 81 tests, ~30 s, no servers needed
npm run build
```

## Tests

### Phase 8 follow-up: failed-document recovery (2026-10-13)

- **Backend: 357 passed** (331 before, +26), full suite including real-model and Ollama tests. `test_document_reindex.py` ran 5 times in a row with no failures.
  - accepted retry keeps ID, file, name and schema; failed → processed once the cause is fixed (searchable, 2 vectors, one document)
  - leftover and obsolete vectors replaced with no duplicates
  - 7 malformed IDs → 422 (document untouched); unknown → 404; uploaded and processing → 409 with nothing extra queued; processed → 409 with no re-embedding
  - repeated retries (before and during the job) and 8 simultaneous requests queue exactly one job; the store primitive is atomic across 16 threads
  - retry failing again: reason recorded, no vectors, retryable; failing mid-indexing: partial batch removed; unreadable PDF: same error, no chunks
  - failure still recorded when the chunk file can't be removed (this test failed against the previous `_fail`)
  - delete while the retry is queued, during indexing, or right before a failing embed: nothing recreated
  - delete whose metadata removal lands after the retry finished: second cleanup removes it all
  - accepted-but-not-run retry resumes after a restart; failed documents aren't retried on restart
- **Frontend: 81 passed** (69 before, +12), 3 runs, no React warnings; `npm run build` OK.
  - `documentRetry.test.jsx` (10): only failed rows have the button; POST to `/api/documents/{id}/reindex` with no body; pending state disables it, so a second click sends nothing; Processing… then Processed and selectable, with chat sending its ID; failing again shows the reason and re-enables the button; 500 detail and unreachable backend shown inline; 409 refreshes to the real state without an alert; 404 drops the row; selection and chat unaffected.
  - `api.test.js` (+2): request shape and 409 detail.
- **Live (throwaway `DATA_DIR`, uvicorn :8765, Vite :5180 → :8765, Chrome, real model + llama3.2:3b):**
  - With `EMBEDDING_DEVICE=cuda:9` (torch has no CUDA here): the valid PDF failed with "The embedding model could not be loaded…" and the corrupted one with "The PDF could not be read…".
  - On that server: 422 malformed, 404 unknown, 409 while still processing. A retry while still broken got 202, an immediate repeat 409; one "Retrying" log line, failed again, 0 vectors.
  - Restarted with the right device: both documents still `failed` (no automatic retry).
  - In the UI, Retry processing on retry_notes.pdf → Processing… (error and button gone) → Processed, 2 pages · 2 chunks.
  - A question was answered from it, with p.2 and p.1 source cards. Retrying broken.pdf → Failed again with the same reason and the button back.
  - A processed document gave 409 with the explanation. No console errors; no question text in the backend log.

### Phase 8 (2026-10-09)

- **Backend: 331 passed** (309 before, +22):
  - `test_document_file.py` (21): stored bytes, content type and safe headers; encoded non-ASCII and quoted names; range 206; preview before processing; unknown 404; deleted 404; missing-file 404; 7 malformed IDs → 422; 8 traversal URLs never reach a file; tampered metadata can't redirect to another document's file; no data paths in headers or errors.
  - `test_rag.py` (+1): every chat source's `text`, page, chunk index and filename equal the stored chunk, and the source schema is unchanged.
- **Frontend: 69 passed** (49 before, +20), 3 consecutive runs, no React warnings.
  - `citations.test.jsx` (19):
    - excerpts expand and collapse and are verbatim quotes; same-page chunks are listed separately; no invented text
    - citation mapping by label even with shuffled sources; a click focuses the exact chunk and moves on the next click; citations scoped per answer
    - 6 malformed or out-of-range markers stay text; answers without citations still list sources
    - similarity wording; PDF link href, page and rel; link and toggle are separate controls
    - deleted before the answer and deleted during the conversation; HTML in answers and excerpts stays text
  - `utils.test.js` (+1): label-based mapping and DOM ids.
- **Browser (Chrome, real backend + llama3.2:3b):**
  - Hidden-layers + weights question: answered without `[Source N]` markers; 3 cards shown anyway.
  - Expanded excerpt identical to the stored chunk from `/chunks` (464 chars, same id, page and file).
  - "PDF p.3" opened ml_handbook.pdf in Chrome's viewer at **3 / 3**, showing that page's text.
  - Uploaded a test PDF whose page 1 split into 3 chunks. A question with requested citations got `[Source 1–4]` buttons; page 1's card held Sources 1–3 separately.
  - Clicking Source 2 with the card collapsed opened it, scrolled 207 → 735, focused chunk `…-00001` (fully visible) and marked it "Selected from the answer". The first attempt (smooth scroll) left it out of view; fixed to an instant jump.
  - Asked the model to echo `[Source 9] [Source] [Src 1] [Source 1]`: the backend removed `[Source 9]`, `[Source]` and `[Src 1]` stayed text, `[Source 1]` became a button.
  - Deleted the test PDF in the UI: all 3 of its cards switched to "Deleted", with no PDF links, a notice, and excerpts kept. Its old URL returned `{"detail":"Document not found. It may have been deleted."}`.
  - Live endpoint: headers as above through the Vite proxy; `..%2F`, `../../`, `NOT-AN-ID` and an unknown ID were rejected (404/404/422/404).
  - 375px iframe: citation jump, excerpt and PDF link usable, no horizontal overflow.
  - No console errors or warnings; no document or question text in the backend log.
  - The Chrome window was occluded (`visibilityState: hidden`) during testing, and the page reloaded once (navigation type `reload`; Vite logged nothing and no app code reloads). Cause not identified.


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
- **PDF page navigation:** relies on the browser's viewer honouring `#page=N` (verified in Chrome only). There's no in-app viewer, no text highlighting inside the PDF, and phones may download or open the PDF externally.
- **Excerpt = what the model saw:** if `CHUNK_SIZE` were set above `RAG_MAX_CONTEXT_CHARS`, the single best chunk would be shortened (with " …") before reaching the model, and the excerpt would show that shortened text. It can't happen with the defaults (1000 vs 6000).
- **Citations are the model's choice:** `llama3.2:3b` often writes no `[Source N]` at all, or "Source 1" without brackets (plain text). Cards are always shown; a citation doesn't prove that a specific sentence is supported.
- **Stale links:** the PDF link is disabled from the client's document list; a PDF deleted from another tab only shows as deleted after the list refreshes (opening it then gives the 404 detail).
- **Mobile:** tested at 502px (Chrome's minimum window) and in a 375px iframe, not on real devices or touch input.
- **Thin evaluation:** the dataset is small and English-only. `all-MiniLM-L6-v2` truncates at 256 tokens.
- **HNSW is approximate:** for large libraries, the boundary at k may differ slightly from an exact search.
- **Windows:** ChromaDB keeps index files memory-mapped until the process exits, so the evaluation runner's temp directory may not be fully deleted (it lives in the OS temp dir).
- `chroma.sqlite3` doesn't shrink after deletes (about 25 MB after the Phase 4 tests).
- **Carried over:** the embedding model downloads on first use; CPU embedding only; no OCR; single backend process.
- **Re-index is for failed documents only:**
  - Processed documents can't be re-indexed.
  - Changed chunk settings only apply to new uploads, retried documents, and documents processed or re-indexed by startup recovery.
- **Single-process assumption:** the retry guard and delete safety rely on one backend process (in-process locks, one worker thread). Several uvicorn workers or processes on one data dir could queue duplicate jobs.
- **Unwritable metadata:** if `documents.json` can't be written, a failure can't be recorded. The document stays `processing` until the next start (startup recovery re-queues it).
- **Orphaned data on store errors (cleanup is best-effort):**
  - If ChromaDB fails while `_fail` removes a failed run's vectors, they stay with the still-listed document. The next retry's indexer replaces or removes them, and deleting the document removes them.
  - If removing chunks or vectors fails after the document record is gone, nothing removes them later. This covers the delete's second cleanup (`_remove_late_writes`) and the worker's `_discard`. Orphaned chunk files or vectors then stay on disk.
  - None of this is ever retrieved, because retrieval reads only `processed` documents.
- **Queued vs running:** a retry waiting behind another document already shows Processing….
- **Chat empty state:** with only failed documents, the chat area still says "Getting your documents ready…" (Phase 7 wording).
- **Stale doc:** Architecture.md's `/api/chat` example (with `conversation_id` and `document`/`page`/`excerpt` sources) predates the real schema. It was left untouched.
- **Port 5173 is shared:** the separate `unified-dashboard` project also runs Vite on port 5173. Never stop it.
  - It was last observed on `127.0.0.1:5173` (2026-10-13); earlier notes recorded `[::1]:5173`.
  - While it runs, PersonalDoc's `npm run dev` may not get port 5173. Open the URL Vite prints, or choose a free port (`npm run dev -- --host 127.0.0.1 --port 5180`).

## Next phase

Phase 9: Evaluation and Reliability. Not started.
