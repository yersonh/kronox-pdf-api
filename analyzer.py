"""
Responsabilidad: recibir el texto extraído del PDF, enviarlo a Gemini con
un prompt diseñado para contratos y evidencias, y devolver el JSON estructurado.
"""

import json
import os
import re

import google.generativeai as genai

from models import AnalysisResponse, MinutaAnalysisResponse, SupervisorAnalysisResponse, TableItem

_MODEL = "gemini-2.5-flash"
_MAX_CONTENT_CHARS = 30_000
_MAX_TABLES = 5
_MAX_ROWS_PER_TABLE = 20

_PROMPT = """\
Eres un analizador experto de documentos de evidencia para contratos gubernamentales colombianos.

Analiza el siguiente texto extraído de un PDF y devuelve ÚNICAMENTE un JSON válido con esta estructura:
{{
  "document_type": "tipo de documento (acta, informe, factura, certificado, contrato, memorando, otro)",
  "dates": ["fechas encontradas, preferir formato YYYY-MM-DD; si no se puede, el texto original"],
  "signatories": ["nombres completos de personas o empresas que firman o aparecen como responsables"],
  "amounts": ["valores o montos con su descripción, ej: '$ 5.000.000 - honorarios mes de enero'"],
  "tables": [
    {{
      "title": "nombre o descripción de la tabla si existe, sino vacío",
      "rows": [["col1", "col2"], ["val1", "val2"]]
    }}
  ],
  "summary": "resumen claro del documento en 2-3 oraciones indicando de qué trata y qué demuestra",
  "is_valid_evidence": true
}}

Criterios para is_valid_evidence:
- true si el documento demuestra que se realizó una actividad, entrega, servicio o cumplimiento.
- false si es un documento de planificación, solicitud, borrador o sin evidencia concreta de ejecución.

Usa [] para listas sin datos. No inventes información que no esté en el texto.

TEXTO DEL DOCUMENTO:
{content}"""


def analyze(text: str, tables: list[list]) -> AnalysisResponse:
    api_key = os.getenv("GEMINI_API_KEY")

    if not api_key:
        return AnalysisResponse(
            success=False,
            raw_text=text,
            error="GEMINI_API_KEY no configurada.",
        )

    genai.configure(api_key=api_key)

    content = _prepare_content(text, tables)
    prompt = _PROMPT.format(content=content)

    model = genai.GenerativeModel(
        _MODEL,
        generation_config={"response_mime_type": "application/json"},
    )

    try:
        response = model.generate_content(prompt)
        data = _parse_response(response.text)

        return AnalysisResponse(
            success=True,
            document_type=data.get("document_type", ""),
            dates=data.get("dates", []),
            signatories=data.get("signatories", []),
            amounts=data.get("amounts", []),
            tables=[TableItem(**t) for t in data.get("tables", [])],
            summary=data.get("summary", ""),
            is_valid_evidence=bool(data.get("is_valid_evidence", False)),
            raw_text=text,
        )

    except Exception as e:
        return AnalysisResponse(
            success=False,
            raw_text=text,
            error=str(e),
        )


def _prepare_content(text: str, tables: list[list]) -> str:
    content = text

    tables_text = _format_tables(tables)
    if tables_text:
        content += f"\n\nTABLAS DETECTADAS:\n{tables_text}"

    if len(content) > _MAX_CONTENT_CHARS:
        content = content[:_MAX_CONTENT_CHARS] + "\n...[documento truncado]"

    return content


def _format_tables(tables: list[list]) -> str:
    if not tables:
        return ""

    lines: list[str] = []
    for i, table in enumerate(tables[:_MAX_TABLES], 1):
        lines.append(f"Tabla {i}:")
        for row in table[:_MAX_ROWS_PER_TABLE]:
            lines.append(" | ".join(str(c or "").strip() for c in row))
        lines.append("")

    return "\n".join(lines)


_MINUTA_PROMPT = """\
Eres un experto en contratos de prestación de servicios del sector público colombiano.

Analiza el documento adjunto (minuta de contrato) y devuelve ÚNICAMENTE un JSON válido:
{
  "numero_contrato": "número o código del contrato, ej: '0475' o '0475-2026'",
  "fecha_suscripcion": "fecha en que se suscribió o firmó el contrato, en texto, ej: '21 de enero de 2026'",
  "duracion": "duración del contrato tal como aparece, ej: 'Seis (6) meses' o 'Doce (12) meses'",
  "valor": "valor total del contrato con signo pesos y separadores de miles, ej: '$33.000.000'",
  "contratista_nombre": "nombre completo del contratista persona natural",
  "cedula": "número de cédula del contratista, solo dígitos",
  "objeto": "objeto completo del contrato, texto completo sin recortar"
}

Si no encuentras un campo deja la cadena vacía "". No inventes datos que no estén explícitamente en el documento."""


