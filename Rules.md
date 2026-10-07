# PersonalDoc AI

## Development Rules

## 1. General Rules

-   Build incrementally.
-   Do not implement future phases early.
-   Prefer simple, readable solutions.
-   Do not introduce dependencies without a concrete reason.
-   Do not rewrite working code unnecessarily.
-   Preserve existing behavior when making changes.

## 2. Architecture Rules

-   Frontend communicates with backend through the API layer.
-   RAG logic must not be embedded directly inside FastAPI route
    handlers.
-   Document ingestion must be separate from retrieval.
-   Retrieval must be separate from LLM generation.
-   External dependencies should be wrapped behind small service
    modules.
-   Do not introduce microservices for Version 1.

## 3. RAG Rules

-   Never pass an entire large document to the LLM when retrieval can
    provide relevant chunks.
-   Preserve document and page metadata.
-   Use overlapping chunks.
-   Start with a simple similarity retriever before adding advanced
    retrieval.
-   Retrieval parameters must be configurable.
-   Do not silently change the embedding model after a vector database
    has been created. Re-index when the embedding model changes.

## 4. Grounding Rules

The model must: - Answer using retrieved context. - State when evidence
is insufficient. - Never invent citations. - Never claim a source
supports something when it does not. - Clearly distinguish an answer
from uncertainty.

Preferred fallback:

> I couldn't find enough information in the selected documents to answer
> that reliably.

## 5. Privacy Rules

-   Documents remain local by default.
-   Do not send document contents to external APIs unless explicitly
    added as an opt-in feature.
-   Do not log document contents.
-   Do not log full user questions in production-style logs unless
    explicitly required for debugging.
-   Never commit user documents to Git.
-   Add data directories to `.gitignore`.

## 6. Security Rules

-   Validate file types.
-   Limit upload sizes.
-   Sanitize filenames.
-   Never construct shell commands directly from user input.
-   Never execute uploaded files.
-   Keep secrets out of source code.
-   Validate API input with Pydantic.

## 7. Error Handling

Every external or failure-prone operation must have useful error
handling.

Errors should: - Be logged appropriately. - Return a safe user-facing
message. - Preserve existing application state where possible.

Do not use:

``` python
except Exception:
    pass
```

unless there is a documented reason.

## 8. Frontend Rules

-   Every network request needs loading and error states.
-   Empty states should be intentional.
-   Avoid giant components.
-   Reuse components for repeated UI patterns.
-   Do not expose raw backend stack traces to users.
-   Keep the interface usable at laptop and desktop widths.

## 9. Dependency Rules

Prefer: - Python standard library where practical. - FastAPI for API. -
React/Vite for UI. - ChromaDB for the initial vector store. - Ollama for
local inference. - Hugging Face/sentence-transformers for local
embeddings.

Avoid adding: - Redux unless state complexity genuinely requires it. - A
second backend framework. - Multiple vector databases. - An agent
framework. - A cloud LLM provider.

## 10. AI Coding-Agent Rules

When working with an AI coding agent:

1.  Read the relevant documentation before modifying code.
2.  Work only on the current phase.
3.  Inspect existing code before creating replacements.
4.  Explain architectural changes in the phase summary.
5.  Run tests after meaningful changes.
6.  Fix errors before moving to the next phase.
7.  Update `Memory.md` after completing a phase.
8.  Never claim a feature works without testing it.
9.  Never delete working functionality merely to simplify
    implementation.
10. Ask for clarification only when a decision cannot reasonably be
    inferred from the project documents.

## 11. Definition of Done

A phase is complete only when: - Its acceptance criteria are
satisfied. - The application starts successfully. - Relevant tests
pass. - No known blocking errors remain. - Documentation is updated. -
`Memory.md` reflects the new project state.
