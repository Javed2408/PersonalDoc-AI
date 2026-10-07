# PersonalDoc AI

A privacy-first, local RAG application for chatting with your personal documents using a locally running LLM.

> **Status:** Phase 1 (project foundation). The repo has a FastAPI backend with a health endpoint and a React/Vite frontend shell that reports backend status. Document upload, indexing, and chat come in later phases (see [Phases.md](Phases.md)).

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
│   │   ├── api/health.py    GET /api/health
│   │   └── models/schemas.py
│   ├── tests/               pytest suite
│   ├── requirements.txt     Runtime dependencies
│   ├── requirements-dev.txt Runtime + test dependencies
│   └── .env.example
└── frontend/                React + Vite application
    ├── src/
    │   ├── components/      Layout/ and Common/ components
    │   ├── hooks/useHealth.js
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

### Backend configuration

Settings are read from environment variables or `backend/.env`. All have defaults, so `.env` is optional.

| Variable | Default | Description |
| --- | --- | --- |
| `APP_NAME` | `PersonalDoc AI` | Name reported by the health endpoint |
| `APP_VERSION` | `0.1.0` | Version reported by the health endpoint |
| `ENVIRONMENT` | `development` | Environment label |
| `LOG_LEVEL` | `INFO` | Python logging level |
| `CORS_ORIGINS` | `http://localhost:5173,http://127.0.0.1:5173` | Comma-separated origins allowed to call the API directly |

## Frontend setup

From the `frontend/` directory:

```bash
npm install
npm run dev
```

Open http://localhost:5173. The header and the Backend card show **Local / Ready** when the API is reachable. When it isn't, they show **Backend offline** with a retry button.

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
