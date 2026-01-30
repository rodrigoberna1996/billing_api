# Billing API (Carta Porte)

Backend FastAPI con arquitectura hexagonal para integrar el API publica de [Facturify](https://docs.facturify.com/) y timbrar CFDI 4.0 con complemento Carta Porte 3.0.

## Requisitos

- Python 3.11+
- PostgreSQL 16 (puedes usar `docker compose up -d`)
- Entorno virtual (`python -m venv .venv && source .venv/bin/activate`)

## Puesta en marcha

```bash
cp .env.example .env
make install
make run
```

La API queda disponible en `http://localhost:8000` con documentacion interactiva en `/docs` y `/redoc`.

## Variables clave

- `DATABASE_URL`: cadena asyncpg (por defecto apunta al contenedor local)
- `FACTURIFY_API_KEY`: token JWT emitido por Facturify
- `FACTURIFY_ACCOUNT_UUID`: UUID del emisor registrado en Facturify (se usa para el bloque `emisor`)

## Migraciones

```bash
# aplicar estado mas reciente
make upgrade

# crear nueva revision
make migrate
```

## Pruebas

```bash
make test
```

## Arquitectura

- **Dominio (`app/domain`)**: entidades puras (`Invoice`, `Shipment`, `Party`) y value objects (`Money`).
- **Aplicacion (`app/application`)**: DTOs de entrada/salida, puertos y casos de uso (`CreateCartaPorteService`).
- **Infraestructura (`app/infrastructure`)**: ORM SQLAlchemy 2.0, repositorios, unidad de trabajo y `FacturifyClient` (HTTPX + tenacity).
- **Interfaces (`app/interfaces`)**: routers FastAPI (`/health`, `/v1/cfdi/carta-porte`) y dependencias (`app/interfaces/api/deps.py`).

## Endpoints disponibles

### POST /v1/cfdi/carta-porte
Endpoint original que acepta el formato interno de la API.

### POST /v1/cfdi/carta-porte/facturify
**Nuevo endpoint** que acepta el formato compatible con Facturify. Este endpoint:
- Acepta `emisor` y `receptor` con UUID (y opcionalmente datos completos)
- Recibe la estructura de `factura` con el complemento `CartaPorte` anidado
- Transforma automáticamente al formato interno antes de procesar
- Ver ejemplo en `examples/carta_porte_facturify_format.json`

### GET /v1/cfdi/{invoice_id}
Consulta el estado de una factura previamente generada.

## Flujo principal

1. El endpoint recibe el request (formato interno o Facturify) validado con Pydantic.
2. Si es formato Facturify, se transforma automáticamente al formato interno.
3. El caso de uso consulta al emisor, normaliza al receptor, persiste el borrador y construye el payload conforme a la especificacion oficial (`docs.facturify.com/es/compiled.yaml`).
4. `FacturifyClient` invoca `POST /api/v1/factura` con reintentos exponenciales. La respuesta actualiza el estatus local (`issued`/`failed`).
5. `GET /v1/cfdi/{invoice_id}` consulta la factura almacenada (sin pegar nuevamente a Facturify).

## Referencias utiles

- Esquema CFDI + Carta Porte 3.0 de Facturify: `https://docs.facturify.com/es/compiled.yaml`
- Ejemplo oficial de carta porte ingreso: `https://docs.facturify.com/src/ejemplos/carta-porte/factura_ingreso_federal_carta_porte.json`
- Diagrama y notas adicionales en `docs/architecture.md`
