# Arquitectura

El servicio sigue principios de arquitectura hexagonal:

- **Dominio (`app/domain`)**: entidades puras (`Invoice`, `Shipment`, `Party`) y enums de negocio.
- **Aplicacion (`app/application`)**: DTOs de entrada/salida, puertos (interfaces) y casos de uso (`CreateCartaPorteService`).
- **Infraestructura (`app/infrastructure`)**: implementaciones concretas (ORM con SQLAlchemy, cliente HTTP a Facturify, mapeadores y unidad de trabajo).
- **Interfaces (`app/interfaces`)**: routers FastAPI, dependencias y validaciones HTTP.

## Integracion con Facturify

- Documentacion oficial consumida: [docs.facturify.com](https://docs.facturify.com/) (`compiled.yaml`).
- Endpoints utilizados
  - `POST /api/v1/factura` para crear CFDI
  - `GET /api/v1/factura/{cfdi_uuid}` para consultar estatus
- El `FacturifyClient` aplica reintentos exponenciales y superficie homologada de errores (`ExternalServiceError`).

## Modelo de datos

| Tabla | Objetivo |
| --- | --- |
| `companies` | Emisores registrados con su `facturify_uuid` |
| `clients` | Receptores normalizados |
| `invoices` | CFDI generados, estatus local y metadata de Facturify |
| `invoice_items` | Conceptos asociados al CFDI |
| `shipments` | Datos generales del complemento Carta Porte |
| `shipment_locations` | Origen/destinos del traslado |
| `shipment_goods` | Mercancias transportadas |
| `transport_figures` | Operadores/propietarios exigidos por la norma |

## Flujo de timbrado

1. El router recibe `CartaPorteRequest` con datos del CFDI y se valida con Pydantic.
2. `CreateCartaPorteService` abre una unidad de trabajo, recupera al emisor y actualiza/alinea al receptor.
3. Se persiste el borrador de la factura y se construye el payload usando `FacturifyPayloadBuilder` (ajustado a Carta Porte 3.0).
4. Se invoca `FacturifyClient`. Ante exito, se almacena el `cfdi_uuid`; ante error, se marca como `failed`.
5. FastAPI responde con `CartaPorteResponse` y se publica automaticamente en `/docs` y `docs/openapi.json` (via `make openapi`).
