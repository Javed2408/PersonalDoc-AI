# PersonalDoc AI

A privacy-first, local RAG application for chatting with your personal documents using a locally running LLM.

> **Status:** Phase 2 (document upload and storage). You can upload PDFs, list them, and delete them; files and metadata stay on your machine. Text extraction, indexing, and chat come in later phases (see [Phases.md](Phases.md)).

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
│   │   │   └── documents.py Upload / list / delete endpoints
│   │   ├── services/
│   │   │   ├── document_service.py  Validation, file storage, deletion
│   │   │   └── document_store.py    JSON metadata persistence
│   │   └── models/schemas.py
│   ├── data/                Runtime data, created on startup, git-ignored
│   │   ├── documents/       Uploaded PDFs, stored as <document_id>.pdf
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
| `DELETE` | `/api/documents/{document_id}` | Delete a document's file and metadata |

```bash
curl -F "file=@report.pdf;type=application/pdf" http://127.0.0.1:8000/api/documents/upload
```

Uploads are rejected with a readable `detail` message when they are not PDFs (`415`), are empty (`400`) or exceed the size limit (`413`). Unknown document IDs return `404`.

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

Uploaded documents never leave `DATA_DIR`, and that directory is git-ignored.

## Frontend setup

From the `frontend/` directory:

```bash
npm install
npm run dev
```

Open http://localhost:5173. The header and the Backend card show **Local / Ready** when the API is reachable. When it isn't, they show **Backend offline** with a retry button.

The **Documents** sidebar lets you upload PDFs (button or drag and drop), see each upload's state, retry or dismiss failed uploads, refresh the list, and delete a document after an inline confirmation.

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
