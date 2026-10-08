# PersonalDoc AI

A privacy-first, local RAG application for chatting with your personal documents using a locally running LLM.

> **Status:** Phase 7 (chat UI). Upload PDFs, choose which ones to ask about (or all of them), and chat with them in the browser. Each answer comes from a local Ollama model, **only from the retrieved passages**, and lists the pages it's based on, or says clearly that the documents don't contain the answer. Everything stays on your machine. Next: Phase 8, citations and document UX (see [Phases.md](Phases.md)).

## Project documents

| File | Purpose |
| --- | --- |
| [PRD.md](PRD.md) | Product requirements |
| [Architecture.md](Architecture.md) | System architecture and target structure |
| [Rules.md](Rules.md) | Development rules |
| [Phases.md](Phases.md) | Phased delivery plan |
| [Design.md](Design.md) | UI/UX specification |
| [Memory.md](Memory.md) | Current project state |

## Repository layout

```text
PersonalDoc-AI/
├── backend/                 FastAPI application
│   ├── app/
│   │   ├── main.py          App factory, CORS, router registration
│   │   ├── config.py        Settings (pydantic-settings, reads backend/.env)
│   │   ├── api/
│   │   │   ├── health.py    GET /api/health
│   │   │   ├── documents.py Upload / list / delete / chunks endpoints
│   │   │   ├── retrieval.py POST /api/retrieval/search
│   │   │   └── chat.py      POST /api/chat (grounded answers)
│   │   ├── ingestion/
│   │   │   ├── loader.py    PDF -> per-page text (pypdf)
│   │   │   ├── splitter.py  Recursive character text splitter
│   │   │   └── pipeline.py  Pages -> chunks with metadata
│   │   ├── retrieval/
│   │   │   ├── embeddings.py    Embedder interface + sentence-transformers model
│   │   │   ├── vector_store.py  ChromaDB persistence (store / delete / stats / nearest-neighbour query)
│   │   │   └── retriever.py     Question -> top-k chunks (validation, filtering, scoring)
│   │   ├── generation/
│   │   │   ├── llm.py           LLM interface + Ollama client (stdlib HTTP)
│   │   │   ├── prompts.py       Grounded prompt with delimited, untrusted context
│   │   │   └── rag_chain.py     Retrieve -> evidence gate -> context budget -> LLM -> answer + sources
│   │   ├── services/
│   │   │   ├── document_service.py    Validation, file storage, deletion
│   │   │   ├── document_store.py      JSON metadata persistence
│   │   │   ├── chunk_store.py         JSON chunk persistence (one file per document)
│   │   │   ├── indexing_service.py    Chunks -> embeddings -> ChromaDB, only what changed
│   │   │   └── processing_service.py  Background extract -> chunk -> index, status updates
│   │   └── models/schemas.py
│   ├── data/                Runtime data, created on startup, git-ignored
│   │   ├── documents/       Uploaded PDFs, stored as <document_id>.pdf
│   │   ├── chunks/          Extracted chunks, <document_id>.json
│   │   ├── chroma/          ChromaDB vector index
│   │   └── documents.json   Document metadata
│   ├── evaluation/          Retrieval and RAG evaluation sets, runners and saved results
│   ├── tests/               pytest suite
│   ├── requirements.txt     Runtime dependencies
│   ├── requirements-dev.txt Runtime + test dependencies
│   └── .env.example
└── frontend/                React + Vite application
    ├── src/
    │   ├── components/      Layout/, Common/, Documents/, Chat/ and Sources/ components
    │   ├── hooks/           useHealth, useDocuments, useDocumentSelection, useChat
    │   ├── utils/           Formatting, answer text, source grouping, error and status wording
    │   ├── services/api.js  All HTTP calls go through here
    │   ├── test/            Test setup and a fake backend for the frontend tests
    │   ├── styles/          Design tokens and global styles
    │   ├── App.jsx
    │   └── main.jsx
    ├── vite.config.js       Dev server + /api proxy
    └── .env.example
```

