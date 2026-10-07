# PersonalDoc AI

## Product Requirements Document

## 1. Product Overview

PersonalDoc AI is a privacy-first, local Retrieval-Augmented Generation
(RAG) application that lets a user upload personal documents and chat
with them using a locally running Large Language Model.

The project is inspired by the local RAG pipeline described in Aman
Kharwal's "Create a ChatGPT for Your Personal Documents" article. The
reference implementation uses PDF loading, recursive chunking, Hugging
Face embeddings, ChromaDB, and Ollama/Mistral. This project will extend
that basic tutorial into a portfolio-quality application with a proper
document library, citations, document-scoped conversations, error
handling, and evaluation.

Reference article:
https://amanxai.com/2026/08/02/create-a-chatgpt-for-your-personal-documents/

## 2. Problem Statement

People often have large collections of PDFs and other documents that are
difficult to search manually. Sending private documents to external LLM
APIs can also create privacy and cost concerns.

The application should provide a local alternative where documents
remain on the user's machine and answers are generated from retrieved
document content.

## 3. Target Users

### Primary

-   Students studying from lecture notes, textbooks, papers, and
    assignments.
-   Developers and engineers working with technical documentation.
-   Professionals working with reports, specifications, and internal
    documents.
-   Anyone who wants to query a private collection of documents locally.

### Secondary

-   AI/ML learners who want to understand how a production-style RAG
    system works.

## 4. Goals

1.  Allow users to upload documents.
2.  Extract and index document content locally.
3.  Generate semantic embeddings for document chunks.
4.  Store embeddings in a local vector database.
5.  Retrieve relevant chunks for a user question.
6.  Generate answers using a locally hosted LLM.
7.  Show the document sources used to answer each question.
8.  Refuse to invent information when the answer is not supported by
    retrieved context.
9.  Support multiple documents.
10. Provide a clean, responsive web interface.
11. Make the system modular enough to replace the embedding model,
    vector database, or LLM later.

## 5. Non-Goals for Version 1

-   User accounts and multi-user authentication.
-   Cloud document storage.
-   Training/fine-tuning an LLM.
-   Autonomous agents.
-   Web search.
-   OCR for every possible scanned-document format.
-   Mobile-native applications.
-   Enterprise-scale distributed infrastructure.

These can be considered later.

## 6. Core Features

### F1. Document Upload

-   Upload supported documents.
-   Validate file type and size.
-   Store files locally.
-   Display processing status.

### F2. Document Processing

-   Extract text and page metadata.
-   Split text into overlapping chunks.
-   Generate embeddings.
-   Store vectors locally.
-   Preserve document name and page metadata.

### F3. Document Library

-   List indexed documents.
-   Show document status and basic metadata.
-   Delete documents.
-   Re-index a document.

### F4. Chat

-   Ask natural-language questions.
-   Retrieve relevant chunks.
-   Generate an answer from retrieved context.
-   Display loading and error states.
-   Preserve conversation history during a session.

### F5. Source Citations

Every answer should expose the document sources used by retrieval,
including: - Document name. - Page number when available. - Relevant
source excerpt.

### F6. Document Scope

The user should be able to: - Chat with one selected document. - Chat
across all indexed documents.

### F7. Grounded Answers

The model must answer from retrieved context only.

If sufficient evidence is unavailable, it should explicitly say that the
information could not be found in the selected documents.

### F8. Health/Status UI

The application should show: - Backend status. - LLM availability. -
Number of indexed documents. - Processing errors.

## 7. Functional Requirements

### FR-01

The system shall accept supported document uploads.

### FR-02

The system shall reject unsupported or invalid files with a useful error
message.

### FR-03

The system shall preserve page/document metadata during ingestion.

### FR-04

The system shall create vector embeddings for indexed chunks.

### FR-05

The system shall persist the vector index locally.

### FR-06

The system shall retrieve the most relevant chunks for each query.

### FR-07

The system shall send retrieved context to the local LLM.

### FR-08

The system shall not answer using unsupported information when the
required evidence is absent.

### FR-09

The system shall expose retrieved sources to the frontend.

### FR-10

The system shall allow deletion and re-indexing of documents.

## 8. Quality Requirements

### Privacy

Documents and embeddings should remain local by default.

### Reliability

A failed document should not crash the entire application.

### Explainability

Answers should provide source references.

### Maintainability

Backend components should have clear responsibilities and interfaces.

### Performance

The application should avoid unnecessary re-embedding and should provide
visible processing feedback.

## 9. Success Criteria

Version 1 is successful when a user can:

1.  Start the local application.
2.  Upload a PDF.
3.  See the PDF become indexed.
4.  Ask a question about it.
5.  Receive a grounded answer.
6.  Open the answer's sources and identify the relevant page.
7.  Ask a question whose answer is absent and receive a clear "not
    found" response.
8.  Upload multiple PDFs and query them together.
9.  Delete an indexed document and confirm it is no longer retrievable.

## 10. Future Enhancements

-   DOCX, TXT, Markdown, and HTML support.
-   OCR for scanned PDFs.
-   Hybrid keyword + semantic search.
-   Re-ranking.
-   Streaming responses.
-   Persistent conversation history.
-   Authentication.
-   Encryption at rest.
-   Evaluation dashboard.
-   Multiple local LLM choices.
-   Cloud deployment as an optional mode.
