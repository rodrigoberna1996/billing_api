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
