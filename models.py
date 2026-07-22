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
    fecha_adicion_prorroga: str = ""
    valor_adicion_prorroga: str = ""
    error: str = ""


class ActaResumenResponse(BaseModel):
    success: bool
    resumen: str = ""
    error: str = ""


class PlanillaAnalysisResponse(BaseModel):
    success: bool
    planilla_numero: str = ""
    fondo_pension: str = ""
    arl: str = ""
    eps: str = ""
    ibc: str = ""
    valor_pension: str = ""
    valor_salud: str = ""
    valor_arl: str = ""
    valor_total: str = ""
    fecha_pago: str = ""
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
