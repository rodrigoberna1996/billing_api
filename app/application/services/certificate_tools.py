"""Utilidades para convertir un CSD del SAT (.cer/.key en DER) a los formatos que
requiere FacturaloPlus (PEM para timbrado, base64 para cancelación).

Todo el procesamiento ocurre en memoria: no se escribe a disco ni se loguea material
criptográfico sensible (llave privada, contraseña).
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

from cryptography import x509
from cryptography.hazmat.primitives import serialization

from app.core.exceptions import ValidationError

# OID 2.5.4.45 (x500UniqueIdentifier): en los CSD del SAT contiene "RFC / CURP".
_RFC_CURP_OID = x509.ObjectIdentifier("2.5.4.45")


@dataclass(frozen=True)
class CertificateInfo:
    """Metadatos extraídos de un certificado .cer del SAT (sin datos sensibles)."""

    serial_number: str
    rfc: str | None
    razon_social: str | None
    not_before: datetime
    not_after: datetime
    is_expired: bool


def certificate_der_to_pem(cer_der: bytes) -> str:
    """Convierte un .cer del SAT (DER) a PEM (para FACTURALO_CER_PEM)."""
    try:
        cert = x509.load_der_x509_certificate(cer_der)
    except ValueError as exc:
        raise ValidationError("El archivo .cer no es un certificado X.509 (DER) válido.") from exc
    return cert.public_bytes(serialization.Encoding.PEM).decode("ascii")


def decrypt_private_key_to_pem(key_der: bytes, password: str) -> str:
    """Descifra la llave privada del CSD (.key, PKCS8 DER cifrado) y la devuelve como
    PEM PKCS8 sin cifrar (para FACTURALO_KEY_PEM)."""
    try:
        private_key = serialization.load_der_private_key(key_der, password=password.encode("utf-8"))
    except (ValueError, TypeError) as exc:
        raise ValidationError(
            "No se pudo descifrar la llave privada. Verifica que el archivo .key y la "
            "contraseña del CSD sean correctos."
        ) from exc
    pem = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    )
    return pem.decode("ascii")


def extract_certificate_info(cer_der: bytes) -> CertificateInfo:
    """Extrae serie (NoCertificado), RFC, razón social y vigencia del .cer."""
    try:
        cert = x509.load_der_x509_certificate(cer_der)
    except ValueError as exc:
        raise ValidationError("El archivo .cer no es un certificado X.509 (DER) válido.") from exc

    rfc_curp = next(
        (attr.value for attr in cert.subject if attr.oid == _RFC_CURP_OID),
        None,
    )
    rfc = rfc_curp.split("/")[0].strip() if isinstance(rfc_curp, str) and rfc_curp else None

    cn_attrs = cert.subject.get_attributes_for_oid(x509.NameOID.COMMON_NAME)
    razon_social = str(cn_attrs[0].value) if cn_attrs else None

    not_before = cert.not_valid_before_utc
    not_after = cert.not_valid_after_utc

    # El serial de un CSD del SAT codifica el NoCertificado como texto ASCII en hexadecimal.
    serial_hex = format(cert.serial_number, "x")
    if len(serial_hex) % 2:
        serial_hex = "0" + serial_hex
    try:
        no_certificado = bytes.fromhex(serial_hex).decode("ascii")
    except (ValueError, UnicodeDecodeError):
        no_certificado = str(cert.serial_number)

    return CertificateInfo(
        serial_number=no_certificado,
        rfc=rfc,
        razon_social=razon_social,
        not_before=not_before,
        not_after=not_after,
        is_expired=datetime.now(timezone.utc) > not_after,
    )


def keys_match(key_pem: str, cer_pem: str) -> bool:
    """Verifica que la llave privada corresponda a la llave pública del certificado."""
    try:
        private_key = serialization.load_pem_private_key(key_pem.encode("ascii"), password=None)
        cert = x509.load_pem_x509_certificate(cer_pem.encode("ascii"))
    except ValueError as exc:
        raise ValidationError("No se pudo comparar la llave privada con el certificado.") from exc

    return private_key.public_key().public_numbers() == cert.public_key().public_numbers()
