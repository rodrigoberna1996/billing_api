"""DTOs expuestos a FastAPI para timbrado carta porte."""
from __future__ import annotations

from datetime import datetime
from typing import Literal, Sequence
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field, constr

from app.domain.enums import ShipmentLocationType


class AddressDTO(BaseModel):
    street: str = Field(..., min_length=1, max_length=120)
    exterior_number: str = Field(..., min_length=1, max_length=12)
    neighborhood: str
    city: str
    state: str
    country: str = Field(default="MEX")
    zip_code: constr(pattern=r"^\d{5}$")  # type: ignore[type-arg]


class PartyDTO(BaseModel):
    legal_name: str
    rfc: constr(pattern=r"^[A-Z&\u00d1]{3,4}\d{6}[A-Z0-9]{3}$")  # type: ignore[type-arg]
    tax_regime: str
    email: EmailStr | None = None
    address: AddressDTO


class InvoiceItemDTO(BaseModel):
    product_key: str = Field(..., description="ClaveProdServ")
    description: str
    quantity: float = Field(..., gt=0)
    unit_key: str = Field(..., description="ClaveUnidad")
    unit_price: float = Field(..., gt=0)
    tax_percentage: float | None = Field(default=None, ge=0)


class ShipmentVehicleDTO(BaseModel):
    configuration: str
    plate: constr(pattern=r"^[A-Z0-9]{5,10}$")  # type: ignore[type-arg]
    federal_permit: str | None = None
    insurance_company: str | None = None
    insurance_policy: str | None = None
    model_year: str | None = Field(default=None, description="Año del modelo del vehículo")
    gross_weight: str | None = Field(default=None, description="Peso bruto vehicular")
    insurance_premium: str | None = Field(default=None, description="Prima del seguro")
    trailers: list[dict] | None = Field(default=None, description="Lista de remolques")

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "configuration": "T3S2",
                    "plate": "05BH7S",
                    "federal_permit": "TPAF02",
                    "insurance_company": "AXA Seguros S.A. de C.V.",
                    "insurance_policy": "DAA667380000-642",
                    "model_year": "2025",
                    "gross_weight": "46.5",
                    "insurance_premium": "1200",
                    "trailers": [
                        {
                            "subtype": "CTR007",
                            "plate": "03UX8W"
                        }
                    ]
                }
            ]
        }
    }


class ShipmentLocationDTO(BaseModel):
    type: ShipmentLocationType
    datetime: datetime
    street: str
    exterior_number: str
    neighborhood: str
    city: str
    state: str
    country: str = "MEX"
    zip_code: constr(pattern=r"^\d{5}$")  # type: ignore[type-arg]
    latitude: float | None = Field(default=None, ge=-90, le=90)
    longitude: float | None = Field(default=None, ge=-180, le=180)
    reference: str | None = Field(default=None, max_length=200)
    locality: str | None = Field(default=None, description="Localidad")

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "type": "origin",
                    "datetime": "2026-01-21T08:30:00",
                    "street": "PARQUE INDUSTRIAL",
                    "exterior_number": "S/N",
                    "neighborhood": "INDUSTRIAL",
                    "city": "045",
                    "state": "MEX",
                    "country": "MEX",
                    "zip_code": "54257"
                }
            ]
        }
    }


class ShipmentGoodsDTO(BaseModel):
    description: str
    product_key: str
    quantity: float = Field(..., gt=0)
    unit_key: str
    weight_kg: float = Field(..., gt=0)
    value: float = Field(..., ge=0)
    dangerous_material: bool = False
    dangerous_key: str | None = None


class TransportFigureDTO(BaseModel):
    type: str = Field(description="TipoFigura del complemento (01 operador, 02 propietario, etc.)")
    rfc: constr(pattern=r"^[A-Z&\u00d1]{3,4}\d{6}[A-Z0-9]{3}$")  # type: ignore[type-arg]
    name: str
    license: str | None = None
    role_description: str | None = Field(default=None, max_length=120)


class ShipmentDTO(BaseModel):
    transport_mode: Literal["01", "02", "03", "04", "05"]
    permit_type: str
    permit_number: str
    total_distance_km: float | None = None
    total_weight_kg: float = Field(..., gt=0)
    vehicle: ShipmentVehicleDTO
    locations: Sequence[ShipmentLocationDTO]
    goods: Sequence[ShipmentGoodsDTO]
    figures: Sequence[TransportFigureDTO] = ()


