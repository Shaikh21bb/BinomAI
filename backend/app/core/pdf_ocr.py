"""Bounded, local OCR fallback for scanned pages in a quick PDF check."""

from __future__ import annotations

import io
import shutil
import subprocess
import tempfile
import time
from pathlib import Path

from pypdf import PdfReader


MAX_OCR_PAGES = 12
OCR_DEADLINE_SECONDS = 90
MIN_TEXT_CHARS = 40


class PdfOcrUnavailableError(Exception):
    """The local PDF renderer or required OCR language data is unavailable."""


class PdfOcrLimitError(Exception):
    """The document exceeds the bounded quick-check OCR workload."""


class PdfOcrProcessingError(Exception):
    """A page could not be rendered or recognized safely."""


def _ocr_languages() -> str:
    if not shutil.which("pdftoppm") or not shutil.which("tesseract"):
        raise PdfOcrUnavailableError("PDF renderer or OCR engine is not installed")
    try:
        result = subprocess.run(
            ["tesseract", "--list-langs"], capture_output=True, text=True, timeout=5,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise PdfOcrUnavailableError("Could not inspect OCR languages") from exc
    available = set(result.stdout.splitlines()) | set(result.stderr.splitlines())
    languages = [code for code in ("rus", "kaz", "eng") if code in available]
    if result.returncode != 0 or not languages:
        raise PdfOcrUnavailableError("Russian, Kazakh, or English OCR data is missing")
    return "+".join(languages)


def _run(command: list[str], *, deadline: float, timeout: int) -> subprocess.CompletedProcess[str]:
    remaining = deadline - time.monotonic()
    if remaining <= 0:
        raise PdfOcrProcessingError("OCR time limit exceeded")
    try:
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=min(timeout, remaining),
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise PdfOcrProcessingError("PDF page OCR timed out or could not start") from exc
    if result.returncode != 0:
        raise PdfOcrProcessingError("PDF page OCR failed")
    return result


def extract_pdf_text_with_ocr(file_bytes: bytes) -> tuple[str, int]:
    """Keep native page text; recognize only pages with no meaningful text layer.

    Returns combined text and the number of pages sent to OCR. Uploaded bytes
    and rendered images exist only in a temporary directory during the request.
    """
    try:
        reader = PdfReader(io.BytesIO(file_bytes))
        page_text = [page.extract_text() or "" for page in reader.pages]
    except Exception as exc:
        raise ValueError("Failed to parse PDF") from exc

    scanned = [index for index, text in enumerate(page_text)
               if sum(char.isalnum() for char in text) < MIN_TEXT_CHARS]
    if not scanned:
        return "\n\n".join(page_text), 0
    if len(scanned) > MAX_OCR_PAGES:
        raise PdfOcrLimitError(f"More than {MAX_OCR_PAGES} scanned pages")

    languages = _ocr_languages()
    deadline = time.monotonic() + OCR_DEADLINE_SECONDS
    with tempfile.TemporaryDirectory(prefix="binom-pdf-ocr-") as temp_dir:
        pdf_path = Path(temp_dir) / "document.pdf"
        pdf_path.write_bytes(file_bytes)
        for index in scanned:
            image_prefix = Path(temp_dir) / f"page-{index + 1}"
            image_path = image_prefix.with_suffix(".png")
            _run(
                ["pdftoppm", "-f", str(index + 1), "-l", str(index + 1),
                 "-singlefile", "-scale-to", "2000", "-gray", "-png",
                 str(pdf_path), str(image_prefix)],
                deadline=deadline,
                timeout=15,
            )
            if not image_path.is_file():
                raise PdfOcrProcessingError("PDF page render did not produce an image")
            result = _run(
                ["tesseract", str(image_path), "stdout", "-l", languages, "--psm", "3"],
                deadline=deadline,
                timeout=25,
            )
            page_text[index] = result.stdout
            image_path.unlink(missing_ok=True)

    return "\n\n".join(page_text), len(scanned)
