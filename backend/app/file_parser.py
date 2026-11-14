"""Extract plain text from uploaded .txt / .docx files."""
from __future__ import annotations

import io

MAX_UPLOAD_BYTES = 2 * 1024 * 1024  # 2 MB is far more than a draft needs


class UnsupportedFile(ValueError):
    pass


def extract_text(filename: str, data: bytes) -> str:
    if len(data) > MAX_UPLOAD_BYTES:
        raise UnsupportedFile("File is larger than 2 MB.")
    name = filename.lower()

    if name.endswith((".txt", ".md")):
        for enc in ("utf-8-sig", "utf-16", "cp1252", "latin-1"):
            try:
                return data.decode(enc).replace("\r\n", "\n").replace("\r", "\n")
            except UnicodeDecodeError:
                continue
        raise UnsupportedFile("Could not decode the text file.")

    if name.endswith(".docx"):
        try:
            from docx import Document  # lazy import: only needed for .docx
        except ImportError as exc:  # pragma: no cover
            raise UnsupportedFile("python-docx is not installed on the server.") from exc
        try:
            doc = Document(io.BytesIO(data))
        except Exception as exc:
            raise UnsupportedFile("That .docx file could not be read.") from exc
        # One blank line between paragraphs so the segmenter sees them.
        paragraphs = [p.text for p in doc.paragraphs]
        return "\n\n".join(p for p in paragraphs if p.strip())

    raise UnsupportedFile("Only .txt, .md and .docx files are supported.")
