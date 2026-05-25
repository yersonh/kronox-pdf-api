import os

import uvicorn
from dotenv import load_dotenv
from fastapi import FastAPI, File, HTTPException, UploadFile

from analyzer import analyze
from extractor import extract_text
from models import AnalysisResponse, ExtractResponse

load_dotenv()

app = FastAPI(title="PDF Analyzer API", version="1.0.0")


@app.get("/health")
def health():
    """Railway uses this to confirm the service started correctly."""
    return {"status": "ok"}


@app.post("/extract", response_model=ExtractResponse)
async def extract(archivo: UploadFile = File(...)):
    """
    Returns only the raw extracted text from the PDF.
    Useful for debugging extraction before involving Gemini.
    """
    pdf_bytes = await _read_pdf(archivo)

    text, _, method = extract_text(pdf_bytes)

    if not text:
        return ExtractResponse(
            success=False,
            error="No se pudo extraer texto. El PDF puede estar protegido o vacío.",
        )

    return ExtractResponse(success=True, raw_text=text, extraction_method=method)


@app.post("/analyze", response_model=AnalysisResponse)
async def analyze_pdf(archivo: UploadFile = File(...)):
    """
    Main endpoint. Extracts text from the PDF and sends it to Gemini.
    Returns structured JSON with document metadata and evidence analysis.
    """
    pdf_bytes = await _read_pdf(archivo)

    text, tables, _ = extract_text(pdf_bytes)

    if not text:
        return AnalysisResponse(
            success=False,
            error="No se pudo extraer texto. El PDF puede estar protegido o vacío.",
        )

    return analyze(text, tables)


async def _read_pdf(archivo: UploadFile) -> bytes:
    if not (archivo.filename or "").lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Solo se aceptan archivos PDF.")

    content = await archivo.read()

    if not content:
        raise HTTPException(status_code=400, detail="El archivo está vacío.")

    return content


if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=int(os.getenv("PORT", 8000)),
        reload=True,
    )