## Prerequisites

- Python 3.11+
- Node.js 20.19+ (or 22.12+) and npm
- About 1.5 GB of disk for the Python environment (PyTorch CPU, sentence-transformers, ChromaDB)
- Internet access the first time a document is processed, to download the embedding model (~90 MB, see below)
- [Ollama](https://ollama.com/download) with a local model for answers (see "Local LLM setup"). Everything else works without it.

## Backend setup

From the `backend/` directory:

```bash
python -m venv .venv

# Activate it
# Windows (PowerShell):  .venv\Scripts\Activate.ps1
# Windows (Git Bash):    source .venv/Scripts/activate
# macOS / Linux:         source .venv/bin/activate

pip install -r requirements-dev.txt   # or requirements.txt for runtime only

# Optional: customise settings
cp .env.example .env
```

Run the API (with the venv active):

```bash
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

Check it:

```bash
curl http://127.0.0.1:8000/api/health
# {"status":"ok","app_name":"PersonalDoc AI","version":"0.1.0","environment":"development",
#  "llm":{"status":"ready","model":"llama3.2:3b"}}
```

Interactive API docs are at http://127.0.0.1:8000/docs.

### API

| Method | Path | Description |
| --- | --- | --- |
| `GET` | `/api/health` | Backend status, plus whether the local model can answer (`llm.status`: `ready`, `unavailable` or `model_missing`) |
| `GET` | `/api/documents` | List stored documents, newest first |
| `POST` | `/api/documents/upload` | Upload one PDF (multipart field `file`). Returns `201` with metadata |
| `GET` | `/api/documents/{document_id}/chunks` | Extracted text chunks of a processed document |
| `DELETE` | `/api/documents/{document_id}` | Delete a document's file, chunks and metadata |
| `POST` | `/api/retrieval/search` | Most relevant chunks for a question (no answer generation) |
| `POST` | `/api/chat` | Grounded answer from a local LLM, with its sources (needs Ollama) |

```bash
curl -F "file=@report.pdf;type=application/pdf" http://127.0.0.1:8000/api/documents/upload
```

Uploads are rejected with a readable `detail` message when they are not PDFs (`415`), are empty (`400`) or exceed the size limit (`413`). Unknown document IDs return `404`.

### Document processing

After an upload is stored, a background worker processes it:

```text
uploaded -> processing -> processed   (extracted, chunked, embedded and stored in ChromaDB)
                       -> failed      (processing_error explains why; the PDF is kept)
```

- Text is extracted page by page with [pypdf](https://pypi.org/project/pypdf/). Empty pages are kept in the page count but produce no chunks.
- Each page is split on its own with a recursive character splitter: paragraphs, then lines, then words, then characters. Chunks are at most `CHUNK_SIZE` characters and overlap by up to `CHUNK_OVERLAP`. Because pages are split separately, every chunk belongs to exactly one page.
- Each chunk records `chunk_id`, `document_id`, `original_filename`, `page_number`, `chunk_index`, `start_char` (offset within the page text), `char_count` and `text`.
- Corrupted, password-protected and text-free (e.g. scanned) PDFs end up `failed` with a readable reason.
- Each chunk is embedded with a local [sentence-transformers](https://www.sbert.net/) model and stored in ChromaDB. The vector ID is the chunk's `chunk_id`; the vector keeps the chunk text and the metadata above (except the text itself, which is stored as the record's document).
- A document only becomes `processed` once its vectors are stored. If embedding or storage fails, it becomes `failed`; its PDF and chunks are kept and partial vectors removed.
- Reprocessing never duplicates vectors: chunks whose text and metadata are unchanged are not re-embedded, changed ones are replaced, and vectors for chunks that no longer exist are deleted.
- At startup, documents left `uploaded` or `processing` are processed again, and `processed` documents whose vectors are missing (for example after deleting `data/chroma`) are re-indexed.
- Deleting a document removes its PDF, chunks, vectors and metadata.

### Retrieval

`POST /api/retrieval/search` embeds the question once with the same local model, runs one ChromaDB nearest-neighbour query, and returns the top-k chunks. It never generates an answer.

```bash
curl -X POST http://127.0.0.1:8000/api/retrieval/search   -H "Content-Type: application/json"   -d '{"query": "What are the main findings?", "k": 4, "document_ids": []}'
```

```json
{
  "query": "What are the main findings?",
  "k": 4,
  "document_ids": null,
  "result_count": 4,
  "results": [
    {
      "rank": 1,
      "chunk_id": "<document_id>-00021",
      "document_id": "<document_id>",
      "original_filename": "report.pdf",
      "page_number": 14,
      "chunk_index": 21,
      "start_char": 0,
      "char_count": 912,
      "text": "...",
      "distance": 0.23,
      "similarity": 0.77
    }
  ]
}
```

- **Request:**
  - `query`: required, trimmed, 1–2000 characters.
  - `k`: optional, 1–`RETRIEVAL_MAX_K`; default `RETRIEVAL_TOP_K` (4).
  - `document_ids`: optional. Omitted or `[]` searches every processed document; otherwise only the listed ones.
- **Scores:**
  - `distance` is ChromaDB's cosine distance, `1 − cosine similarity`: 0 means the same direction, about 1 means unrelated, 2 means opposite. **Lower is more similar**, and results are sorted by it, with ties broken by `chunk_id`.
  - `similarity` is exactly `1 − distance`, so higher is more similar.
  - Both are geometric measures, not probabilities or confidence.
- **What gets searched:** only `processed` documents, so partially indexed or failed documents never appear. Fewer than k results come back when fewer chunks exist; results are never padded.
- **No threshold by default:** plain top-k always returns the nearest chunks, even for questions the documents can't answer. Their larger distances show it. `RETRIEVAL_MAX_DISTANCE` can drop chunks beyond a cut-off, but it stays off until evaluation (Phase 9) justifies a value.
- **Errors:**
  - `422`: empty query, k out of range, or a malformed document ID
  - `404`: unknown document ID
  - `409`: the document isn't processed yet, or failed
  - `503`: the embedding model or vector index is unavailable
- **Privacy:** INFO logs record only k, the filter size, the result count and the best distance. Query text and per-result details are logged only at `LOG_LEVEL=DEBUG`.

### Retrieval evaluation

`backend/evaluation/retrieval_dataset.json` holds 3 small documents with deliberately shared vocabulary and 15 questions: 12 answerable, each tied to the page with its answer, and 3 the documents can't answer. The runner indexes them with the real model in a throwaway directory (never `backend/data`) and checks whether the right page appears in the top-k:

```bash
cd backend
python -m evaluation.retrieval_eval           # print the report
python -m evaluation.retrieval_eval --write   # also update evaluation/results/retrieval_baseline.md
```

### Local LLM setup (Ollama)

Answers are generated by a model running locally in [Ollama](https://ollama.com). Nothing is sent to any cloud service, and the app never installs Ollama or downloads a model by itself.

1. Install Ollama: <https://ollama.com/download> (Windows, macOS, Linux). It runs in the background on `http://127.0.0.1:11434`.
2. Pull the default model, about 2 GB:

   ```bash
   ollama pull llama3.2:3b
   ```

3. Start the backend as usual. Ollama is only contacted when a question is asked.

The default model, `llama3.2:3b`, is small enough for a laptop GPU with 4 GB of VRAM (or the CPU) and follows instructions reasonably well. Larger models such as `mistral` (7B, about 4 GB) or `llama3.1:8b` follow grounding rules more reliably but need more memory and are slower. Switch with `OLLAMA_MODEL` after `ollama pull <model>`.

If Ollama isn't running, `/api/chat` answers `503` with "Can't reach Ollama...". If the model isn't pulled, it answers `503` with the exact `ollama pull` command to run. Everything else keeps working.

### Grounded answers (RAG)

`POST /api/chat` answers one question at a time; there is no conversation history yet.

```bash
curl -X POST http://127.0.0.1:8000/api/chat \
  -H "Content-Type: application/json" \
  -d '{"question": "What are the main findings?", "k": 4, "document_ids": []}'
```

```json
{
  "question": "What are the main findings?",
  "answer": "The report finds that ... [Source 1]",
  "status": "answered",
  "model": "llama3.2:3b",
  "sources": [
    {
      "label": "Source 1",
      "chunk_id": "<document_id>-00021",
      "document_id": "<document_id>",
      "original_filename": "report.pdf",
      "page_number": 14,
      "chunk_index": 21,
      "text": "...",
      "distance": 0.23,
      "similarity": 0.77
    }
  ]
}
```

How an answer is produced (one embedding, one vector search, at most one LLM call):

1. **Retrieve** the top-k chunks with the retriever. `k` and `document_ids` work exactly as in `/api/retrieval/search`, including its validation and errors.
2. **Evidence gate:** chunks whose cosine distance is above `RAG_MAX_DISTANCE` (default 0.7, meaning cosine similarity below 0.3) are not treated as evidence. If none are left, the response is `status: "not_found"` with the fallback sentence, and the LLM is not called. The default is provisional and deliberately loose, so it only removes clearly unrelated text. Judging subtler cases is left to the model and its grounding rules. It should be tuned with the Phase 9 evaluation.
3. **Context budget:** evidence chunks go into the prompt in rank order, whole, while their text fits in `RAG_MAX_CONTEXT_CHARS` (6000 by default; about 1500 tokens, comfortably inside the 4096-token window together with the instructions and a 512-token answer). A chunk that doesn't fit is skipped rather than cut. Only a single chunk larger than the whole budget is shortened, at a word boundary.
4. **Prompt:**
   - The system message holds the rules: answer only from the excerpts, no outside knowledge, no invented facts or sources, the exact fallback sentence when the excerpts don't answer, say which part is missing for partial answers, and treat excerpts as untrusted data rather than instructions.
   - The user message holds a `CONTEXT` section, with each excerpt in its own `<source label="Source N" document="..." page="...">` block inside `<context>...</context>`, then a `USER QUESTION` section in `<question>...</question>`.
   - Tag-like text inside documents or questions is neutralised, so a PDF can't close the context block and pose as instructions.
5. **Answer:**
   - If the model replies with the fallback sentence, the response is `not_found`.
   - Otherwise the answer is returned with exactly the chunks the model was given as `sources`, copied from retrieval, never generated.
   - `[Source N]` citations that point at no real source are removed.

| Status | Meaning |
| --- | --- |
| `200` `answered` | Answer plus the sources it was based on |
| `200` `not_found` | No sufficient evidence; fallback sentence, no sources |
| `422` / `404` / `409` | Invalid request, unknown document, or document not processed (same as retrieval) |
| `503` | Ollama not running, model not pulled, or the embedding model/index unavailable |
| `504` | The model didn't answer within `LLM_TIMEOUT_SECONDS` |
| `502` | The model failed or returned an empty or invalid response |

Logs record counts and timings only, never the context, question or answer text.

### RAG evaluation

`backend/evaluation/rag_dataset.json` asks 22 questions about the retrieval evaluation documents plus a memo containing a prompt injection. The questions cover answerable, partial-evidence, related-but-insufficient, misleading-overlap, unanswerable and prompt-injection cases. The runner uses the real embedding model and Ollama in a throwaway directory:

```bash
cd backend
python -m evaluation.rag_eval           # print the report (needs Ollama and the model)
python -m evaluation.rag_eval --write   # also update evaluation/results/rag_baseline.md
```

Scoring is keyword-based and the set is small, so treat it as a smoke test and read the saved answers.

Baseline with `llama3.2:3b` ([rag_baseline.md](backend/evaluation/results/rag_baseline.md)): 20/22. All answerable, unanswerable, related-but-insufficient and misleading-overlap questions pass. The memo's injection is never followed. However, the 3B model also refuses to give the real renewal date from that memo, so the two memo questions come back `not_found`. Prompt wordings that got it to answer also got it to obey the injection, so the safe refusal is kept.

### Embedding model and first run

The default model is [`sentence-transformers/all-MiniLM-L6-v2`](https://huggingface.co/sentence-transformers/all-MiniLM-L6-v2): 384-dimensional embeddings, about 90 MB, fast on a laptop CPU, and the "MiniLM" model named in the architecture. It reads up to 256 tokens (more than a 1000-character chunk), and English text works best.

- **First run:** the model is downloaded from the Hugging Face Hub when the first document is processed (not at startup), into the Hugging Face cache (`~/.cache/huggingface`, or `HF_HOME`), never into this repository. Later runs work offline.
- **Loading:** the model loads once per backend process, on first use (a few seconds), so the first document after a restart takes a little longer.
- **Speed:** on CPU, about 100 chunks per second; an 800-page PDF (3200 chunks) takes roughly 35-40 seconds. The API stays responsive meanwhile.
- **Changing the model:** vectors from different models can't be mixed, so the backend refuses to start if `EMBEDDING_MODEL` doesn't match the model the collection was built with. Set a new `CHROMA_COLLECTION` too; existing documents are then re-indexed automatically at startup.
- ChromaDB runs embedded (no server) with its anonymous telemetry turned off.

### Backend configuration

Settings are read from environment variables or `backend/.env`. All have defaults, so `.env` is optional.

| Variable | Default | Description |
| --- | --- | --- |
| `APP_NAME` | `PersonalDoc AI` | Name reported by the health endpoint |
| `APP_VERSION` | `0.1.0` | Version reported by the health endpoint |
| `ENVIRONMENT` | `development` | Environment label |
| `LOG_LEVEL` | `INFO` | Python logging level |
| `CORS_ORIGINS` | `http://localhost:5173,http://127.0.0.1:5173` | Comma-separated origins allowed to call the API directly |
| `DATA_DIR` | `data` | Runtime data directory. Relative paths resolve against `backend/` |
| `MAX_UPLOAD_SIZE_MB` | `25` | Maximum size of one uploaded file |
| `CHUNK_SIZE` | `1000` | Maximum chunk length, in characters |
| `CHUNK_OVERLAP` | `150` | Maximum overlap between consecutive chunks on a page (must be less than `CHUNK_SIZE`) |
| `EMBEDDING_MODEL` | `sentence-transformers/all-MiniLM-L6-v2` | Local embedding model (Hugging Face name or local path) |
| `EMBEDDING_DEVICE` | `cpu` | `cpu`, `cuda`, `mps`; empty to auto-detect |
| `EMBEDDING_BATCH_SIZE` | `32` | Chunks embedded per batch |
| `CHROMA_DIR` | `<DATA_DIR>/chroma` | ChromaDB storage directory |
| `CHROMA_COLLECTION` | `personaldoc_chunks` | ChromaDB collection name |
| `RETRIEVAL_TOP_K` | `4` | Default number of chunks returned per query |
| `RETRIEVAL_MAX_K` | `20` | Largest `k` a request may ask for (at most 100) |
| `RETRIEVAL_MAX_DISTANCE` | *(empty: off)* | Optional cosine-distance cut-off (0–2) |
| `OLLAMA_BASE_URL` | `http://127.0.0.1:11434` | Ollama server |
| `OLLAMA_MODEL` | `llama3.2:3b` | Model used for answers (must be pulled in Ollama) |
| `LLM_TEMPERATURE` | `0` | Sampling temperature (0 = most deterministic) |
| `LLM_MAX_TOKENS` | `512` | Maximum answer length in tokens |
| `LLM_CONTEXT_WINDOW` | `4096` | Model context window in tokens (Ollama `num_ctx`) |
| `LLM_TIMEOUT_SECONDS` | `120` | Give up on a generation after this long |
| `RAG_MAX_DISTANCE` | `0.7` | Chunks farther than this are not used as evidence |
| `RAG_MAX_CONTEXT_CHARS` | `6000` | Document text budget per prompt |

Uploaded documents never leave `DATA_DIR`, and that directory is git-ignored.

## Frontend setup

From the `frontend/` directory:

```bash
npm install
npm run dev
```

Open http://127.0.0.1:5173.

The header shows what is actually available: **Local / Ready** only when the backend is up and Ollama has the model, **Ollama unavailable** or **Model not installed** when the backend is up but can't answer yet, and **Backend offline** when the API can't be reached. The last three come with a short explanation above the question box and a **Check again** button. Status is checked on load, when you ask, and after errors; it isn't polled.

### Chatting with your documents

- **Context:** with nothing selected, questions search **all processed documents**, the API's default. Tick documents in the sidebar to search only those; the box above the composer always shows the current context, and each question in the conversation is labelled with the documents it was asked about. Only processed documents can be ticked. Uploading or failed ones stay visible but disabled, and a deleted document leaves the context automatically.
- **Asking:** Enter sends, Shift+Enter adds a line. While an answer is being generated the send button is disabled (the box stays editable so you can draft the next question). Local models can take a few seconds, longer on the first question after a start.
- **Answers:** the model's text is shown as plain text with paragraphs, lists, **bold** and `[Source N]` markers. It is never rendered as HTML. Below each answer, **Sources** lists the document pages the model was given, grouped by page; open a card to see which chunks it came from and their similarity. Similarity says how close a passage is to the question; it isn't a confidence score. When the documents don't contain the answer, you get the "couldn't find enough information" reply without sources.
- **Errors:** a failed answer explains what went wrong (backend down, Ollama not running, model not installed, timeout, a deleted document) and offers **Retry**, which asks the same question again with the documents selected now.
- **New chat** clears the conversation. Documents and the selection are kept.
- **Follow-ups:** each question is answered on its own from the documents; earlier messages aren't sent to the model. The conversation lives only in the page: reloading starts a new chat, and nothing is stored on the server or in the browser.
- **Small screens:** below 720px wide the document list becomes a drawer, opened from the header or with **Choose documents**.

### Document library

The **Documents** sidebar lets you upload PDFs (button or drag and drop), see each upload's state, retry or dismiss failed uploads, refresh the list, and delete a document after an inline confirmation. Each document shows its processing status (Uploaded, Processing…, Processed with page and chunk counts, or Failed with the reason); the list refreshes itself while anything is still processing.

In development, the Vite server proxies `/api/*` to the backend, so the browser never makes a cross-origin request.

### Frontend configuration

Copy `.env.example` to `.env.local` to override:

| Variable | Default | Description |
| --- | --- | --- |
| `VITE_API_PROXY_TARGET` | `http://127.0.0.1:8000` | Where the dev server proxies `/api` |
| `VITE_API_BASE_URL` | *(empty)* | Set to call the backend directly instead of through the proxy (CORS must allow the frontend origin) |

## Tests and checks

```bash
# Backend (from backend/, venv active)
pytest                 # everything, including tests that load the real embedding model
pytest -m "not model"  # skip tests that need the real embedding model or Ollama (fast)
pytest -m ollama       # only the real-LLM tests (skipped automatically if Ollama or the model is missing)

# Frontend (from frontend/)
npm test               # Vitest + Testing Library, against a fake backend (no servers needed)
npm run build          # production build
```
