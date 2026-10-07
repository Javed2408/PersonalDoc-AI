# PersonalDoc AI

## Development Phases

## Phase 1: Project Foundation

### Goal

Create a clean monorepo structure and establish the development
environment.

### Tasks

-   Create backend and frontend.
-   Create Python virtual environment.
-   Add dependency management.
-   Create FastAPI application.
-   Create React/Vite application.
-   Add environment configuration.
-   Add `.gitignore`.
-   Add basic health endpoint.
-   Add basic frontend shell.

### Acceptance Criteria

-   Backend starts.
-   Frontend starts.
-   Frontend can call `/api/health`.
-   Repository has a clean structure.

------------------------------------------------------------------------

## Phase 2: Document Upload and Storage

### Goal

Allow users to upload PDF documents.

### Tasks

-   Create upload endpoint.
-   Validate PDF files.
-   Validate file size.
-   Generate stable document IDs.
-   Save files locally.
-   Create document metadata.
-   Build document library UI.

### Acceptance Criteria

-   User can upload a PDF.
-   Invalid files are rejected.
-   Uploaded documents appear in the UI.
-   Existing documents remain available after restart.

------------------------------------------------------------------------

## Phase 3: PDF Extraction and Chunking

### Goal

Turn uploaded PDFs into searchable text chunks.

### Tasks

-   Implement PDF loading.
-   Extract page content.
-   Implement recursive text splitting.
-   Start with approximately 1000-character chunks and 150-character
    overlap.
-   Preserve document ID and page metadata.
-   Add ingestion status.

### Acceptance Criteria

-   A PDF can be processed into chunks.
-   Chunk count is visible in logs.
-   Page metadata is preserved.
-   Extraction failures are handled gracefully.

------------------------------------------------------------------------

## Phase 4: Embeddings and ChromaDB

### Goal

Create a persistent semantic search index.

### Tasks

-   Integrate local embedding model.
-   Create ChromaDB collection.
-   Store chunk embeddings.
-   Add document metadata.
-   Prevent duplicate indexing.
-   Implement document deletion from the vector store.

### Acceptance Criteria

-   Chunks are embedded successfully.
-   ChromaDB persists between restarts.
-   A document can be deleted.
-   Duplicate uploads do not silently create duplicate vectors.

------------------------------------------------------------------------

## Phase 5: Retrieval

### Goal

Retrieve relevant document chunks for a question.

### Tasks

-   Create retriever service.
-   Implement top-k similarity search.
-   Add optional document filtering.
-   Return source metadata.
-   Add retrieval debugging information for development.

### Acceptance Criteria

-   Relevant chunks are returned for known questions.
-   Document-specific retrieval works.
-   Source page metadata is available.

------------------------------------------------------------------------

## Phase 6: Local LLM and RAG Generation

### Goal

Generate grounded answers using Ollama.

### Tasks

-   Integrate Ollama.
-   Configure the local model.
-   Build grounded prompt.
-   Connect retriever to generation.
-   Implement missing-information fallback.

### Acceptance Criteria

-   A question produces an answer.
-   The answer is based on retrieved context.
-   Unsupported questions trigger a safe fallback.
-   LLM connection failures are handled cleanly.

------------------------------------------------------------------------

## Phase 7: Chat API and Frontend

### Goal

Turn the RAG pipeline into a usable chat application.

### Tasks

-   Create chat endpoint.
-   Build chat interface.
-   Add message history for the active session.
-   Add selected-document filtering.
-   Add loading state.
-   Add error state.
-   Add empty state.

### Acceptance Criteria

-   User can chat with a selected document.
-   User can chat across all documents.
-   Messages display correctly.
-   Errors are understandable.

------------------------------------------------------------------------

## Phase 8: Citations and Document UX

### Goal

Make answers auditable.

### Tasks

-   Return source chunks.
-   Display document name.
-   Display page number.
-   Display source excerpt.
-   Add source cards to chat responses.
-   Add document delete/re-index actions.

### Acceptance Criteria

-   Every grounded answer exposes its retrieved sources.
-   User can identify where an answer came from.
-   Deleted documents stop appearing in retrieval.

------------------------------------------------------------------------

## Phase 9: Evaluation and Reliability

### Goal

Measure whether the RAG system actually works.

### Tasks

-   Create a small evaluation dataset.
-   Include answerable questions.
-   Include unanswerable questions.
-   Test retrieval relevance.
-   Test citation correctness.
-   Test hallucination/fallback behavior.
-   Test duplicate ingestion.
-   Test API failures.

### Acceptance Criteria

-   Evaluation cases are repeatable.
-   Known failure cases are documented.
-   Critical bugs are fixed before polish.

------------------------------------------------------------------------

## Phase 10: UI Polish and Portfolio Readiness

### Goal

Turn the prototype into a polished portfolio project.

### Tasks

-   Improve visual hierarchy.
-   Add responsive behavior.
-   Add processing indicators.
-   Improve source cards.
-   Add empty states.
-   Add application documentation.
-   Add architecture diagram.
-   Add screenshots/GIFs.
-   Add README with setup instructions and technical explanation.

### Acceptance Criteria

-   New user can understand the application quickly.
-   Setup instructions work on a clean machine.
-   Demo flow is reliable.
-   README explains the RAG architecture.

------------------------------------------------------------------------

## Phase 11: Optional Advanced Retrieval

Only start after Version 1 is stable.

Possible additions: - MMR. - Hybrid keyword + vector retrieval. -
Re-ranking. - Query rewriting. - Context compression.

Do not implement all of these automatically. Evaluate whether each
improves retrieval quality first.

------------------------------------------------------------------------

## Phase 12: Optional Advanced Features

Potential future work: - DOCX/Markdown/TXT support. - OCR. - Streaming
generation. - Persistent conversations. - Multiple local models. -
Authentication. - Encryption. - Evaluation dashboard. - Optional cloud
deployment.

These are not required for the initial portfolio version.
