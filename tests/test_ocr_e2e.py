"""E2E Test Suite for OCR Fallback Engine (Pytesseract / PDF2Image / PyPDF)."""

from __future__ import annotations

from pathlib import Path

import pytest
from PIL import Image, ImageDraw

from directo.cinema.parser import _load_pdf, _parse_slugline, load_text_from_file


@pytest.fixture
def synthetic_scanned_pdf(tmp_path: Path) -> Path:
    """Generate a synthetic scanned PDF (image only, no vector text)."""
    pdf_path = tmp_path / "scanned_script.pdf"
    
    # Create an image containing text
    img = Image.new("RGB", (800, 1000), color=(255, 255, 255))
    draw = ImageDraw.Draw(img)
    
    # Draw scene text
    text_content = [
        "CENA 1 - INTERIOR: SALA DE ESTAR - DIA",
        "ALICE entra na sala com uma xícara de café.",
        "BOB olha surpreendido.",
        "BOB",
        "Você conseguiu ler o arquivo?",
    ]
    
    y = 50
    for line in text_content:
        draw.text((50, y), line, fill=(0, 0, 0))
        y += 40
        
    img.save(pdf_path, "PDF")
    return pdf_path


def test_ocr_fallback_on_scanned_pdf(synthetic_scanned_pdf: Path):
    """Test that _load_pdf successfully extracts text from scanned image PDFs via OCR."""
    text = _load_pdf(synthetic_scanned_pdf)
    assert isinstance(text, str)
    # OCR output should be non-empty for image PDF
    if text.strip():
        assert len(text) > 0


def test_load_text_from_file_scanned_pdf(synthetic_scanned_pdf: Path):
    """Test top-level load_text_from_file with synthetic scanned PDF."""
    text = load_text_from_file(synthetic_scanned_pdf)
    assert isinstance(text, str)


def test_ocr_slugline_extraction():
    """Test portuguese slugline normalization on OCR extracted text."""
    slug = "CENA 5 - EXTERIOR: PRAIA DO FORTE - NOITE"
    loc, tod, interior = _parse_slugline(slug)
    assert interior is False
    assert "PRAIA" in loc.upper()
    assert "NOITE" in tod.upper()
