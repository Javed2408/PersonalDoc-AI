# PersonalDoc AI

## Architecture Document

## 1. Architecture Goal

Build a modular local RAG system in which ingestion, retrieval,
generation, API, and frontend responsibilities are separated.

The initial implementation should favor simplicity and local execution
while leaving clean extension points for future improvements.

## 2. High-Level Architecture

``` text
                    ┌──────────────────────┐
                    │      Frontend        │
                    │ React + Vite         │
                    └──────────┬───────────┘
                               │ HTTP/JSON
                               ▼
                    ┌──────────────────────┐
                    │       FastAPI        │
                    │ REST API             │
                    └───────┬───────┬──────┘
                            │       │
               ┌────────────┘       └─────────────┐
               ▼                                  ▼
      ┌─────────────────┐               ┌─────────────────┐
      │ Ingestion       │               │ RAG Service     │
      │ PDF/Text loader │               │ Retrieval       │
      │ Chunking        │               │ Prompting       │
      │ Metadata        │               │ Generation      │
      └────────┬────────┘               └───────┬─────────┘
               │                                │
               ▼                                ▼
      ┌─────────────────┐               ┌─────────────────┐
      │ Embedding Model │               │ Ollama          │
      │ MiniLM initially│               │ Local LLM       │
      └────────┬────────┘               └─────────────────┘
               │
               ▼
      ┌─────────────────┐
      │ ChromaDB        │
      │ Local vectors   │
      └─────────────────┘
```

## 3. Recommended Stack

### Frontend

-   React
-   Vite
-   CSS or a lightweight component approach

### Backend

-   Python
-   FastAPI
-   Pydantic

### RAG

-   LangChain components where they simplify integration
-   PyPDF for PDF extraction
-   RecursiveCharacterTextSplitter for initial chunking
-   sentence-transformers / Hugging Face embeddings
-   ChromaDB for local vector storage
-   Ollama for local LLM inference

The reference tutorial uses: - `PyPDFLoader` -
`RecursiveCharacterTextSplitter` - `HuggingFaceEmbeddings` - `Chroma` -
`OllamaLLM`

## 4. Backend Structure

``` text
backend/
├── app/
│   ├── main.py
│   ├── config.py
│   │
│   ├── api/
│   │   ├── documents.py
│   │   ├── chat.py
│   │   └── health.py
│   │
│   ├── ingestion/
│   │   ├── loader.py
│   │   ├── splitter.py
│   │   ├── metadata.py
│   │   └── pipeline.py
│   │
│   ├── retrieval/
│   │   ├── embeddings.py
│   │   ├── vector_store.py
│   │   └── retriever.py
│   │
│   ├── generation/
│   │   ├── llm.py
│   │   ├── prompts.py
│   │   └── rag_chain.py
│   │
│   ├── models/
│   │   └── schemas.py
│   │
│   └── services/
│       ├── document_service.py
│       └── chat_service.py
│
├── data/
│   ├── documents/
│   └── chroma/
│
├── tests/
└── requirements.txt
```

## 5. Frontend Structure

``` text
frontend/
├── src/
│   ├── components/
│   │   ├── Chat/
│   │   ├── Documents/
│   │   ├── Sources/
│   │   └── Common/
│   │
│   ├── pages/
│   │   ├── ChatPage.jsx
│   │   └── DocumentsPage.jsx
│   │
│   ├── services/
│   │   └── api.js
│   │
│   ├── hooks/
│   ├── styles/
│   ├── App.jsx
│   └── main.jsx
│
└── package.json
```

## 6. Core Data Flow

### Ingestion

``` text
Upload
  ↓
Validate
  ↓
Save locally
  ↓
Extract text
  ↓
Split into chunks
  ↓
Attach metadata
  ↓
Generate embeddings
  ↓
Store in ChromaDB
  ↓
Mark document indexed
```

### Query

``` text
User question
  ↓
Validate request
  ↓
Embed question
  ↓
Vector similarity search
  ↓
Retrieve top-k chunks
  ↓
Build grounded prompt
  ↓
Ollama local LLM
  ↓
Answer + source metadata
  ↓
Frontend
```

## 7. API Design

### `GET /api/health`

Returns application and dependency health.

### `GET /api/documents`

Returns indexed documents.

### `POST /api/documents/upload`

Uploads and indexes a document.

### `DELETE /api/documents/{document_id}`

Deletes a document and its indexed chunks.

### `POST /api/documents/{document_id}/reindex`

Reprocesses a document.

### `POST /api/chat`

Request:

``` json
{
  "question": "What are the main findings?",
  "document_ids": ["optional-id"],
  "conversation_id": "optional-id"
}
```

Response:

``` json
{
  "answer": "The report identifies...",
  "sources": [
    {
      "document": "report.pdf",
      "page": 14,
      "excerpt": "..."
    }
  ]
}
```

## 8. Retrieval Strategy

Initial version: - Similarity search. - `k = 4` initially. - Metadata
filtering for document scope. - Preserve source metadata.

Later: - Similarity threshold. - MMR retrieval. - Hybrid BM25 + vector
search. - Cross-encoder re-ranking.

Do not add these advanced retrieval techniques until the baseline works.

## 9. LLM Strategy

Initial local model: - Ollama - Mistral or another suitable instruction
model available locally.

The LLM must receive: 1. System instructions. 2. Retrieved context. 3.
User question.

The LLM should not receive the entire document collection.

## 10. Prompt Strategy

The generation prompt must: - Restrict answers to supplied context. -
Explicitly handle missing information. - Avoid pretending that
unsupported claims are facts. - Preserve useful source references.

## 11. Persistence

Local directories:

``` text
data/documents/
data/chroma/
```

The application should not regenerate embeddings every time it starts.

## 12. Error Boundaries

Errors should be isolated at: - File validation. - Text extraction. -
Chunking. - Embedding. - Vector storage. - LLM connection. - API
validation. - Frontend network calls.

A failed upload should not make existing indexed documents unavailable.

## 13. Architecture Principles

1.  Keep ingestion independent from chat.
2.  Keep the LLM provider replaceable.
3.  Keep the embedding model replaceable.
4.  Keep vector storage behind a service interface.
5.  Preserve metadata through every stage.
6.  Prefer local processing by default.
7.  Avoid premature microservices.
8.  Build a working vertical slice before adding advanced features.
