"""Importación de mercancías desde XLSX para complemento Carta Porte."""
from __future__ import annotations

import io
import logging
import unicodedata

from fastapi import APIRouter, File, HTTPException, Request, UploadFile, status
from pydantic import BaseModel

from app.interfaces.api.limiter import limiter

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/v1/mercancias", tags=["mercancias"])

MAX_UPLOAD_BYTES = 10 * 1024 * 1024  # 10 MB

# ---------------------------------------------------------------------------
# Helpers de normalización
# ---------------------------------------------------------------------------

def _norm_header(s: str) -> str:
    """Minúsculas, sin acentos, sin separadores."""
    nfd = unicodedata.normalize("NFD", s.strip().lower())
    sin_tildes = "".join(c for c in nfd if unicodedata.category(c) != "Mn")
    return sin_tildes.replace(" ", "").replace("_", "").replace("-", "").replace(".", "")


def _pick(row: dict[str, str], *keys: str) -> str:
    """Devuelve el primer valor no vacío que coincida con alguna de las claves normalizadas."""
    for k in keys:
        v = row.get(k, "").strip()
        if v:
            return v
    return ""


def _parse_material_peligroso(val: str) -> str:
    return "Sí" if val.lower() in {"sí", "si", "s", "yes", "1", "true", "x", "y"} else "No"


# ---------------------------------------------------------------------------
# Schemas de respuesta
# ---------------------------------------------------------------------------

class MercanciaItemResponse(BaseModel):
    BienesTransp: str
    Cantidad: float
    ClaveUnidad: str
    Descripcion: str
    PesoEnKg: float
    MaterialPeligroso: str
    CveMaterialPeligroso: str
    Embalaje: str
    DescripEmbalaje: str


class MercanciasImportResponse(BaseModel):
    mercancias: list[MercanciaItemResponse]
    total: int
    peso_neto_total: float


# ---------------------------------------------------------------------------
# Parseo del XLSX
# ---------------------------------------------------------------------------

def _parse_xlsx_to_rows(content: bytes) -> list[dict[str, str]]:
    """Lee la primera hoja del XLSX y devuelve filas como dicts con encabezados normalizados."""
    try:
        import openpyxl  # noqa: PLC0415
    except ImportError as exc:
        raise RuntimeError("openpyxl no está instalado. Agrega openpyxl a requirements.txt.") from exc

    wb = openpyxl.load_workbook(io.BytesIO(content), data_only=True, read_only=True)
    ws = wb.active
    if ws is None:
        return []

    raw_rows = list(ws.iter_rows(values_only=True))
    wb.close()

    if not raw_rows:
        return []

    # Primera fila = encabezados
    headers = [_norm_header(str(h or "")) for h in raw_rows[0]]

    result: list[dict[str, str]] = []
    for raw in raw_rows[1:]:
        cells = [str(v if v is not None else "").strip() for v in raw]
        if not any(cells):
            continue
        result.append({headers[i]: cells[i] for i in range(min(len(headers), len(cells)))})

    return result


