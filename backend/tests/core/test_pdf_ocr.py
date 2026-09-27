"""Quick-check OCR must preserve text pages and bound work on scans."""

from pathlib import Path
from types import SimpleNamespace

import pytest

from app.core import pdf_ocr


class FakeReader:
    def __init__(self, texts):
        self.pages = [SimpleNamespace(extract_text=lambda value=text: value) for text in texts]


def test_text_pdf_does_not_call_ocr(monkeypatch):
    monkeypatch.setattr(pdf_ocr, "PdfReader", lambda _: FakeReader(["Товар " * 15]))
    monkeypatch.setattr(pdf_ocr, "_ocr_languages", lambda: pytest.fail("OCR was called for text PDF"))

    text, pages = pdf_ocr.extract_pdf_text_with_ocr(b"%PDF-test")

    assert "Товар" in text
    assert pages == 0


def test_mixed_pdf_ocr_preserves_page_order(monkeypatch):
    first = "Название товара и количество " * 4
    last = "Технические характеристики " * 4
    monkeypatch.setattr(pdf_ocr, "PdfReader", lambda _: FakeReader([first, "", last]))
    monkeypatch.setattr(pdf_ocr, "_ocr_languages", lambda: "rus+kaz+eng")
    calls = []

    def run(command, *, deadline, timeout):
        calls.append(command)
        if command[0] == "pdftoppm":
            Path(f"{command[-1]}.png").write_bytes(b"image")
            return SimpleNamespace(stdout="")
        return SimpleNamespace(stdout="Распознанный товар 62 шт")

    monkeypatch.setattr(pdf_ocr, "_run", run)

    text, pages = pdf_ocr.extract_pdf_text_with_ocr(b"%PDF-test")

    assert pages == 1
    assert text.index(first) < text.index("Распознанный товар") < text.index(last)
    assert calls[0][2:6] == ["2", "-l", "2", "-singlefile"]
    assert calls[1][0] == "tesseract"
    assert calls[1][calls[1].index("-l") + 1] == "rus+kaz+eng"


def test_too_many_scanned_pages_fail_before_ocr(monkeypatch):
    monkeypatch.setattr(pdf_ocr, "PdfReader", lambda _: FakeReader([""] * (pdf_ocr.MAX_OCR_PAGES + 1)))
    monkeypatch.setattr(pdf_ocr, "_ocr_languages", lambda: pytest.fail("OCR should not start"))

    with pytest.raises(pdf_ocr.PdfOcrLimitError):
        pdf_ocr.extract_pdf_text_with_ocr(b"%PDF-test")


def test_missing_ocr_binary_has_clear_error(monkeypatch):
    monkeypatch.setattr(pdf_ocr, "PdfReader", lambda _: FakeReader([""]))
    monkeypatch.setattr(pdf_ocr.shutil, "which", lambda _: None)

    with pytest.raises(pdf_ocr.PdfOcrUnavailableError):
        pdf_ocr.extract_pdf_text_with_ocr(b"%PDF-test")
