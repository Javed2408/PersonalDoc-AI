"""Build small, deterministic PDFs in memory for tests (no binary fixtures in the repo)."""

from collections.abc import Sequence

DRAWING_ONLY = object()  # Page with vector graphics but no text, like a scanned/image page


def _escape(text: str) -> str:
    return text.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")


def _content_stream(page: str | object | None) -> bytes:
    if page is None:
        return b""
    if page is DRAWING_ONLY:
        return b"0.5 g 72 72 400 600 re f 0 G 72 72 m 472 672 l S"
    # One Tj per line, moving down with T* so the extractor sees real line breaks.
    lines = "".join(f"({_escape(line)}) Tj T* " for line in str(page).split("\n"))
    return f"BT /F1 10 Tf 12 TL 50 760 Td {lines}ET".encode("latin-1")


def build_pdf(pages: Sequence[str | object | None]) -> bytes:
    """Return PDF bytes with one page per entry.

    An entry can be text (lines separated by newlines), None for a blank page, or
    DRAWING_ONLY for a page that has graphics but no text.
    """
    count = len(pages)
    font_id = 3 + 2 * count
    objects: list[bytes] = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [%s] /Count %d >>"
        % (b" ".join(b"%d 0 R" % (3 + 2 * i) for i in range(count)), count),
    ]
    for i, page in enumerate(pages):
        content_id = 4 + 2 * i
        objects.append(
            b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents %d 0 R "
            b"/Resources << /Font << /F1 %d 0 R >> >> >>" % (content_id, font_id)
        )
        stream = _content_stream(page)
        objects.append(b"<< /Length %d >>\nstream\n%s\nendstream" % (len(stream), stream))
    objects.append(b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>")

    pdf = bytearray(b"%PDF-1.4\n")
    offsets = []
    for number, body in enumerate(objects, start=1):
        offsets.append(len(pdf))
        pdf += b"%d 0 obj\n%s\nendobj\n" % (number, body)
    xref = len(pdf)
    pdf += b"xref\n0 %d\n0000000000 65535 f \n" % (len(objects) + 1)
    for offset in offsets:
        pdf += b"%010d 00000 n \n" % offset
    pdf += b"trailer\n<< /Size %d /Root 1 0 R >>\nstartxref\n%d\n%%%%EOF\n" % (len(objects) + 1, xref)
    return bytes(pdf)


def paragraph(prefix: str, sentences: int) -> str:
    """Deterministic filler text: numbered sentences, wrapped into ~80-character lines."""
    words = " ".join(f"{prefix} sentence {n} describes local document processing." for n in range(1, sentences + 1))
    lines, current = [], ""
    for word in words.split(" "):
        if current and len(current) + 1 + len(word) > 80:
            lines.append(current)
            current = word
        else:
            current = f"{current} {word}".strip()
    lines.append(current)
    return "\n".join(lines)
