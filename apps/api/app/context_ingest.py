"""Extract plain text from uploaded context files (txt, md, pdf) for Decision Room."""

from __future__ import annotations

import re
from io import BytesIO
from typing import Final

from fastapi import HTTPException, UploadFile

# Raw upload cap (bytes) before extraction.
MAX_UPLOAD_BYTES: Final[int] = 8 * 1024 * 1024
# Debate context cap (characters) — also enforced on POST /debate/stream and in the web UI.
MAX_CONTEXT_CHARS: Final[int] = 500
MAX_EXTRACTED_CHARS: Final[int] = MAX_CONTEXT_CHARS

_TEXT_LIKE = frozenset(
    {
        "text/plain",
        "text/markdown",
        "text/x-markdown",
    }
)
_PDF = "application/pdf"


def _ext(name: str) -> str:
    if not name or "." not in name:
        return ""
    return name.rsplit(".", 1)[-1].lower()


async def _read_limited(file: UploadFile) -> bytes:
    total = 0
    chunks: list[bytes] = []
    while True:
        piece = await file.read(1024 * 1024)
        if not piece:
            break
        total += len(piece)
        if total > MAX_UPLOAD_BYTES:
            raise HTTPException(
                status_code=413,
                detail=f"File too large (max {MAX_UPLOAD_BYTES // (1024 * 1024)} MB)",
            )
        chunks.append(piece)
    return b"".join(chunks)


def _decode_text(raw: bytes) -> str:
    return raw.decode("utf-8", errors="replace")


def _extract_pdf(raw: bytes) -> str:
    try:
        from pypdf import PdfReader
    except ImportError as e:
        raise HTTPException(status_code=500, detail="PDF support not available") from e
    try:
        reader = PdfReader(BytesIO(raw))
        parts: list[str] = []
        for page in reader.pages:
            t = page.extract_text()
            if t:
                parts.append(t)
        return "\n\n".join(parts)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Could not read PDF: {e!s}") from e


def _normalize_whitespace(s: str) -> str:
    s = s.replace("\r\n", "\n").replace("\r", "\n")
    s = re.sub(r"\n{3,}", "\n\n", s)
    return s.strip()


async def extract_text_from_upload(file: UploadFile) -> dict[str, str | bool]:
    """
    Returns {"text": str, "truncated": bool}.
    """
    filename = file.filename or "upload"
    ext = _ext(filename)
    content_type = (file.content_type or "").split(";")[0].strip().lower()

    raw = await _read_limited(file)

    if not raw:
        raise HTTPException(status_code=400, detail="Empty file")

    is_pdf = content_type == _PDF or ext == "pdf" or (
        content_type == "application/octet-stream" and ext == "pdf"
    )
    is_text = (
        content_type in _TEXT_LIKE
        or ext in ("txt", "md", "markdown")
        or (
            content_type == "application/octet-stream"
            and ext in ("txt", "md", "markdown")
        )
    )

    if is_pdf:
        text = _extract_pdf(raw)
    elif is_text:
        text = _decode_text(raw)
    else:
        raise HTTPException(
            status_code=400,
            detail="Unsupported type. Use .txt, .md, or .pdf",
        )

    text = _normalize_whitespace(text)
    if not text:
        raise HTTPException(status_code=400, detail="No extractable text in file")

    truncated = len(text) > MAX_EXTRACTED_CHARS
    if truncated:
        text = text[:MAX_EXTRACTED_CHARS]

    return {"text": text, "truncated": truncated}
