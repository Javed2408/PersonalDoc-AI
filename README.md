# PersonalDoc AI

A privacy-first, local RAG application for chatting with your personal documents using a locally running LLM.

> **Status:** Phase 3 (PDF extraction and chunking). Uploaded PDFs are processed in the background: text is extracted page by page and split into overlapping chunks that keep their page numbers. Everything stays on your machine. Embeddings, search, and chat come in later phases (see [Phases.md](Phases.md)).

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
│   │   │   └── documents.py Upload / list / delete / chunks endpoints
│   │   ├── ingestion/
│   │   │   ├── loader.py    PDF -> per-page text (pypdf)
│   │   │   ├── splitter.py  Recursive character text splitter
│   │   │   └── pipeline.py  Pages -> chunks with metadata
│   │   ├── services/
│   │   │   ├── document_service.py    Validation, file storage, deletion
│   │   │   ├── document_store.py      JSON metadata persistence
│   │   │   ├── chunk_store.py         JSON chunk persistence (one file per document)
│   │   │   └── processing_service.py  Background extraction + chunking, status updates
│   │   └── models/schemas.py
│   ├── data/                Runtime data, created on startup, git-ignored
│   │   ├── documents/       Uploaded PDFs, stored as <document_id>.pdf
│   │   ├── chunks/          Extracted chunks, <document_id>.json
│   │   └── documents.json   Document metadata
│   ├── tests/               pytest suite
│   ├── requirements.txt     Runtime dependencies
│   ├── requirements-dev.txt Runtime + test dependencies
│   └── .env.example
└── frontend/                React + Vite application
    ├── src/
    │   ├── components/      Layout/, Common/ and Documents/ components
    │   ├── hooks/           useHealth.js, useDocuments.js
    │   ├── utils/format.js  Byte and date formatting
    │   ├── services/api.js  All HTTP calls go through here
    │   ├── styles/          Design tokens and global styles
    │   ├── App.jsx
    │   └── main.jsx
    ├── vite.config.js       Dev server + /api proxy
    └── .env.example
```

## Prerequisites

- Python 3.11+
- Node.js 20.19+ (or 22.12+) and npm

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
# {"status":"ok","app_name":"PersonalDoc AI","version":"0.1.0","environment":"development"}
```

Interactive API docs are at http://127.0.0.1:8000/docs.

### API

| Method | Path | Description |
| --- | --- | --- |
| `GET` | `/api/health` | Backend status |
| `GET` | `/api/documents` | List stored documents, newest first |
| `POST` | `/api/documents/upload` | Upload one PDF (multipart field `file`). Returns `201` with metadata |
| `GET` | `/api/documents/{document_id}/chunks` | Extracted text chunks of a processed document |
| `DELETE` | `/api/documents/{document_id}` | Delete a document's file, chunks and metadata |

```bash
curl -F "file=@report.pdf;type=application/pdf" http://127.0.0.1:8000/api/documents/upload
```

Uploads are rejected with a readable `detail` message when they are not PDFs (`415`), are empty (`400`) or exceed the size limit (`413`). Unknown document IDs return `404`.

### Document processing

After an upload is stored, a background worker processes it:

```text
uploaded -> processing -> processed   (text extracted and chunked)
                       -> failed      (processing_error explains why; the PDF is kept)
```

- Text is extracted page by page with [pypdf](https://pypi.org/project/pypdf/). Empty pages are kept in the page count but produce no chunks.
- Each page is split on its own with a recursive character splitter: paragraphs, then lines, then words, then characters. Chunks are at most `CHUNK_SIZE` characters and overlap by up to `CHUNK_OVERLAP`. Because pages are split separately, every chunk belongs to exactly one page.
- Each chunk records `chunk_id`, `document_id`, `original_filename`, `page_number`, `chunk_index`, `start_char` (offset within the page text), `char_count` and `text`.
- Corrupted, password-protected and text-free (e.g. scanned) PDFs end up `failed` with a readable reason.
- Documents left `uploaded` or `processing` by a restart are processed again at startup.

"Processed" means extracted and chunked, not indexed: embeddings and search arrive in Phase 4.

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

Uploaded documents never leave `DATA_DIR`, and that directory is git-ignored.

## Frontend setup

From the `frontend/` directory:

```bash
npm install
npm run dev
```

Open http://localhost:5173. The header and the Backend card show **Local / Ready** when the API is reachable. When it isn't, they show **Backend offline** with a retry button.

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
pytest

# Frontend production build (from frontend/)
npm run build
```
