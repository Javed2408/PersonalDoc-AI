# PersonalDoc AI — Project Memory

## Current phase

**Phase 1: Project Foundation — complete.** Awaiting review before Phase 2.

## Completed work

- FastAPI backend with app factory, CORS, env-driven settings, and `GET /api/health`.
- React 19 + Vite 8 frontend shell (header, sidebar, workspace) using the Design.md dark tokens.
- Frontend calls `/api/health` through `services/api.js` and the `useHealth` hook, with loading, ok, and error states plus retry.
- `.env.example` for backend and frontend; root `.gitignore` (excludes `.env`, `data/`, venv, node_modules, dist).
- README with setup instructions.

## Project structure

```text
backend/
  app/main.py            create_app(): CORS + routers under /api
  app/config.py          Settings (pydantic-settings), get_settings() cached
  app/api/health.py      GET /api/health -> HealthResponse
  app/models/schemas.py  HealthResponse
  tests/                 test_health.py, test_config.py
  requirements.txt / requirements-dev.txt / pytest.ini / .env.example
frontend/
  src/services/api.js    single place for HTTP calls (ApiError)
  src/hooks/useHealth.js
  src/components/Layout/ Header, Sidebar
  src/components/Common/ StatusIndicator, BackendStatusCard
  src/styles/            tokens.css, global.css
  vite.config.js         /api proxy -> VITE_API_PROXY_TARGET (default 127.0.0.1:8000)
```

## Technical decisions

- Python deps: `venv` + pinned `requirements.txt` (matches Architecture.md). Dev/test deps live in `requirements-dev.txt`.
- Pinned: fastapi 0.142.2, uvicorn 0.54.0, pydantic 2.13.5, pydantic-settings 2.15.0, pytest 9.1.1, httpx2 2.13.1. Starlette's TestClient now uses `httpx2`; plain `httpx` triggers a deprecation warning.
- Config through `pydantic-settings`. `CORS_ORIGINS` is a comma-separated string (uses `NoDecode`).
- Dev requests go through the Vite proxy (same origin). CORS is still configured so `VITE_API_BASE_URL` can target the backend directly.
- `api.js` maps 502/503/504 to "Can't reach the backend", because the Vite proxy returns 502 when the backend is down.
- Plain CSS with design tokens; no UI library, router, or state library. No web fonts loaded (local-first; system font fallback).
- Health endpoint reports app status only. LLM, vector DB, and document counts get added in their own phases.
- `backend/data/` is not created yet (Phase 2) but is already gitignored.

## Commands

```bash
# Backend (backend/)
python -m venv .venv && .venv/Scripts/pip install -r requirements-dev.txt
.venv/Scripts/python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
.venv/Scripts/python -m pytest

# Frontend (frontend/)
npm install
npm run dev      # http://localhost:5173
npm run build
```

## Tests performed

- `pytest`: 4 passed (health payload, CORS header for frontend origin, 404 on unknown route, CORS env parsing).
- Live `curl` of `/api/health` returns 200 `{"status":"ok",...}`. CORS preflight from `localhost:5173` returns 200 with allow-origin.
- `npm run build` succeeds; `npm install` reports 0 vulnerabilities.
- Browser (Chrome): shell renders with "Local / Ready" and live health data. With the backend stopped it shows "Backend offline" and a readable message. After restarting the backend, Retry recovers. No console errors.

## Known issues

- React StrictMode double-runs effects in dev, so the first `/api/health` request is aborted (DevTools shows it as failed or 503). This is expected, dev-only, and not a bug.
- No frontend unit-test runner yet. The frontend is verified through the build and manual browser checks.
- No git repository initialised yet.

## Next phase

Phase 2: Document Upload and Storage (upload endpoint, PDF and size validation, stable IDs, local storage, metadata, document library UI). Not started.
