# PersonalDoc AI — Project Memory

## Current phase

**Phase 2: Document Upload and Storage — complete.** Awaiting review before Phase 3.

## Completed

- Phase 1: FastAPI app factory, env settings, `GET /api/health`, React/Vite shell with backend status.
- PDF upload (`POST /api/documents/upload`) with validation for extension, content type, `%PDF-` signature, empty files, size limit and unsafe filenames.
- Local storage in `backend/data/documents/`, created at startup and git-ignored.
- Metadata persisted in `backend/data/documents.json`.
- Document listing (`GET /api/documents`, newest first) and deletion (`DELETE /api/documents/{id}`).
- Frontend document library in the sidebar:
  - upload by button or drag and drop, with Uploading → Uploaded / Upload failed states
  - Retry and Dismiss on failed uploads
  - refresh; delete with inline confirmation
  - empty, loading and error states

## Project structure

```text
backend/app/
  main.py                      create_app(settings?): CORS, upload size guard, routers, lifespan creates storage
  config.py                    Settings + DATA_DIR, MAX_UPLOAD_SIZE_MB, derived documents_dir/metadata_file
  api/health.py, api/documents.py
  services/document_service.py validation, streaming save, delete (raises DocumentError subclasses)
  services/document_store.py   JsonDocumentStore (lock + atomic write)
  models/schemas.py            HealthResponse, DocumentMetadata, list/delete responses
backend/tests/                 conftest.py (tmp data dir per test), test_health, test_config, test_documents
frontend/src/
  services/api.js              request() + getHealth/listDocuments/uploadDocument/deleteDocument
  hooks/useHealth.js, hooks/useDocuments.js
  components/Documents/        DocumentLibrary, UploadDropzone, UploadItem, DocumentItem
  components/Common/           StatusIndicator, BackendStatusCard, Icon
  components/Layout/           Header, Sidebar
  utils/format.js
```

## Important decisions

- **Document ID:** `uuid4().hex`. The stored filename is always `<document_id>.pdf`. The client filename is display-only: it is reduced to its basename, control/format characters are stripped, and it is truncated to 200 chars. It is never used as a path.
- **Storage:** the upload streams to `.<id>.pdf.part` (exclusive create), then is renamed into place. Every path is resolved and checked to stay inside the documents directory.
- **Metadata persistence:** a single JSON file behind `JsonDocumentStore`, using a threading lock and temp-file + `os.replace` writes. Assumes one backend process. If the file is unreadable, endpoints return 500 and the file is never overwritten. The store is small and replaceable (e.g. SQLite later).
- **Upload size:** `MAX_UPLOAD_SIZE_MB` (default 25).
  - Enforced twice: a middleware pre-check on `Content-Length`, and an exact byte count while streaming.
  - The pre-check drains the body before sending 413. Answering mid-upload makes the Vite proxy return 502.
- **Status:** `uploaded` | `failed`. The backend only persists successful uploads. Failed attempts are shown client-side for the session with Retry.
- **Consistency:** if the metadata write fails, the stored file is removed. Delete removes the file first and keeps the metadata if removal fails; a file that is already missing is tolerated.
- **Errors:** the API returns `{"detail": "<safe message>"}` with 400/404/413/415/500. The frontend shows `detail`, with fallbacks per status code.
- **Logging:** document IDs and sizes only. No filenames or contents are logged.
- New dependency: `python-multipart==0.0.32`, which FastAPI requires for file uploads.

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

## Tests

- **Backend:** 48 passed. The 4 Phase 1 tests still pass, and Phase 2 adds tests for:
  - upload and metadata
  - listing order, restart persistence and corrupt metadata
  - unsupported types and fake PDFs, empty files, oversized files (pre-check, streaming, exact limit)
  - missing and malformed multipart
  - duplicate filenames
  - delete, delete of a missing ID, delete when the file is already missing
  - path-traversal filenames and IDs, filename sanitisation, config parsing
- Tests use a per-test tmp data dir; the real `backend/data/` was not touched by tests.
- `npm run build` passes.
- **Browser (Chrome, real PDFs):**
  - upload; persists after page reload
  - two `report.pdf` files coexist; deleting one removes the right file and metadata on disk
  - `.txt` and a fake `.pdf` show readable 415 messages; Retry and Dismiss work
  - backend offline: list, upload and delete each show "Can't reach the backend"; Retry recovers once it's back
  - 2 MB file with a 1 MB limit shows the size-limit message
  - no console errors

## Known issues

- The header/backend status is only checked on page load, so it can say "Local / Ready" while document requests are failing. Periodic health polling would fix this.
- In dev, React StrictMode double-fetches on mount, so DevTools shows one aborted request. Dev-only.
- No frontend unit-test runner yet. The frontend is verified by build and manual browser testing.
- Metadata store assumes a single backend process; multiple uvicorn workers would need a real database.
- On Windows, stopping `npm run dev` from a parent process can leave the `node` Vite process running on port 5173.

## Next phase

Phase 3: PDF Extraction and Chunking. Not started.
