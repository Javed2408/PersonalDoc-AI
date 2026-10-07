"""Unit tests for PDF extraction, recursive splitting and the chunking pipeline."""

import io

import pytest
from pypdf import PdfReader, PdfWriter

from app.ingestion.loader import ExtractionError, extract_pages, normalize_text
from app.ingestion.pipeline import chunk_pages, make_chunk_id, process_pdf
from app.ingestion.splitter import RecursiveTextSplitter
from tests.conftest import MINIMAL_PDF
from tests.pdf_factory import DRAWING_ONLY, build_pdf, paragraph

DOCUMENT_ID = "0123456789abcdef0123456789abcdef"

# The quality-check document: two short pages with known text.
QUALITY_PAGES = [
    "PersonalDoc AI extraction test.\nThis text lives on the first page.",
    "Second page extraction test.\nThis text lives on the second page.",
]


@pytest.fixture
def write_pdf(tmp_path):
    def factory(pages, name="doc.pdf"):
        path = tmp_path / name
        path.write_bytes(build_pdf(pages))
        return path

    return factory


@pytest.fixture
def splitter():
    return RecursiveTextSplitter(chunk_size=1000, chunk_overlap=150)


# --- Extraction -------------------------------------------------------------


def test_extracts_text_from_normal_pdf(write_pdf):
    pages = extract_pages(write_pdf(["PersonalDoc AI extraction test"]))

    assert len(pages) == 1
    assert pages[0].page_number == 1
    assert pages[0].text == "PersonalDoc AI extraction test"


def test_extracts_each_page_separately_with_page_numbers(write_pdf):
    pages = extract_pages(write_pdf(QUALITY_PAGES + ["Third page text."]))

    assert [page.page_number for page in pages] == [1, 2, 3]
    assert pages[0].text == QUALITY_PAGES[0]
    assert pages[1].text == QUALITY_PAGES[1]
    assert pages[2].text == "Third page text."
    # Page boundaries are kept: no page's text leaks into another.
    assert "Second page" not in pages[0].text
    assert "PersonalDoc AI" not in pages[1].text


def test_empty_and_drawing_only_pages_are_kept_with_empty_text(write_pdf):
    pages = extract_pages(write_pdf(["First.", None, DRAWING_ONLY, "Fourth."]))

    assert [(page.page_number, page.text) for page in pages] == [
        (1, "First."), (2, ""), (3, ""), (4, "Fourth."),
    ]


def test_special_characters_survive_extraction(write_pdf):
    pages = extract_pages(write_pdf(["Costs (approx.) rose 5% - see C:\\data"]))

    assert pages[0].text == "Costs (approx.) rose 5% - see C:\\data"


def test_corrupted_pdf_raises_readable_error(tmp_path):
    path = tmp_path / "broken.pdf"
    path.write_bytes(b"%PDF-1.4\n" + b"\x00garbage that is not a pdf body\n" * 20)

    with pytest.raises(ExtractionError, match="could not be read. It may be corrupted"):
        extract_pages(path)


def test_truncated_pdf_raises_readable_error(tmp_path):
    path = tmp_path / "truncated.pdf"
    path.write_bytes(build_pdf(QUALITY_PAGES)[:200])

    with pytest.raises(ExtractionError):
        extract_pages(path)


def test_missing_file_raises_readable_error(tmp_path):
    with pytest.raises(ExtractionError, match="stored PDF file is missing"):
        extract_pages(tmp_path / "nope.pdf")


def test_password_protected_pdf_is_rejected(tmp_path):
    writer = PdfWriter(clone_from=PdfReader(io.BytesIO(build_pdf(QUALITY_PAGES))))
    writer.encrypt(user_password="secret", algorithm="RC4-128")
    path = tmp_path / "locked.pdf"
    with path.open("wb") as handle:
        writer.write(handle)

    with pytest.raises(ExtractionError, match="Password-protected"):
        extract_pages(path)


def test_file_is_released_after_extraction(write_pdf):
    path = write_pdf(QUALITY_PAGES)
    extract_pages(path)

    path.unlink()  # Would fail on Windows if the extractor kept the file open.
    assert not path.exists()


def test_normalize_text_cleans_whitespace_and_control_characters():
    raw = "  Title  \r\nline one   \rline two\x00\n\n\n\n\nnext para  "

    assert normalize_text(raw) == "Title\nline one\nline two\n\nnext para"


# --- Splitter ---------------------------------------------------------------


def assert_exact_slices(text, chunks):
    for chunk in chunks:
        assert text[chunk.start:chunk.start + len(chunk.text)] == chunk.text


def test_short_text_is_one_chunk_with_correct_offset(splitter):
    chunks = splitter.split("  \n Short page text.  ")

    assert [(c.text, c.start) for c in chunks] == [("Short page text.", 4)]


def test_empty_or_whitespace_text_produces_no_chunks(splitter):
    assert splitter.split("") == []
    assert splitter.split(" \n\n \t ") == []


def test_chunks_never_exceed_chunk_size(splitter):
    text = paragraph("Size", 300)

    chunks = splitter.split(text)

    assert len(chunks) > 5
    assert all(len(c.text) <= 1000 for c in chunks)
    assert_exact_slices(text, chunks)


def test_chunks_are_close_to_target_size(splitter):
    text = " ".join(f"word{n}" for n in range(3000))

    chunks = splitter.split(text)

    # All but the last chunk should be well filled, not fragmented.
    assert all(850 <= len(c.text) <= 1000 for c in chunks[:-1])


