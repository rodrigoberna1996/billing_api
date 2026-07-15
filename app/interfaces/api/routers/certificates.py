"""Utilidad interna para convertir un CSD del SAT (.cer/.key) a los formatos que
requiere FacturaloPlus (PEM para timbrado, base64 para cancelación).

ADVERTENCIA DE SEGURIDAD: este endpoint recibe y devuelve material criptográfico
sensible (la llave privada del CSD). Debe usarse únicamente:
  - En un entorno confiable (idealmente corriendo billing_api en local, no en un
    servidor compartido/staging expuesto), y
  - Solo para el proceso puntual de carga de credenciales; los valores devueltos se
    pegan directamente en el .env y no deben quedar en logs, tickets ni chats.

El archivo/llave/contraseña nunca se persisten a disco ni a base de datos: todo el
procesamiento ocurre en memoria dentro del request.
"""
from __future__ import annotations

import base64
import logging

from fastapi import APIRouter, File, Form, HTTPException, Request, UploadFile, status
from pydantic import BaseModel, Field

from app.application.services.certificate_tools import (
    certificate_der_to_pem,
    decrypt_private_key_to_pem,
    extract_certificate_info,
)
from app.application.services.certificate_tools import keys_match as _keys_match
from app.core.exceptions import ValidationError
from app.interfaces.api.limiter import limiter

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/v1/certificates", tags=["certificates"])

# Los CSD del SAT son de unos pocos KB; un límite generoso evita abusos sin estorbar.
MAX_UPLOAD_BYTES = 16 * 1024


class CertificateConvertResponse(BaseModel):
    key_pem: str = Field(..., description="Pegar en FACTURALO_KEY_PEM (timbrado)")
    cer_pem: str = Field(..., description="Pegar en FACTURALO_CER_PEM (timbrado)")
    csd_key_b64: str = Field(..., description="Pegar en FACTURALO_CSD_KEY_B64 (cancelación)")
    csd_cer_b64: str = Field(..., description="Pegar en FACTURALO_CSD_CER_B64 (cancelación)")
    csd_serial: str = Field(..., description="Pegar en FACTURALO_CSD_SERIAL (NoCertificado)")
    rfc: str | None = Field(
        None, description="RFC embebido en el certificado (verificar contra FACTURALO_EMISOR_RFC)"
    )
    razon_social: str | None = None
    vigencia_desde: str
    vigencia_hasta: str
    vigente: bool
    llave_y_certificado_coinciden: bool = Field(
        ..., description="False indica que el .cer y el .key no son pareja: revisa los archivos."
    )


async def _read_upload(file: UploadFile, label: str) -> bytes:
    content = await file.read()
    if not content:
        raise HTTPException(status_code=400, detail=f"El archivo {label} está vacío.")
    if len(content) > MAX_UPLOAD_BYTES:
        raise HTTPException(
            status_code=413,
            detail=f"El archivo {label} excede el límite de {MAX_UPLOAD_BYTES // 1024} KB.",
        )
    return content


@router.post(
    "/convert",
    response_model=CertificateConvertResponse,
    status_code=status.HTTP_200_OK,
    summary="Convertir un CSD (.cer/.key) a los formatos que requiere FacturaloPlus",
    responses={
        400: {"description": "Certificado/llave inválidos, corruptos o contraseña incorrecta"},
        413: {"description": "Archivo demasiado grande"},
    },
)
@limiter.limit("5/minute")
async def convert_certificate(
    request: Request,
    cer_file: UploadFile = File(
        ..., description="Archivo .cer del CSD (formato DER, tal cual lo entrega el SAT)"
    ),
    key_file: UploadFile = File(
        ..., description="Archivo .key del CSD (formato DER PKCS8 cifrado)"
    ),
    password: str = Form(..., description="Contraseña de la llave privada del CSD"),
) -> CertificateConvertResponse:
    cer_der = await _read_upload(cer_file, ".cer")
    key_der = await _read_upload(key_file, ".key")

    try:
        cer_pem = certificate_der_to_pem(cer_der)
        key_pem = decrypt_private_key_to_pem(key_der, password)
        info = extract_certificate_info(cer_der)
        match = _keys_match(key_pem, cer_pem)
    except ValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    # No loguear key_pem/csd_key_b64/password: solo metadatos no sensibles.
    logger.info(
        "certificates/convert procesado: rfc=%s serial=%s vigente=%s coinciden=%s",
        info.rfc,
        info.serial_number,
        not info.is_expired,
        match,
    )

    if not match:
        logger.warning(
            "certificates/convert: la llave privada y el certificado NO son pareja "
            "(rfc=%s serial=%s)",
            info.rfc,
            info.serial_number,
        )

    return CertificateConvertResponse(
        key_pem=key_pem,
        cer_pem=cer_pem,
        csd_key_b64=base64.b64encode(key_der).decode("ascii"),
        csd_cer_b64=base64.b64encode(cer_der).decode("ascii"),
        csd_serial=info.serial_number,
        rfc=info.rfc,
        razon_social=info.razon_social,
        vigencia_desde=info.not_before.isoformat(),
        vigencia_hasta=info.not_after.isoformat(),
        vigente=not info.is_expired,
        llave_y_certificado_coinciden=match,
    )
