import os
import secrets

import uvicorn
from dotenv import load_dotenv
from fastapi import Depends, FastAPI, File, Header, HTTPException, UploadFile

from analyzer import analyze, analyze_minuta, analyze_planilla, analyze_supervisor
from extractor import extract_text
from models import AnalysisResponse, ExtractResponse, MinutaAnalysisResponse, PlanillaAnalysisResponse, SupervisorAnalysisResponse

load_dotenv()

app = FastAPI(title="PDF Analyzer API", version="1.0.0")

# Tamaño máximo de archivo aceptado (50 MB). Evita agotar memoria y limita el abuso.
MAX_FILE_SIZE = 50 * 1024 * 1024


def verificar_api_key(x_api_key: str = Header(None)):
    """
    Exige una clave compartida en el header X-API-Key.
    Solo SAA-Agenda (que conoce la clave) puede llamar a estos endpoints,
    evitando que cualquiera en internet consuma la cuota de Gemini.
    """
    esperado = os.getenv("API_KEY")

    # Si no hay clave configurada en el servidor, se rechaza todo por seguridad.
    if not esperado:
        raise HTTPException(status_code=503, detail="Servicio no configurado.")

    if not x_api_key or not secrets.compare_digest(x_api_key, esperado):
        raise HTTPException(status_code=401, detail="No autorizado.")


@app.get("/health")
def health():
    """Railway uses this to confirm the service started correctly."""
    return {"status": "ok"}


@app.post("/extract", response_model=ExtractResponse, dependencies=[Depends(verificar_api_key)])
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


@app.post("/analyze", response_model=AnalysisResponse, dependencies=[Depends(verificar_api_key)])
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


@app.post("/analyze-minuta", response_model=MinutaAnalysisResponse, dependencies=[Depends(verificar_api_key)])
async def analyze_minuta_pdf(archivo: UploadFile = File(...)):
    """
    Specialized endpoint for contract minutas.
    Uses text extraction for digital PDFs (fast) and Gemini Vision
    as fallback for scanned/image-based PDFs.
    """
    pdf_bytes = await _read_pdf(archivo)

    text, _, method = extract_text(pdf_bytes)

    return analyze_minuta(pdf_bytes, text, method)


@app.post("/analyze-planilla", response_model=PlanillaAnalysisResponse, dependencies=[Depends(verificar_api_key)])
async def analyze_planilla_pdf(archivo: UploadFile = File(...)):
    """Extrae datos de seguridad social de una planilla de pago."""
    pdf_bytes = await _read_pdf(archivo)
    text, _, method = extract_text(pdf_bytes)
    return analyze_planilla(pdf_bytes, text, method)


@app.post("/analyze-supervisor", response_model=SupervisorAnalysisResponse, dependencies=[Depends(verificar_api_key)])
async def analyze_supervisor_pdf(archivo: UploadFile = File(...)):
    """
    Specialized endpoint for supervisor resolution documents.
    Extracts: supervisor name/cedula, acta inicio date, termination date,
    adicion/prorroga, report period, and city/date of presentation.
    """
    pdf_bytes = await _read_pdf(archivo)
    text, _, method = extract_text(pdf_bytes)
    return analyze_supervisor(pdf_bytes, text, method)


async def _read_pdf(archivo: UploadFile) -> bytes:
    if not (archivo.filename or "").lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Solo se aceptan archivos PDF.")

    content = await archivo.read()

    if not content:
        raise HTTPException(status_code=400, detail="El archivo está vacío.")

    if len(content) > MAX_FILE_SIZE:
        raise HTTPException(status_code=413, detail="El archivo supera el tamaño máximo de 50 MB.")

    return content


if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=int(os.getenv("PORT", 8000)),
        reload=True,
    )