class CartaPorteRequest(BaseModel):
    facturify_issuer_uuid: str = Field(..., description="UUID del emisor en Facturify")
    cfdi_type: Literal["ingreso", "traslado"] = "ingreso"
    recipient: PartyDTO
    cfdi_use: str = Field(default="G01")
    payment_form: str = Field(default="03")
    payment_method: str = Field(default="PUE")
    expedition_place: constr(pattern=r"^\d{5}$")  # type: ignore[type-arg]
    currency: str = Field(default="MXN")
    subtotal: float = Field(..., gt=0)
    total: float = Field(..., gt=0)
    items: Sequence[InvoiceItemDTO]
    shipment: ShipmentDTO

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "issuer_id": "cedc4e5e-d690-4bab-b548-fd2662c53379",
                    "cfdi_type": "ingreso",
                    "recipient": {
                        "legal_name": "EMPRESA EJEMPLO SA DE CV",
                        "rfc": "THE791105HP2",
                        "tax_regime": "601",
                        "email": "contacto@ejemplo.com",
                        "address": {
                            "street": "Calle Principal",
                            "exterior_number": "123",
                            "neighborhood": "Centro",
                            "city": "Ciudad",
                            "state": "MEX",
                            "country": "MEX",
                            "zip_code": "54000"
                        }
                    },
                    "cfdi_use": "G01",
                    "payment_form": "03",
                    "payment_method": "PUE",
                    "expedition_place": "54257",
                    "currency": "MXN",
                    "subtotal": 10.0,
                    "total": 11.6,
                    "items": [
                        {
                            "product_key": "78101800",
                            "description": "SERVICIO DE TRANSPORTE",
                            "quantity": 1,
                            "unit_key": "E48",
                            "unit_price": 10.0,
                            "tax_percentage": 16
                        }
                    ],
                    "shipment": {
                        "transport_mode": "01",
                        "permit_type": "TPAF02",
                        "permit_number": "2242ALO20082021001011",
                        "total_distance_km": 2673,
                        "total_weight_kg": 18000,
                        "vehicle": {
                            "configuration": "T3S2",
                            "plate": "05BH7S",
                            "federal_permit": "TPAF02",
                            "insurance_company": "AXA Seguros S.A. de C.V.",
                            "insurance_policy": "DAA667380000-642",
                            "model_year": "2025",
                            "gross_weight": "46.5",
                            "insurance_premium": "1200",
                            "trailers": [
                                {
                                    "subtype": "CTR007",
                                    "plate": "03UX8W"
                                }
                            ]
                        },
                        "locations": [
                            {
                                "type": "origin",
                                "datetime": "2026-01-21T08:30:00",
                                "street": "PARQUE INDUSTRIAL",
                                "exterior_number": "S/N",
                                "neighborhood": "INDUSTRIAL",
                                "city": "045",
                                "state": "MEX",
                                "country": "MEX",
                                "zip_code": "54257"
                            },
                            {
                                "type": "destination",
                                "datetime": "2026-01-21T14:30:00",
                                "street": "Blvd. La Encantada Lote 5",
                                "exterior_number": "5",
                                "neighborhood": "ZONA COMERCIAL",
                                "city": "004",
                                "state": "BCN",
                                "country": "MEX",
                                "zip_code": "22244",
                                "locality": "04"
                            }
                        ],
                        "goods": [
                            {
                                "description": "Cueros",
                                "product_key": "11131504",
                                "quantity": 18,
                                "unit_key": "H87",
                                "weight_kg": 18000,
                                "value": 10.0,
                                "dangerous_material": False
                            }
                        ],
                        "figures": [
                            {
                                "type": "01",
                                "rfc": "OECG020323J63",
                                "name": "GAMALIEL OLVERA CID",
                                "license": "LFD01011247"
                            }
                        ]
                    }
                }
            ]
        }
    }


class CartaPorteResponse(BaseModel):
    invoice_id: UUID
    status: str
    facturify_uuid: str | None = None
    facturify_status: str | None = None
    facturify_response: dict | None = None

    model_config = {
        "from_attributes": True,
    }