def test_consecutive_chunks_overlap_by_at_most_chunk_overlap(splitter):
    text = " ".join(f"word{n}" for n in range(3000))

    chunks = splitter.split(text)

    for previous, current in zip(chunks, chunks[1:]):
        overlap = previous.start + len(previous.text) - current.start
        assert 100 <= overlap <= 150
        assert previous.text[-overlap:] == current.text[:overlap]


def test_zero_overlap_produces_adjacent_chunks():
    text = " ".join(f"word{n}" for n in range(1000))

    chunks = RecursiveTextSplitter(chunk_size=200, chunk_overlap=0).split(text)

    for previous, current in zip(chunks, chunks[1:]):
        assert current.start >= previous.start + len(previous.text)


def test_all_text_is_covered_by_chunks(splitter):
    text = paragraph("Coverage", 200)

    chunks = splitter.split(text)

    covered = set()
    for chunk in chunks:
        covered.update(range(chunk.start, chunk.start + len(chunk.text)))
    assert all(i in covered for i, ch in enumerate(text) if not ch.isspace())


def test_prefers_paragraph_boundaries():
    first, second = "A" * 500 + " end.", "B" * 500 + " end."

    chunks = RecursiveTextSplitter(chunk_size=1000, chunk_overlap=150).split(f"{first}\n\n{second}")

    assert [c.text for c in chunks] == [first, second]


def test_unbroken_text_falls_back_to_characters():
    text = "x" * 2500

    chunks = RecursiveTextSplitter(chunk_size=1000, chunk_overlap=150).split(text)

    assert [len(c.text) for c in chunks] == [1000, 1000, 800]
    assert [c.start for c in chunks] == [0, 850, 1700]


def test_splitting_is_deterministic(splitter):
    text = paragraph("Determinism", 150)

    assert splitter.split(text) == splitter.split(text)


@pytest.mark.parametrize(("size", "overlap"), [(0, 0), (100, 100), (100, 150), (100, -1)])
def test_invalid_splitter_settings_are_rejected(size, overlap):
    with pytest.raises(ValueError):
        RecursiveTextSplitter(chunk_size=size, chunk_overlap=overlap)


# --- Pipeline ---------------------------------------------------------------


def test_quality_document_produces_one_chunk_per_page(write_pdf, splitter):
    result = process_pdf(write_pdf(QUALITY_PAGES), DOCUMENT_ID, "quality.pdf", splitter)

    assert result.page_count == 2
    assert [(c.page_number, c.text) for c in result.chunks] == [(1, QUALITY_PAGES[0]), (2, QUALITY_PAGES[1])]
    first = result.chunks[0]
    assert first.document_id == DOCUMENT_ID
    assert first.original_filename == "quality.pdf"
    assert first.chunk_index == 0
    assert first.chunk_id == f"{DOCUMENT_ID}-00000"
    assert first.start_char == 0
    assert first.char_count == len(QUALITY_PAGES[0])


def test_chunks_never_span_pages_and_point_back_to_their_page(write_pdf, splitter):
    page_texts = [paragraph("Alpha", 60), None, paragraph("Gamma", 45), "Short final page."]
    path = write_pdf(page_texts)
    pages = extract_pages(path)

    result = process_pdf(path, DOCUMENT_ID, "multi.pdf", splitter)

    assert {c.page_number for c in result.chunks} == {1, 3, 4}  # Page 2 is blank
    for chunk in result.chunks:
        page_text = pages[chunk.page_number - 1].text
        assert page_text[chunk.start_char:chunk.start_char + chunk.char_count] == chunk.text
    # Chunks are ordered by page, then position.
    keys = [(c.page_number, c.start_char) for c in result.chunks]
    assert keys == sorted(keys)


def test_chunk_indexes_and_ids_are_sequential_and_unique(write_pdf, splitter):
    result = process_pdf(write_pdf([paragraph("One", 50), paragraph("Two", 50)]), DOCUMENT_ID, "a.pdf", splitter)

    assert [c.chunk_index for c in result.chunks] == list(range(len(result.chunks)))
    ids = [c.chunk_id for c in result.chunks]
    assert len(set(ids)) == len(ids)
    assert ids == [make_chunk_id(DOCUMENT_ID, i) for i in range(len(ids))]
    assert {c.document_id for c in result.chunks} == {DOCUMENT_ID}


def test_processing_is_deterministic(write_pdf, splitter):
    path = write_pdf([paragraph("Repeat", 80)])

    assert process_pdf(path, DOCUMENT_ID, "r.pdf", splitter) == process_pdf(path, DOCUMENT_ID, "r.pdf", splitter)


def test_pdf_without_extractable_text_fails_clearly(write_pdf, splitter):
    path = write_pdf([None, DRAWING_ONLY])

    with pytest.raises(ExtractionError, match="No extractable text was found"):
        process_pdf(path, DOCUMENT_ID, "scan.pdf", splitter)


def test_pdf_with_no_pages_fails_clearly(tmp_path, splitter):
    path = tmp_path / "empty.pdf"
    path.write_bytes(MINIMAL_PDF)

    with pytest.raises(ExtractionError):
        process_pdf(path, DOCUMENT_ID, "empty.pdf", splitter)


def test_chunk_pages_skips_empty_pages(splitter):
    from app.ingestion.loader import PageText

    chunks = chunk_pages([PageText(1, ""), PageText(2, "Only text.")], splitter, DOCUMENT_ID, "x.pdf")

    assert [(c.page_number, c.chunk_index, c.text) for c in chunks] == [(2, 0, "Only text.")]
