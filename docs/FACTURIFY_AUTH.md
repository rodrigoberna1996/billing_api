# Facturify Authentication Integration

## Descripción

Este módulo implementa la integración con la API de autenticación de Facturify, incluyendo:

- Obtención de tokens de autenticación
- Refresco automático de tokens
- Almacenamiento en caché usando Redis
- Gestión automática del ciclo de vida del token en segundo plano

## Configuración

### Variables de Entorno

Agrega las siguientes variables a tu archivo `.env`:

```bash
# Redis
REDIS_URL=redis://localhost:6379/0
REDIS_DECODE_RESPONSES=true

# Facturify
FACTURIFY_BASE_URL=https://api-sandbox.facturify.com
FACTURIFY_API_KEY=tu-api-key-aqui
FACTURIFY_API_SECRET=tu-api-secret-aqui
FACTURIFY_TIMEOUT=30
FACTURIFY_MAX_RETRIES=3
FACTURIFY_RETRY_BACKOFF=2.0
FACTURIFY_TOKEN_REFRESH_BUFFER=60
```

### Instalación de Dependencias

```bash
pip install -e .
```

### Iniciar Servicios

```bash
docker-compose up -d
```

Esto iniciará PostgreSQL y Redis.

## Endpoints Disponibles

### 1. Obtener Token

**POST** `/api/v1/facturify/auth/token`

Obtiene un nuevo token de autenticación desde Facturify y lo almacena en caché.

**Respuesta exitosa (200):**
```json
{
  "message": "string",
  "jwt": {
    "token": "string",
    "expires_in": 240
  }
}
```

**Ejemplo:**
```bash
curl -X POST http://localhost:8000/api/v1/facturify/auth/token
```

### 2. Refrescar Token

**POST** `/api/v1/facturify/auth/token/refresh`

Refresca el token actual. Si el token no puede ser refrescado, obtiene uno nuevo automáticamente.

**Respuesta exitosa (200):**
```json
{
  "message": "string",
  "jwt": {
    "token": "string",
    "expires_in": 43200
  }
}
```

**Ejemplo:**
```bash
curl -X POST http://localhost:8000/api/v1/facturify/auth/token/refresh
```

### 3. Obtener Token Válido

**GET** `/api/v1/facturify/auth/token`

Retorna un token válido, refrescándolo automáticamente si es necesario.

**Respuesta exitosa (200):**
```json
{
  "token": "string",
  "ttl": 180
}
```

**Ejemplo:**
```bash
curl -X GET http://localhost:8000/api/v1/facturify/auth/token
```

### 4. Estado del Token

**GET** `/api/v1/facturify/auth/token/status`

Retorna el estado actual del token en caché, incluyendo el tiempo de vida restante (TTL).

**Respuesta exitosa (200):**
```json
{
  "has_token": true,
  "ttl": 180,
  "expires_in": 240
}
```

**Ejemplo:**
```bash
curl -X GET http://localhost:8000/api/v1/facturify/auth/token/status
```

## Funcionamiento del Sistema

### Ciclo de Vida del Token

El sistema implementa una estrategia optimizada para mantener siempre un token de larga duración:

1. **Obtención Inicial** (`POST /api/v1/auth`): 
   - Cuando la aplicación inicia o no hay token, se obtiene un token inicial
   - Este token dura **240 segundos (4 minutos)**
   - Se almacena en Redis con su tiempo de expiración

2. **Refresco Inmediato** (`GET /api/v1/token/refresh`):
   - Inmediatamente después de obtener el token inicial, el sistema lo refresca
   - El token refrescado dura **43200 segundos (12 horas)**
   - Este es el token que se mantiene activo durante toda la operación

3. **Mantenimiento del Token de Larga Duración**:
   - Un proceso en segundo plano monitorea el token refrescado
   - Lo refresca automáticamente antes de que expire (60s antes por defecto)
   - Cada refresh extiende la duración a 12 horas más

4. **Recuperación ante Fallos**:
   - Si el refresh falla (token expirado o inválido), se obtiene un nuevo token inicial
   - Inmediatamente se refresca para obtener el token de 12 horas
   - El ciclo continúa normalmente

### Tiempos de Expiración

- **Token inicial** (`/auth`): 240 segundos (4 minutos) - Solo usado al inicio
- **Token refrescado** (`/token/refresh`): 43200 segundos (12 horas) - Mantenido activamente

### Proceso de Refresco Automático

El sistema ejecuta un loop en segundo plano con la siguiente estrategia optimizada:

1. **Sin token en caché**:
   - Obtiene token inicial via `/auth` (240s)
   - Espera 5 segundos
   - Refresca inmediatamente via `/token/refresh` para obtener token de 12 horas
   
2. **Token de corta duración detectado** (< 300s):
   - Refresca inmediatamente para obtener token de larga duración
   
3. **Token de larga duración activo**:
   - Monitorea el TTL constantemente
   - Refresca 60 segundos antes de expirar (configurable)
   - Mantiene el token siempre con 12 horas de validez
   
4. **Token expirado**:
   - Obtiene nuevo token inicial
   - Refresca inmediatamente para obtener token de 12 horas
   - Continúa el ciclo normal

### Manejo de Errores

- **401 Unauthorized**: Credenciales inválidas o token expirado
- **422 Validation Error**: Datos de entrada inválidos
- **500 Internal Server Error**: Error del servidor

Cuando un refresco falla con 401, el sistema automáticamente obtiene un nuevo token.

## Uso en Código

### Obtener un Token Válido

```python
from app.infrastructure.http.facturify_auth_client import get_facturify_auth_client

async def mi_funcion():
    client = await get_facturify_auth_client()
    token = await client.get_valid_token()
    # Usar el token para llamadas a Facturify
```

### Acceso Directo a Redis

```python
from app.core.redis import get_value, get_ttl

async def verificar_token():
    token = await get_value("facturify:auth:token")
    ttl = await get_ttl("facturify:auth:token")
    print(f"Token: {token}, TTL: {ttl}s")
```

## Monitoreo

### Logs

El sistema registra eventos importantes:

- Obtención de tokens
- Refresco de tokens
- Errores de autenticación
- Estado del proceso en segundo plano

### Verificación de Salud

Usa el endpoint de estado para monitorear:

```bash
curl http://localhost:8000/api/v1/facturify/auth/token/status
```

## Arquitectura

```
┌─────────────────┐
│   FastAPI App   │
└────────┬────────┘
         │
    ┌────▼────────────────────┐
    │ FacturifyAuthClient     │
    │ - obtain_token()        │
    │ - refresh_token()       │
    │ - get_valid_token()     │
    │ - background_refresh()  │
    └────┬────────────────────┘
         │
    ┌────▼────────┐      ┌──────────────┐
    │   Redis     │      │  Facturify   │
    │   Cache     │      │     API      │
    └─────────────┘      └──────────────┘
```

## Notas Importantes

1. **Redis es requerido**: El sistema no funcionará sin Redis disponible.

2. **Credenciales**: Asegúrate de configurar correctamente `FACTURIFY_API_KEY` y `FACTURIFY_API_SECRET`.

3. **Ambiente Sandbox**: Por defecto usa el ambiente sandbox de Facturify. Para producción, cambia `FACTURIFY_BASE_URL` a `https://api.facturify.com`.

4. **Reintentos**: El sistema reintenta automáticamente hasta 3 veces en caso de errores de red.

5. **Thread-Safe**: El cliente usa un singleton para garantizar una única instancia y evitar múltiples procesos de refresco.
