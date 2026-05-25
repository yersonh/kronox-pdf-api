"""
Responsabilidad: recibir el texto extraído del PDF, enviarlo a Gemini con
un prompt diseñado para contratos y evidencias, y devolver el JSON estructurado.
"""

import json
import os
import re

import google.generativeai as genai

from models import AnalysisResponse, TableItem

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
