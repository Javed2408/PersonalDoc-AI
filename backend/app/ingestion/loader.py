"""PDF text extraction, one entry per page."""

import io
import logging
import re
from dataclasses import dataclass
from pathlib import Path

from pypdf import PdfReader
from pypdf.errors import DependencyError, FileNotDecryptedError, PyPdfError

logger = logging.getLogger(__name__)

_TRAILING_SPACES = re.compile(r"[ \t]+\n")
_EXCESS_BLANK_LINES = re.compile(r"\n{3,}")


class ExtractionError(Exception):
    """The PDF could not be turned into text. `message` is safe to show to users."""

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


@dataclass(frozen=True)
class PageText:
    page_number: int  # 1-based, as shown in PDF viewers
    text: str  # Normalised; empty when the page has no extractable text


def normalize_text(text: str) -> str:
    text = text.replace("\r\n", "\n").replace("\r", "\n").replace("\x00", "")
    text = _TRAILING_SPACES.sub("\n", text)
    text = _EXCESS_BLANK_LINES.sub("\n\n", text)
    return text.strip()


def extract_pages(path: Path) -> list[PageText]:
    """Extract the text of every page, keeping page boundaries and numbers."""
    try:
        # Read into memory and close the file immediately, so the PDF is never held
        # open during extraction (on Windows an open file can't be deleted).
        data = path.read_bytes()
    except FileNotFoundError as error:
        raise ExtractionError("The stored PDF file is missing.") from error
    except OSError as error:
        logger.error("Could not read %s: %s", path.name, error)
        raise ExtractionError("The stored PDF file could not be read.") from error

    try:
        reader = PdfReader(io.BytesIO(data))
        if reader.is_encrypted and not reader.decrypt(""):
            raise ExtractionError("Password-protected PDFs are not supported.")
        pages = list(reader.pages)
    except ExtractionError:
        raise
    except (FileNotDecryptedError, DependencyError) as error:
        raise ExtractionError("Password-protected PDFs are not supported.") from error
    except (PyPdfError, ValueError, KeyError, TypeError, RecursionError) as error:
        logger.warning("Could not parse %s: %s", path.name, error)
        raise ExtractionError("The PDF could not be read. It may be corrupted.") from error

    results = []
    for number, page in enumerate(pages, start=1):
        try:
            text = page.extract_text() or ""
        except Exception as error:  # noqa: BLE001
            # Malformed content streams raise a wide range of errors inside pypdf. One bad
            # page shouldn't sink the whole document, so treat it as a page with no text.
            logger.warning("Could not extract page %d of %s: %s", number, path.name, error)
            text = ""
        results.append(PageText(page_number=number, text=normalize_text(text)))
    return results
