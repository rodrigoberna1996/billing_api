"""DTOs para el formato de entrada compatible con Facturify."""
from __future__ import annotations

from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, Field


class EmisorDTO(BaseModel):
    """Emisor puede venir solo con UUID o con datos completos."""
    uuid: UUID
    razon_social: str | None = None
    rfc: str | None = None
    cp: str | None = None


class ReceptorDTO(BaseModel):
    """Receptor puede venir solo con UUID o con datos completos."""
    uuid: UUID
    rfc: str | None = None
    razon_social: str | None = None
    cp: str | None = None
    regimen: str | None = None
    metodo_de_pago: str | None = None
    forma_de_pago: str | None = None


class DomicilioDTO(BaseModel):
    """Domicilio en formato Facturify."""
    Calle: str
    CodigoPostal: str
    Estado: str
    Pais: str = "MEX"
    Municipio: str | None = None
    Localidad: str | None = None
    NumeroExterior: str | None = None
    Colonia: str | None = None


class UbicacionDTO(BaseModel):
    """Ubicación de origen o destino."""
    TipoUbicacion: Literal["Origen", "Destino"]
    IDUbicacion: str
    RFCRemitenteDestinatario: str
    FechaHoraSalidaLlegada: str
    Domicilio: DomicilioDTO
    DistanciaRecorrida: float | None = None


class UbicacionesDTO(BaseModel):
    """Contenedor de ubicaciones."""
    Ubicacion: list[UbicacionDTO]


class MercanciaDTO(BaseModel):
    """Mercancía transportada."""
    BienesTransp: str
    Cantidad: float
    ClaveUnidad: str
    Descripcion: str
    PesoEnKg: float
    MaterialPeligroso: str | None = None
    CveMaterialPeligroso: str | None = None


class IdentificacionVehicularDTO(BaseModel):
    """Identificación del vehículo."""
    ConfigVehicular: str
    PlacaVM: str
    AnioModeloVM: str
    PesoBrutoVehicular: str


class SegurosDTO(BaseModel):
    """Seguros del vehículo."""
    AseguraRespCivil: str
    PolizaRespCivil: str
    PrimaSeguro: str | None = None


class RemolqueDTO(BaseModel):
    """Remolque del vehículo."""
    SubTipoRem: str
    Placa: str


class RemolquesDTO(BaseModel):
    """Contenedor de remolques."""
    Remolque: list[RemolqueDTO]


class AutotransporteDTO(BaseModel):
    """Autotransporte."""
    PermSCT: str
    NumPermisoSCT: str
    IdentificacionVehicular: IdentificacionVehicularDTO
    Seguros: SegurosDTO
    Remolques: RemolquesDTO | None = None


class MercanciasDTO(BaseModel):
    """Mercancías transportadas."""
    NumTotalMercancias: int
    PesoNetoTotal: float
    PesoBrutoTotal: float
    UnidadPeso: str = "KGM"
    Mercancia: list[MercanciaDTO]
    Autotransporte: AutotransporteDTO


class TipoFiguraDTO(BaseModel):
    """Figura de transporte."""
    TipoFigura: str
    RFCFigura: str
    NumLicencia: str | None = None
    NombreFigura: str


class FiguraTransporteDTO(BaseModel):
    """Figuras de transporte."""
    TiposFigura: list[TipoFiguraDTO]


class CartaPorteComplementoDTO(BaseModel):
    """Complemento Carta Porte en formato Facturify."""
    Version: str = "3.1"
    IdCCP: str | None = None
    TranspInternac: Literal["Si", "No"] = "No"
    TotalDistRec: float
    Ubicaciones: UbicacionesDTO
    Mercancias: MercanciasDTO
    FiguraTransporte: FiguraTransporteDTO


class ComplementoDTO(BaseModel):
    """Contenedor de complementos."""
    CartaPorte: CartaPorteComplementoDTO


class TrasladoDTO(BaseModel):
    """Traslado de impuesto."""
    base: float
    impuesto: str
    tipoFactor: str
    tasaOCuota: float
    importe: float


class TrasladosDTO(BaseModel):
    """Traslados de impuestos."""
    traslado: list[TrasladoDTO]


class ImpuestosConceptoDTO(BaseModel):
    """Impuestos de un concepto."""
    traslados: TrasladosDTO | None = None


class ConceptoDTO(BaseModel):
    """Concepto de la factura."""
    cantidad: float
    clave_producto_servicio: str
    clave_unidad_de_medida: str
    descripcion: str
    valor_unitario: float
    total: float
    objeto_imp: str = "02"
    impuestos: ImpuestosConceptoDTO | None = None


