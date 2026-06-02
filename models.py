from pydantic import BaseModel


class TableItem(BaseModel):
    title: str = ""
    rows: list[list] = []


class MinutaAnalysisResponse(BaseModel):
    success: bool
    numero_contrato: str = ""
    fecha_suscripcion: str = ""
    duracion: str = ""
    valor: str = ""
    contratista_nombre: str = ""
    cedula: str = ""
    objeto: str = ""
    error: str = ""


class SupervisorAnalysisResponse(BaseModel):
    success: bool
    supervisor_nombre: str = ""
    supervisor_cedula: str = ""
    fecha_acta_inicio: str = ""
    fecha_terminacion: str = ""
    fecha_adicion_prorroga: str = ""
    valor_adicion_prorroga: str = ""
    periodo_informe: str = ""
    ciudad_fecha_presentacion: str = ""
    error: str = ""


class ExtractResponse(BaseModel):
    success: bool
    raw_text: str = ""
    extraction_method: str = ""  # "digital" or "ocr"
    error: str = ""


class AnalysisResponse(BaseModel):
    success: bool
    document_type: str = ""
    dates: list[str] = []
    signatories: list[str] = []
    amounts: list[str] = []
    tables: list[TableItem] = []
    summary: str = ""
    is_valid_evidence: bool = False
    raw_text: str = ""
    error: str = ""
