# PersonalDoc AI — Project Memory

## Current phase

**Phase 4: Embeddings and ChromaDB — complete.** Awaiting review before Phase 5.

## Completed

- Phase 1: FastAPI + React/Vite foundation, `GET /api/health`.
- Phase 2: PDF upload and validation, local storage, JSON metadata, list and delete, document library UI.
- Phase 3: pypdf page extraction, recursive chunking (1000/150), chunk metadata, background processing and statuses.
- Phase 4:
  - **Local embedding model:** sentence-transformers `all-MiniLM-L6-v2`, loaded lazily once per process.
  - **Embedding service:** an `Embedder` protocol plus `SentenceTransformerEmbedder` (batching, input validation, normalised vectors).
  - **ChromaDB vector store:** `ChromaVectorStore`, persistent, one collection; upsert, delete by document or ID, counts, stats.
  - **Document-to-vector indexing:** `DocumentIndexer` diffs against stored vectors, embeds only new or changed chunks, upserts, and deletes stale ones.
  - **Processing:** extract → chunk → save chunks → index → `processed`. Embedding or vector failures set `failed` and remove partial vectors.
  - **Deletion cleanup:** deleting a document removes its PDF, chunks, vectors and metadata.
  - **Idempotent vector IDs:** vector ID = Phase 3 `chunk_id`.
  - **Startup:** opens the store and validates the model. Pending documents are re-queued, and processed documents with missing vectors are re-indexed.

## Project structure (Phase 4 additions)

```text
backend/app/retrieval/embeddings.py      Embedder protocol, SentenceTransformerEmbedder, EmbeddingError
backend/app/retrieval/vector_store.py    ChromaVectorStore, chunk_metadata(), EmbeddingModelMismatchError
backend/app/services/indexing_service.py DocumentIndexer, IndexResult, IndexingCancelled
backend/app/main.py                      create_app(settings?, embedder?) wires store/indexer; app.state.vector_store
backend/tests/fakes.py                   FakeEmbedder (hash-based, 16-dim) used by API tests
```

## Important decisions

- **Embedding model:** `sentence-transformers/all-MiniLM-L6-v2`. It is the MiniLM model named in Architecture.md: small (~90 MB), fast on CPU, and well supported. It reads up to 256 tokens, which fits a 1000-character chunk.
- **Embedding dimension:** 384. Vectors are L2-normalised, so cosine similarity is a dot product.
- **Configuration** (all in `Settings`): `EMBEDDING_MODEL`, `EMBEDDING_DEVICE` (default `cpu` for reproducibility; empty means auto), `EMBEDDING_BATCH_SIZE` (32), `CHROMA_DIR` (default `<DATA_DIR>/chroma`), `CHROMA_COLLECTION`. All are validated at load.
- **ChromaDB:**
  - `PersistentClient` at `backend/data/chroma/` (git-ignored), with anonymous telemetry off.
  - Embeddings are always supplied by us (`embedding_function=None`); the HNSW index uses cosine distance.
  - **Collection name:** `personaldoc_chunks`.
  - The collection metadata records `embedding_model`. Startup refuses a mismatch, because `get_or_create` silently ignores metadata and would otherwise mix models.
- **Vector record:**
  - ID: `chunk_id`
  - embedding: from the model
  - document: the chunk text
  - metadata: `document_id`, `original_filename`, `page_number`, `chunk_index`, `start_char`, `char_count`
- **Idempotency:** chunks whose text and metadata are unchanged are skipped, changed ones are upserted, and stale IDs are deleted. Restarts never re-embed or duplicate.
- **Chunk JSON stays** as the canonical chunk record. It is kept on embedding failures, so a fix doesn't require re-extraction.
- **Delete order:** PDF → chunks → vectors → metadata (last). Every step tolerates missing data, so a failed delete can simply be retried.
- **Cancellation:** a document deleted while indexing stops between batches and its vectors and chunks are cleaned up.
- **Dependencies:** `sentence-transformers==6.1.0` (pulls in CPU PyTorch 2.14 and transformers) and `chromadb==1.5.9`. About 75 packages, a 1.4 GB venv. No LangChain, Ollama or OpenAI.

## Commands

```bash
# Backend (backend/)
.venv/Scripts/pip install -r requirements-dev.txt
.venv/Scripts/python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
.venv/Scripts/python -m pytest              # 160 tests, ~19 s (loads the real model)
.venv/Scripts/python -m pytest -m "not model"  # 153 tests, no model needed

# Frontend (frontend/)
npm install && npm run dev      # open http://127.0.0.1:5173
```

## Tests

- **160 passed.** The full suite ran 5 times in a row with no failures.
- **Embedding tests (14):**
  - lazy initialisation, empty and invalid input, load failure (readable message, retried)
  - real model: 384 dimensions, single and batch, normalised, deterministic (alone versus in a batch), loaded once, semantic sanity
- **Vector store tests (13):** creation, add with metadata, persistence after reopen, document identification, duplicate prevention, update, delete by document and by ID, safe deletes, stats, model mismatch, dimension mismatch.
- **Indexer tests (8):** batching, no re-embedding, changed chunks re-embedded, metadata changes, stale removal, isolation between documents, cancellation.
- **API indexing tests (14):**
  - one vector per chunk with full metadata, batching
  - restart without duplicates, rebuilding missing vectors, Phase 3 upgrade path, duplicate filenames
  - deletes, including a retry after a failed vector delete
  - embedding and vector failures, delete during indexing, startup model mismatch
- **End-to-end test (real model and real ChromaDB):**
  - 2 PDFs give chunk count = vector count, chunk IDs as vector IDs, exact metadata
  - stored vector equals the model output; a fresh client sees the data on disk
  - a restart adds no re-embedding or duplicates; a delete removes only that document's vectors
- **Regression:** all Phase 1–3 tests pass. The data-directory listing test now expects `chroma/`.
- **Browser (Chrome, real model):**
  - quality.pdf went Processing… → Processed (2 pages · 2 chunks) → 2 vectors in ChromaDB, checked from a separate process (IDs, metadata, 384 dimensions)
  - 800-page PDF went Processing… → Processed with 3200 vectors; the API answered in under 0.1 s meanwhile
  - after a browser refresh and a backend restart, both stayed Processed; ChromaDB reconnected with 3202 vectors and nothing was re-embedded
  - another PDF processed (1 page · 1 chunk)
  - deleting the handbook removed its 3200 vectors, PDF and chunks while the others stayed
  - no console errors

## Known issues

- **First use downloads the model** (~90 MB) from the Hugging Face Hub into `~/.cache/huggingface`. The first document after each restart waits a few seconds for the model to load. Offline machines need the model pre-cached.
- **Performance:** CPU embedding runs at about 100 chunks/s, so an 800-page PDF takes about 35–40 s. CUDA is not used: the PyPI torch wheel on Windows is CPU-only. A CUDA torch build with `EMBEDDING_DEVICE=cuda` would use the RTX 3050 Ti.
- **Install size:** about 1.4 GB, mostly PyTorch.
- `all-MiniLM-L6-v2` is English-focused, and text beyond 256 tokens is truncated. 1000-character chunks fit.
- Changing `EMBEDDING_MODEL` requires a new `CHROMA_COLLECTION`. The old collection stays on disk until `data/chroma` is cleaned.
- Carried over: header status is only checked on page load; scanned PDFs fail (no OCR); there is no re-process action for failed documents; single backend process assumed; no frontend unit tests.
- Another project's Vite listens on `[::1]:5173` on this machine, so use `http://127.0.0.1:5173`.

## Next phase

Phase 5: Retrieval. Not started.