class FacturaDTO(BaseModel):
    """Factura en formato Facturify."""
    version: str = "4.0"
    fecha: str
    tipo: Literal["ingreso", "traslado"] = "ingreso"
    forma_de_pago: str = "03"
    metodo_de_pago: str = Field(default="PUE", alias="metodo_pago")
    moneda: str = "MXN"
    tipo_de_cambio: str = "1"
    exportacion: str = "01"
    subtotal: float
    impuesto_federal: float | None = None
    total: float
    serie: str | None = None
    folio: str | None = None
    uso_cfdi: str | None = Field(default=None, alias="uso")
    lugar_expedicion: str | None = None
    conceptos: list[ConceptoDTO]
    Complemento: ComplementoDTO

    model_config = {
        "populate_by_name": True,
    }


class FacturifyCartaPorteRequest(BaseModel):
    """Request en formato Facturify para Carta Porte."""
    emisor: EmisorDTO
    receptor: ReceptorDTO
    factura: FacturaDTO

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "emisor": {
                        "uuid": "6fe768d7-922f-4b8a-b1b7-ac2c30300d89"
                    },
                    "receptor": {
                        "uuid": "96076f99-7105-4a62-a732-1ea33d88f4a0"
                    },
                    "factura": {
                        "version": "4.0",
                        "fecha": "2026-01-21 15:58:20",
                        "tipo": "ingreso",
                        "forma_de_pago": "03",
                        "moneda": "MXN",
                        "tipo_de_cambio": "1",
                        "exportacion": "01",
                        "subtotal": 10.0,
                        "impuesto_federal": 1.6,
                        "total": 11.6,
                        "serie": "CPT",
                        "conceptos": [
                            {
                                "cantidad": 1,
                                "clave_producto_servicio": "78101800",
                                "clave_unidad_de_medida": "E48",
                                "descripcion": "SERVICIO DE TRANSPORTE",
                                "valor_unitario": 10.0,
                                "total": 10.0,
                                "objeto_imp": "02",
                                "impuestos": {
                                    "traslados": {
                                        "traslado": [
                                            {
                                                "base": 10.0,
                                                "impuesto": "002",
                                                "tipoFactor": "Tasa",
                                                "tasaOCuota": 0.16,
                                                "importe": 1.6
                                            }
                                        ]
                                    }
                                }
                            }
                        ],
                        "Complemento": {
                            "CartaPorte": {
                                "Version": "3.1",
                                "TranspInternac": "No",
                                "TotalDistRec": 2673,
                                "Ubicaciones": {
                                    "Ubicacion": [
                                        {
                                            "TipoUbicacion": "Origen",
                                            "IDUbicacion": "OR000000",
                                            "RFCRemitenteDestinatario": "THE791105HP2",
                                            "FechaHoraSalidaLlegada": "2026-01-21T08:30:00",
                                            "Domicilio": {
                                                "Calle": "PARQUE INDUSTRIAL",
                                                "CodigoPostal": "54257",
                                                "Municipio": "045",
                                                "Estado": "MEX",
                                                "Pais": "MEX"
                                            }
                                        }
                                    ]
                                },
                                "Mercancias": {
                                    "NumTotalMercancias": 1,
                                    "PesoNetoTotal": 18000,
                                    "PesoBrutoTotal": 18000,
                                    "UnidadPeso": "KGM",
                                    "Mercancia": [
                                        {
                                            "BienesTransp": "11131504",
                                            "Cantidad": 18,
                                            "ClaveUnidad": "H87",
                                            "Descripcion": "Cueros",
                                            "PesoEnKg": 18000
                                        }
                                    ],
                                    "Autotransporte": {
                                        "PermSCT": "TPAF02",
                                        "NumPermisoSCT": "2242ALO20082021001011",
                                        "IdentificacionVehicular": {
                                            "ConfigVehicular": "T3S2",
                                            "PlacaVM": "05BH7S",
                                            "AnioModeloVM": "2025",
                                            "PesoBrutoVehicular": "46.5"
                                        },
                                        "Seguros": {
                                            "AseguraRespCivil": "AXA Seguros S.A. de C.V.",
                                            "PolizaRespCivil": "DAA667380000-642",
                                            "PrimaSeguro": "1200"
                                        },
                                        "Remolques": {
                                            "Remolque": [
                                                {
                                                    "SubTipoRem": "CTR007",
                                                    "Placa": "03UX8W"
                                                }
                                            ]
                                        }
                                    }
                                },
                                "FiguraTransporte": {
                                    "TiposFigura": [
                                        {
                                            "TipoFigura": "01",
                                            "RFCFigura": "OECG020323J63",
                                            "NumLicencia": "LFD01011247",
                                            "NombreFigura": "GAMALIEL OLVERA CID"
                                        }
                                    ]
                                }
                            }
                        }
                    }
                }
            ]
        }
    }
