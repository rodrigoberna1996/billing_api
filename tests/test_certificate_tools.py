"""Pruebas para app.application.services.certificate_tools.

Genera un certificado autofirmado en memoria (no depende de CSD reales del SAT) para
validar la conversión DER->PEM, el descifrado de la llave privada, la extracción de
metadatos (RFC/serial/vigencia) y la verificación de que la llave y el certificado
sean pareja.
"""
from __future__ import annotations

import datetime

import pytest
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import NameOID

from app.application.services.certificate_tools import (
    certificate_der_to_pem,
    decrypt_private_key_to_pem,
    extract_certificate_info,
    keys_match,
)
from app.core.exceptions import ValidationError

_PASSWORD = "s3cr3t-csd-pass"
_RFC = "EKU9003173C9"
_SERIAL_TEXT = "30001000000500003416"


def _build_test_csd() -> tuple[bytes, bytes]:
    """Genera (cer_der, key_der_cifrado) simulando la forma de un CSD del SAT."""
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    name = x509.Name(
        [
            x509.NameAttribute(NameOID.COMMON_NAME, "EMPRESA DE PRUEBA SA DE CV"),
            x509.NameAttribute(x509.ObjectIdentifier("2.5.4.45"), f"{_RFC} / VADA800927DJ3"),
        ]
    )
    now = datetime.datetime.now(datetime.timezone.utc)
    cert = (
        x509.CertificateBuilder()
        .subject_name(name)
        .issuer_name(name)
        .public_key(key.public_key())
        .serial_number(int.from_bytes(_SERIAL_TEXT.encode("ascii"), "big"))
        .not_valid_before(now)
        .not_valid_after(now + datetime.timedelta(days=1460))
        .sign(key, hashes.SHA256())
    )
    cer_der = cert.public_bytes(serialization.Encoding.DER)
    key_der = key.private_bytes(
        encoding=serialization.Encoding.DER,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.BestAvailableEncryption(_PASSWORD.encode("utf-8")),
    )
    return cer_der, key_der


def test_certificate_der_to_pem_roundtrip() -> None:
    cer_der, _ = _build_test_csd()
    pem = certificate_der_to_pem(cer_der)
    assert pem.startswith("-----BEGIN CERTIFICATE-----")
    assert pem.strip().endswith("-----END CERTIFICATE-----")


def test_decrypt_private_key_to_pem_with_correct_password() -> None:
    _, key_der = _build_test_csd()
    pem = decrypt_private_key_to_pem(key_der, _PASSWORD)
    assert pem.startswith("-----BEGIN PRIVATE KEY-----")


def test_decrypt_private_key_to_pem_with_wrong_password_raises() -> None:
    _, key_der = _build_test_csd()
    with pytest.raises(ValidationError):
        decrypt_private_key_to_pem(key_der, "contrasena-incorrecta")


def test_extract_certificate_info_reads_rfc_serial_and_vigencia() -> None:
    cer_der, _ = _build_test_csd()
    info = extract_certificate_info(cer_der)
    assert info.rfc == _RFC
    assert info.serial_number == _SERIAL_TEXT
    assert info.razon_social == "EMPRESA DE PRUEBA SA DE CV"
    assert info.is_expired is False
    assert info.not_before < info.not_after


def test_keys_match_true_for_matching_pair() -> None:
    cer_der, key_der = _build_test_csd()
    cer_pem = certificate_der_to_pem(cer_der)
    key_pem = decrypt_private_key_to_pem(key_der, _PASSWORD)
    assert keys_match(key_pem, cer_pem) is True


def test_keys_match_false_for_unrelated_pair() -> None:
    cer_der, _ = _build_test_csd()
    _, other_key_der = _build_test_csd()
    cer_pem = certificate_der_to_pem(cer_der)
    other_key_pem = decrypt_private_key_to_pem(other_key_der, _PASSWORD)
    assert keys_match(other_key_pem, cer_pem) is False
