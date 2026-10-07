"""PDF -> pages -> chunks. Pure processing: no persistence or status handling."""

from dataclasses import dataclass
from pathlib import Path

from app.ingestion.loader import ExtractionError, PageText, extract_pages
from app.ingestion.splitter import RecursiveTextSplitter
from app.models.schemas import Chunk


@dataclass(frozen=True)
class ProcessedDocument:
    page_count: int
    chunks: list[Chunk]


def make_chunk_id(document_id: str, chunk_index: int) -> str:
    # Deterministic, so re-processing the same document yields the same IDs.
    return f"{document_id}-{chunk_index:05d}"


def chunk_pages(
    pages: list[PageText],
    splitter: RecursiveTextSplitter,
    document_id: str,
    original_filename: str,
) -> list[Chunk]:
    """Chunk each page on its own, so every chunk belongs to exactly one page."""
    chunks: list[Chunk] = []
    for page in pages:
        for piece in splitter.split(page.text):
            index = len(chunks)
            chunks.append(
                Chunk(
                    chunk_id=make_chunk_id(document_id, index),
                    document_id=document_id,
                    original_filename=original_filename,
                    page_number=page.page_number,
                    chunk_index=index,
                    start_char=piece.start,
                    char_count=len(piece.text),
                    text=piece.text,
                )
            )
    return chunks


def process_pdf(
    path: Path,
    document_id: str,
    original_filename: str,
    splitter: RecursiveTextSplitter,
) -> ProcessedDocument:
    pages = extract_pages(path)
    if not pages:
        raise ExtractionError("The PDF has no pages.")

    chunks = chunk_pages(pages, splitter, document_id, original_filename)
    if not chunks:
        raise ExtractionError(
            "No extractable text was found. Scanned or image-only PDFs are not supported yet."
        )
    return ProcessedDocument(page_count=len(pages), chunks=chunks)
