"""Recursive character text splitting.

Follows the algorithm of LangChain's RecursiveCharacterTextSplitter: split on the
coarsest separator present (paragraphs, then lines, then words, then characters),
recurse into pieces that are still too long, then merge neighbouring pieces into
chunks of at most `chunk_size` characters that overlap by up to `chunk_overlap`.

Implemented locally instead of depending on langchain-text-splitters, which pulls in
langchain-core and ~30 transitive packages. Unlike LangChain, it works on character
offsets, so every chunk is an exact slice of the input and knows where it starts.
"""

from dataclasses import dataclass

DEFAULT_SEPARATORS = ("\n\n", "\n", " ", "")


@dataclass(frozen=True)
class TextChunk:
    text: str
    start: int  # Offset of text[0] in the original string


class RecursiveTextSplitter:
    def __init__(self, chunk_size: int, chunk_overlap: int, separators: tuple[str, ...] = DEFAULT_SEPARATORS) -> None:
        if chunk_size <= 0:
            raise ValueError("chunk_size must be positive")
        if not 0 <= chunk_overlap < chunk_size:
            raise ValueError("chunk_overlap must be at least 0 and smaller than chunk_size")
        if not separators or separators[-1] != "":
            raise ValueError("separators must end with '' so any text can be split")
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self.separators = separators

    def split(self, text: str) -> list[TextChunk]:
        spans = self._split_spans(text, 0, len(text), self.separators)
        chunks = []
        for start, end in self._merge(spans):
            # Trim surrounding whitespace but keep the offset pointing at real content.
            piece = text[start:end]
            stripped = piece.strip()
            if stripped:
                chunks.append(TextChunk(text=stripped, start=start + (len(piece) - len(piece.lstrip()))))
        return chunks

    def _split_spans(self, text: str, start: int, end: int, separators: tuple[str, ...]) -> list[tuple[int, int]]:
        """Break text[start:end] into contiguous spans of at most chunk_size characters."""
        if end - start <= self.chunk_size:
            return [(start, end)]

        segment = text[start:end]
        index = next(i for i, sep in enumerate(separators) if sep == "" or sep in segment)
        separator, finer = separators[index], separators[index + 1:]

        spans = []
        for piece_start, piece_end in self._pieces(segment, separator, start):
            if piece_end - piece_start <= self.chunk_size:
                spans.append((piece_start, piece_end))
            else:
                spans.extend(self._split_spans(text, piece_start, piece_end, finer))
        return spans

    @staticmethod
    def _pieces(segment: str, separator: str, offset: int) -> list[tuple[int, int]]:
        """Split on `separator`, keeping it attached to the end of the preceding piece."""
        if separator == "":
            return [(offset + i, offset + i + 1) for i in range(len(segment))]
        pieces = []
        cursor = 0
        while (found := segment.find(separator, cursor)) != -1:
            pieces.append((offset + cursor, offset + found + len(separator)))
            cursor = found + len(separator)
        if cursor < len(segment):
            pieces.append((offset + cursor, offset + len(segment)))
        return pieces

    def _merge(self, spans: list[tuple[int, int]]) -> list[tuple[int, int]]:
        """Greedily combine contiguous spans into chunks, carrying overlap forward."""
        chunks = []
        window: list[tuple[int, int]] = []
        total = 0
        for start, end in spans:
            length = end - start
            if window and total + length > self.chunk_size:
                chunks.append((window[0][0], window[-1][1]))
                # Drop spans from the front until what's left fits the overlap budget
                # and leaves room for the next span.
                while window and (total > self.chunk_overlap or total + length > self.chunk_size):
                    first_start, first_end = window.pop(0)
                    total -= first_end - first_start
            window.append((start, end))
            total += length
        if window:
            chunks.append((window[0][0], window[-1][1]))
        return chunks
