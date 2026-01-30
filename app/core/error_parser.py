"""Parser para errores de Facturify y el SAT."""
from __future__ import annotations

import json
import re
from typing import Any


class FacturifyErrorParser:
    """Extrae y formatea mensajes de error de respuestas de Facturify."""

    # Mapeo de códigos SAT a mensajes amigables
    SAT_ERROR_MESSAGES = {
        "CFDI40147": "El código postal del receptor no está registrado en el SAT",
        "CFDI40148": "El RFC del receptor no está activo en el SAT",
        "CFDI40149": "El régimen fiscal del receptor no es válido",
        "CFDI33101": "El RFC del emisor no está activo en el SAT",
        "CFDI33102": "El certificado del emisor no es válido",
        "CFDI33103": "El sello digital no es válido",
    }

    @classmethod
    def parse_error(cls, error_response: str | dict) -> dict[str, Any]:
        """
        Parsea la respuesta de error de Facturify y extrae información útil.

        Args:
            error_response: Respuesta de error (string JSON o dict)

        Returns:
            Dict con información estructurada del error
        """
        # Si es string, intentar parsear como JSON
        if isinstance(error_response, str):
            try:
                error_data = json.loads(error_response)
            except json.JSONDecodeError:
                # Si no es JSON válido, usar el string directamente
                return cls._parse_plain_text_error(error_response)
        else:
            error_data = error_response

        # Verificar si es un error de validación con campo 'errors'
        if "errors" in error_data and isinstance(error_data["errors"], list):
            return cls._parse_validation_error(error_data)

        # Extraer información del error (formato SAT/PAC)
        success = error_data.get("success", False)
        message = error_data.get("message", "")
        code = error_data.get("code", "")
        pac = error_data.get("pac", "")

        # Extraer mensaje del SAT si existe
        sat_message = cls._extract_sat_message(message)

        # Obtener mensaje amigable si existe
        friendly_message = cls.SAT_ERROR_MESSAGES.get(code, "")

        return {
            "success": success,
            "error_code": code,
            "pac": pac,
            "original_message": message,
            "sat_message": sat_message,
            "friendly_message": friendly_message,
            "user_message": cls._build_user_message(sat_message, friendly_message, message),
            "validation_errors": None,
        }

    @classmethod
    def _extract_sat_message(cls, message: str) -> str | None:
        """Extrae el mensaje del SAT entre paréntesis."""
        # Buscar texto entre (SAT: ... )
        match = re.search(r"\(SAT:\s*(.+?)\)", message)
        if match:
            return match.group(1).strip()

        # Buscar cualquier texto entre paréntesis
        match = re.search(r"\((.+?)\)", message)
        if match:
            return match.group(1).strip()

        return None

    @classmethod
    def _build_user_message(
        cls,
        sat_message: str | None,
        friendly_message: str,
        original_message: str,
    ) -> str:
        """Construye un mensaje claro para el usuario."""
        if friendly_message:
            if sat_message:
                return f"{friendly_message}. Detalle: {sat_message}"
            return friendly_message

        if sat_message:
            return f"Error del SAT: {sat_message}"

        return original_message

    @classmethod
    def _parse_validation_error(cls, error_data: dict) -> dict[str, Any]:
        """
        Parsea errores de validación de Facturify con estructura 'errors'.
        
        Formato:
        {
          "code": 33,
          "message": "Los datos proporcionados no cumplen las reglas de validación",
          "errors": [
            {"field": "factura.serie", "message": "La serie que envió, no existe.", "code": 34}
          ]
        }
        """
        main_message = error_data.get("message", "Error de validación")
        code = error_data.get("code", "")
        errors = error_data.get("errors", [])
        
        # Construir mensaje detallado con todos los errores
        error_details = []
        for err in errors:
            field = err.get("field", "campo desconocido")
            message = err.get("message", "error desconocido")
            error_details.append(f"• {field}: {message}")
        
        if error_details:
            user_message = f"{main_message}:\n" + "\n".join(error_details)
        else:
            user_message = main_message
        
        return {
            "success": False,
            "error_code": str(code),
            "pac": "",
            "original_message": main_message,
            "sat_message": None,
            "friendly_message": "",
            "user_message": user_message,
            "validation_errors": errors,
        }

    @classmethod
    def _parse_plain_text_error(cls, error_text: str) -> dict[str, Any]:
        """Parsea un error en texto plano."""
        sat_message = cls._extract_sat_message(error_text)

        return {
            "success": False,
            "error_code": "",
            "pac": "",
            "original_message": error_text,
            "sat_message": sat_message,
            "friendly_message": "",
            "user_message": sat_message if sat_message else error_text,
            "validation_errors": None,
        }