def _rows_to_mercancias(rows: list[dict[str, str]]) -> list[MercanciaItemResponse]:
    """
    Mapeo de columnas del Excel al modelo de Mercancía:
      CLAVE SAT / BienesTransp / bienes / claveproducto  → BienesTransp
      DESCRIPCION CON PEDIMENTOS (preferido) / DESCRIPCION → Descripcion
      PIEZAS POR REGRESAR OK / Cantidad / cant            → Cantidad
      PESO EN KG / PesoEnKg / peso                        → PesoEnKg
      CLAVE MERCANCIA / ClaveUnidad / unidad              → ClaveUnidad (default H87)
    """
    items: list[MercanciaItemResponse] = []

    for row in rows:
        bienes_transp = _pick(
            row, "clavesat", "bienestransp", "bienes", "claveproducto", "claveprodserv", "claveprodservicio"
        )
        # Preferir descripcion con pedimentos si existe
        descripcion = _pick(row, "descripcionconpedimentos") or _pick(row, "descripcion", "desc", "concepto")

        cantidad_raw = _pick(row, "piezasporregresarok", "cantidad", "cant")
        try:
            cantidad = float(cantidad_raw) if cantidad_raw else 1.0
        except ValueError:
            cantidad = 1.0

        peso_raw = _pick(row, "pesoenkg", "pesokg", "peso", "pesoneto")
        try:
            peso = float(peso_raw.replace(",", ".")) if peso_raw else 0.0
        except ValueError:
            peso = 0.0

        clave_unidad = _pick(row, "clavemercancia", "claveunidad", "unidad", "cunidad") or "H87"

        mat_peligroso = _parse_material_peligroso(
            _pick(row, "materialpeligroso", "materialpeligro", "peligroso", "mp")
        )

        cve_material = ""
        embalaje = ""
        descrip_embalaje = ""
        if mat_peligroso == "Sí":
            cve_material = _pick(row, "cvematerialpeligroso", "cvematerial", "clavematerial")
            embalaje = _pick(row, "embalaje", "tipoembalaje", "cveembalaje")
            descrip_embalaje = _pick(row, "descripembalaje", "descripcionembalaje", "descembalaje")

        # Omitir filas sin los campos obligatorios mínimos
        if not bienes_transp or not descripcion:
            logger.debug("Fila omitida por falta de BienesTransp o Descripcion: %s", row)
            continue

        items.append(
            MercanciaItemResponse(
                BienesTransp=bienes_transp,
                Cantidad=cantidad,
                ClaveUnidad=clave_unidad,
                Descripcion=descripcion,
                PesoEnKg=peso,
                MaterialPeligroso=mat_peligroso,
                CveMaterialPeligroso=cve_material,
                Embalaje=embalaje,
                DescripEmbalaje=descrip_embalaje,
            )
        )

    return items


# ---------------------------------------------------------------------------
# Endpoint
# ---------------------------------------------------------------------------

@router.post(
    "/import-xlsx",
    response_model=MercanciasImportResponse,
    status_code=status.HTTP_200_OK,
    summary="Importar mercancías desde XLSX para Carta Porte",
    responses={
        200: {"description": "Lista de mercancías importadas del Excel"},
        400: {"description": "Archivo inválido o corrupto"},
        413: {"description": "El archivo excede 10 MB"},
        415: {"description": "Tipo de archivo no soportado (solo .xlsx)"},
        422: {"description": "No se encontraron filas con los campos mínimos requeridos"},
    },
)
@limiter.limit("20/minute")
async def import_mercancias_from_xlsx(
    request: Request,
    file: UploadFile = File(..., description="Archivo XLSX con columnas: CLAVE SAT, DESCRIPCION, PIEZAS POR REGRESAR OK, PESO EN KG, CLAVE MERCANCIA"),
) -> MercanciasImportResponse:
    content_length = request.headers.get("content-length")
    if content_length and int(content_length) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail="El archivo excede el límite de 10 MB.")

    allowed_ct = {
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        "application/octet-stream",
    }
    fname = (file.filename or "").lower()
    if file.content_type not in allowed_ct and not fname.endswith(".xlsx"):
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail="Tipo de archivo no soportado. Use un archivo .xlsx",
        )

    try:
        content = await file.read()
    except Exception as exc:
        raise HTTPException(status_code=400, detail="No se pudo leer el archivo.") from exc

    try:
        rows = _parse_xlsx_to_rows(content)
    except Exception as exc:
        logger.error("Error al parsear XLSX de mercancías: %s", exc)
        raise HTTPException(status_code=400, detail="Archivo XLSX inválido o corrupto.") from exc

    mercancias = _rows_to_mercancias(rows)

    if not mercancias:
        raise HTTPException(
            status_code=422,
            detail=(
                "No se encontraron filas con los campos mínimos requeridos "
                "(CLAVE SAT y DESCRIPCION / DESCRIPCION CON PEDIMENTOS). "
                "Verifica que el archivo tenga encabezados en la primera fila."
            ),
        )

    peso_total = round(sum(m.PesoEnKg for m in mercancias), 6)
    logger.info("import-xlsx mercancias: %d filas importadas, peso total %.3f kg", len(mercancias), peso_total)

    return MercanciasImportResponse(
        mercancias=mercancias,
        total=len(mercancias),
        peso_neto_total=peso_total,
    )
