# PersonalDoc AI — Project Memory

## Current phase

**Phase 3: PDF Extraction and Chunking — complete.** Awaiting review before Phase 4.

## Completed

- Phase 1: FastAPI app factory, env settings, `GET /api/health`, React/Vite shell with backend status.
- Phase 2: PDF upload, validation and local storage; JSON metadata; list and delete; frontend document library.
- Phase 3:
  - **PDF extraction:** pypdf, one `PageText` per page, 1-based page numbers, normalised whitespace.
  - **Page-level text:** empty or graphics-only pages are kept as empty text.
  - **Recursive chunking:** each page is chunked separately.
  - **Chunk metadata:** IDs, page, index, offsets.
  - **Processing states:** `uploaded → processing → processed | failed`, run on a background worker. Interrupted jobs resume at startup.
  - `GET /api/documents/{id}/chunks` to inspect chunks. Returns 409 until processed.
  - Frontend shows the new statuses, page and chunk counts, and failure reasons, and polls while anything is pending.

## Project structure

```text
backend/app/
  main.py                        create_app(settings?): stores, services, processor, lifespan (storage + resume)
  config.py                      + CHUNK_SIZE, CHUNK_OVERLAP (validated overlap < size), chunks_dir
  api/documents.py               upload (then submit for processing), list, chunks, delete
  ingestion/loader.py            extract_pages(path) -> list[PageText]; ExtractionError(message)
  ingestion/splitter.py          RecursiveTextSplitter -> TextChunk(text, start)
  ingestion/pipeline.py          process_pdf(...) -> ProcessedDocument(page_count, chunks)
  services/document_service.py   upload/delete/get_chunks; stored_path()
  services/processing_service.py DocumentProcessor (1-thread executor, submit/resume_pending/wait_until_idle)
  services/document_store.py     JSON metadata (+ update())
  services/chunk_store.py        data/chunks/<document_id>.json
  services/json_files.py         write_json_atomic (shared)
backend/tests/                   pdf_factory.py builds test PDFs in memory; test_ingestion, test_processing
frontend/src/hooks/useDocuments.js  + silent polling while uploaded/processing; stale-response guard
```

## Important decisions

- **PDF library:** `pypdf==6.19.0`, which has no dependencies. The file is read into memory and closed before parsing, so a document can be deleted mid-processing on Windows. One bad page becomes an empty page instead of failing the document.
- **Splitter:** a local reimplementation of LangChain's `RecursiveCharacterTextSplitter` algorithm (separators `\n\n`, `\n`, space, character). `langchain-text-splitters` was rejected because it pulls in langchain-core and about 30 packages, including langsmith. It works on character offsets, so every chunk is an exact slice of its page text.
- **Chunk size / overlap:** 1000 / 150 characters, set by `CHUNK_SIZE` / `CHUNK_OVERLAP`. Overlap happens at split boundaries, so it is at most 150. With line-wrapped PDF text it is about one line (~80 chars).
- **Page boundaries:** pages are chunked independently, so each chunk has exactly one `page_number` and nothing spans pages. `start_char` is the offset within that page's text.
- **Chunk metadata:** `chunk_id` (`<document_id>-<index:05d>`, deterministic so re-processing is idempotent for Phase 4), `document_id`, `original_filename`, `page_number`, `chunk_index` (document-wide, 0-based), `start_char`, `char_count`, `text`.
- **Chunk persistence:** one JSON file per document in `data/chunks/`, written atomically. It records the `chunk_size` and `chunk_overlap` used. The chunk store is the boundary Phase 4 replaces or feeds.
- **Document metadata:** added `page_count`, `chunk_count` and `processing_error`, all optional, so Phase 2 metadata files still load.
- **Failures:** the PDF is always kept, and the status becomes `failed` with a safe message:
  - corrupted
  - password-protected
  - no extractable text (scanned)
  - no pages
  - file missing
  - chunks unsaveable
  - unexpected error (logged with traceback; generic message to users)
- **Processing:** a single-worker thread pool keeps uploads fast and processes documents in order. A delete during processing leaves no orphaned chunks. Already-processed documents are not re-processed on restart.
- **List ordering:** newest first, ties broken by insertion order. This fixed a real bug: same-millisecond uploads could come back in the wrong order.

## Commands

```bash
# Backend (backend/)
.venv/Scripts/pip install -r requirements-dev.txt
.venv/Scripts/python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
.venv/Scripts/python -m pytest

# Frontend (frontend/)
npm install && npm run dev      # open http://127.0.0.1:5173
npm run build
```

## Tests

- **102 passed** across: config 8, documents (Phase 2 plus a tie-order regression) 42, health 3, ingestion 31, processing 18. The suite ran 25 times in a row with no failures.
- **Extraction tests:**
  - normal and multi-page text, page numbers
  - empty and graphics-only pages, special characters
  - corrupted and truncated PDFs, missing files, password protection
  - file released after reading, text normalisation
- **Chunking tests:**
  - chunk size limit and fill level, overlap of 150 or less with matching text
  - zero overlap, full coverage, paragraph preference, character fallback
  - determinism, invalid settings
  - one chunk per page on the quality document, chunks never crossing pages, sequential and unique IDs
- **Processing tests:**
  - status flow (observed `processing`), chunks endpoint and metadata, configured chunk sizes, duplicate filenames
  - failures: corrupted, no-text, unexpected exception, missing file
  - resume after restart, chunks persisting, delete removing chunks, delete during processing
- **Regression:** all Phase 1 and 2 tests still pass. Four Phase 2 assertions now compare only the upload-time fields, because status changes after upload, and one expects the new `chunks/` directory.
- **Browser (Chrome):**
  - 800-page PDF went Uploaded → Processing… → Processed (800 pages · 3200 chunks)
  - quality PDF processed into 2 pages and 2 chunks; the API returned the expected chunk text and metadata
  - corrupted and scanned PDFs showed Failed with readable reasons
  - state survived a page reload and a backend restart, with no re-processing
  - deleting a duplicate-named document removed the right PDF and chunk file
  - header showed "Local / Ready"; no console errors

## Known issues

- Header backend status is checked only on page load (from Phase 2).
- Scanned or image-only PDFs fail; OCR is a later enhancement.
- No API to re-process a failed document yet (re-index is a later phase). Delete it and upload again.
- Processing is CPU-bound Python on one worker; an 800-page PDF takes about 3–4 s, and list requests slow slightly meanwhile.
- The metadata store assumes a single backend process.
- No frontend unit-test runner.
- On this machine, another project's Vite also listens on `[::1]:5173`, so use `http://127.0.0.1:5173` for PersonalDoc.

## Next phase

Phase 4: Embeddings and ChromaDB. Not started.
