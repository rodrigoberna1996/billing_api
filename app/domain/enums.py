from __future__ import annotations

from enum import Enum


class InvoiceStatus(str, Enum):
    draft = "draft"
    pending = "pending"
    issued = "issued"
    failed = "failed"
    canceled = "canceled"


class InvoiceType(str, Enum):
    ingreso = "ingreso"
    traslado = "traslado"


class ComplementType(str, Enum):
    carta_porte = "carta_porte"


class TransportMode(str, Enum):
    autotransporte_federal = "01"
    autotransporte_local = "02"
    ferroviario = "03"
    maritimo = "04"
    aereo = "05"


class ShipmentLocationType(str, Enum):
    origin = "Origen"
    destination = "Destino"


class CancelMotivo(str, Enum):
    """Motivos de cancelación de CFDI según el catálogo del SAT (Anexo 20)."""

    con_relacion = "01"  # Comprobante emitido con errores con relación
    sin_relacion = "02"  # Comprobante emitido con errores sin relación
    no_efectuada = "03"  # No se llevó a cabo la operación
    global_nominativa = "04"  # Operación nominativa relacionada en factura global