_MIN_TEXT_FOR_MINUTA = 300  # chars mínimos para considerar el PDF como digital


def analyze_minuta(pdf_bytes: bytes, digital_text: str = "") -> MinutaAnalysisResponse:
    api_key = os.getenv("GEMINI_API_KEY")

    if not api_key:
        return MinutaAnalysisResponse(success=False, error="GEMINI_API_KEY no configurada.")

    genai.configure(api_key=api_key)

    model = genai.GenerativeModel(
        _MODEL,
        generation_config={"response_mime_type": "application/json"},
    )

    try:
        if len(digital_text.strip()) >= _MIN_TEXT_FOR_MINUTA:
            # PDF digital: envía el texto extraído, más rápido y barato
            prompt = _MINUTA_PROMPT + f"\n\nTEXTO DEL CONTRATO:\n{digital_text[:_MAX_CONTENT_CHARS]}"
            response = model.generate_content(prompt)
        else:
            # PDF escaneado: envía el PDF directamente como visión
            import base64
            pdf_part = {
                "inline_data": {
                    "mime_type": "application/pdf",
                    "data": base64.b64encode(pdf_bytes).decode("utf-8"),
                }
            }
            response = model.generate_content([pdf_part, _MINUTA_PROMPT])

        data = _parse_response(response.text)

        return MinutaAnalysisResponse(
            success=True,
            numero_contrato=data.get("numero_contrato", ""),
            fecha_suscripcion=data.get("fecha_suscripcion", ""),
            duracion=data.get("duracion", ""),
            valor=data.get("valor", ""),
            contratista_nombre=data.get("contratista_nombre", ""),
            cedula=data.get("cedula", ""),
            objeto=data.get("objeto", ""),
        )

    except Exception as e:
        return MinutaAnalysisResponse(success=False, error=str(e))


_SUPERVISOR_PROMPT = """\
Eres un experto en contratos del sector público colombiano.

Analiza el documento adjunto (resolución de designación de supervisor de contrato) y devuelve ÚNICAMENTE un JSON válido:
{
  "supervisor_nombre": "nombre completo de la persona designada como supervisora del contrato (no el jefe que firma, sino el supervisor delegado al que se le asigna la función)",
  "supervisor_cedula": "número de cédula del supervisor delegado, solo dígitos",
  "fecha_adicion_prorroga": "fecha de adición o prórroga No. 1 si existe en el documento, si no escribe 'N/A'",
  "valor_adicion_prorroga": "valor y tiempo de adición o prórroga No. 1 si existe, si no escribe 'N/A'"
}

Si no encuentras un campo deja la cadena vacía "". No inventes datos."""


def analyze_supervisor(pdf_bytes: bytes, digital_text: str = "") -> SupervisorAnalysisResponse:
    api_key = os.getenv("GEMINI_API_KEY")

    if not api_key:
        return SupervisorAnalysisResponse(success=False, error="GEMINI_API_KEY no configurada.")

    genai.configure(api_key=api_key)

    model = genai.GenerativeModel(
        _MODEL,
        generation_config={"response_mime_type": "application/json"},
    )

    try:
        if len(digital_text.strip()) >= _MIN_TEXT_FOR_MINUTA:
            prompt = _SUPERVISOR_PROMPT + f"\n\nTEXTO DEL DOCUMENTO:\n{digital_text[:_MAX_CONTENT_CHARS]}"
            response = model.generate_content(prompt)
        else:
            import base64
            pdf_part = {
                "inline_data": {
                    "mime_type": "application/pdf",
                    "data": base64.b64encode(pdf_bytes).decode("utf-8"),
                }
            }
            response = model.generate_content([pdf_part, _SUPERVISOR_PROMPT])

        data = _parse_response(response.text)

        return SupervisorAnalysisResponse(
            success=True,
            supervisor_nombre=data.get("supervisor_nombre", ""),
            supervisor_cedula=data.get("supervisor_cedula", ""),
            fecha_adicion_prorroga=data.get("fecha_adicion_prorroga", ""),
            valor_adicion_prorroga=data.get("valor_adicion_prorroga", ""),
        )

    except Exception as e:
        return SupervisorAnalysisResponse(success=False, error=str(e))


def _parse_response(text: str) -> dict:
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # Gemini sometimes wraps JSON in markdown code blocks
    match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(1))
        except json.JSONDecodeError:
            pass

    return {}
