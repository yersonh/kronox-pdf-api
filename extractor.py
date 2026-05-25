"""
Responsabilidad: recibir bytes de un PDF y devolver su texto sin importar el tipo.

Paso 1 — pdfplumber: extrae texto y tablas de PDFs nativos digitales.
Paso 2 — Si el texto es insuficiente (PDF escaneado/foto): PyMuPDF renderiza
          cada página como imagen y pytesseract hace OCR sobre ella.
Paso 3 — Devuelve el texto limpio consolidado de todas las páginas.
"""

import io

import fitz  # pymupdf
import pdfplumber
import pytesseract
from PIL import Image

_MIN_DIGITAL_CHARS = 100
_OCR_ZOOM = 2.0
_OCR_MAX_PAGES = 15


def extract_text(pdf_bytes: bytes) -> tuple[str, list[list], str]:
    """
    Returns (text, tables, method).
      - text: full document text
      - tables: raw pdfplumber tables (list of rows)
      - method: "digital" or "ocr"
    """
    digital_text, tables = _extract_digital(pdf_bytes)

    if len(digital_text.strip()) >= _MIN_DIGITAL_CHARS:
        return digital_text.strip(), tables, "digital"

    ocr_text = _extract_ocr(pdf_bytes)
    return ocr_text.strip(), tables, "ocr"


def _extract_digital(pdf_bytes: bytes) -> tuple[str, list[list]]:
    pages: list[str] = []
    tables: list[list] = []

    with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
        for page in pdf.pages:
            text = page.extract_text() or ""
            pages.append(text)

            for table in page.extract_tables():
                if table:
                    tables.append(table)

    return "\n\n".join(pages), tables


def _extract_ocr(pdf_bytes: bytes) -> str:
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    pages: list[str] = []
    mat = fitz.Matrix(_OCR_ZOOM, _OCR_ZOOM)

    try:
        for i, page in enumerate(doc):
            if i >= _OCR_MAX_PAGES:
                break

            pix = page.get_pixmap(matrix=mat)
            img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
            text = pytesseract.image_to_string(img, lang="spa+eng")
            pages.append(text)
    finally:
        doc.close()

    return "\n\n".join(pages)
