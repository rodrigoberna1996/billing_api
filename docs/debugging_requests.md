# Guía de Debugging de Requests

## Sistema de Logging Implementado

Se han agregado tres capas de logging para identificar problemas con los requests:

### 1. Middleware de Request Logger

**Ubicación**: Se ejecuta ANTES de que FastAPI procese el request

**Qué loggea**:
- 🔍 Método HTTP y path
- 📋 Content-Type del header
- 📏 Tamaño del body en bytes
- 📦 Raw body (primeros 2000 caracteres)
- ✅ Si el JSON se puede parsear correctamente
- 🔑 Tipo del objeto parseado (dict, str, list, etc.)
- 🔑 Keys del objeto si es un diccionario

**Buscar en logs**:
```
🔍 RAW REQUEST - POST /v1/cfdi/carta-porte/facturify
```

### 2. Exception Handler de Validación

**Ubicación**: Se ejecuta cuando Pydantic falla al validar el payload

**Qué loggea**:
- ❌ Detalles completos del error de validación
- 📋 Content-Type recibido
- 📦 Raw body completo
- 🚨 Lista detallada de todos los errores de validación con:
  - Tipo de error
  - Ubicación del error (path en el JSON)
  - Mensaje de error
  - Input que causó el error

**Buscar en logs**:
```
❌ ERROR DE VALIDACIÓN DE PYDANTIC
```

### 3. Logging en el Endpoint

**Ubicación**: Se ejecuta DESPUÉS de que Pydantic valida exitosamente

**Qué loggea**:
- ✅ Confirmación de validación exitosa
- 🔍 Tipo del objeto payload
- 📄 JSON completo ya validado y parseado

**Buscar en logs**:
```
✅ PAYLOAD VALIDADO CORRECTAMENTE EN /v1/cfdi/carta-porte/facturify
```

## Cómo Interpretar los Logs

### Caso 1: Error "Input should be a valid dictionary"

Si ves este error, revisa en orden:

1. **Middleware logs** - Verifica:
   ```
   📋 Content-Type: application/json  ← DEBE ser application/json
   ✅ JSON PARSEADO CORRECTAMENTE     ← DEBE aparecer
   🔑 Tipo del objeto parseado: <class 'dict'>  ← DEBE ser dict
   ```

2. **Exception Handler logs** - Revisa:
   ```
   📦 RAW BODY recibido:
   {"emisor": {...}}  ← Debe ser un objeto JSON, NO un string
   ```

### Caso 2: Content-Type incorrecto

Si el Content-Type NO es `application/json`:
```
📋 Content-Type: text/plain
```

**Solución**: Asegúrate de enviar el header:
```bash
curl -X POST http://localhost:8000/v1/cfdi/carta-porte/facturify \
  -H "Content-Type: application/json" \
  -d @examples/carta_porte_facturify_format.json
```

### Caso 3: JSON como string

Si ves en los logs:
```
🔑 Tipo del objeto parseado: <class 'str'>
```

**Problema**: Estás enviando el JSON como un string escapado:
```json
"{\"emisor\": {\"uuid\": \"...\"}}"  ← INCORRECTO
```

**Solución**: Envía el JSON directamente:
```json
{"emisor": {"uuid": "..."}}  ← CORRECTO
```

### Caso 4: JSON inválido

Si ves:
```
❌ ERROR AL PARSEAR JSON: Expecting property name enclosed in double quotes
```

**Problema**: El JSON tiene errores de sintaxis (comas faltantes, comillas incorrectas, etc.)

**Solución**: Valida tu JSON en https://jsonlint.com/

## Ejemplo de Request Correcto

```bash
curl -X POST http://localhost:8000/v1/cfdi/carta-porte/facturify \
  -H "Content-Type: application/json" \
  -H "Accept: application/json" \
  -d '{
    "emisor": {
      "uuid": "6fe768d7-922f-4b8a-b1b7-ac2c30300d89"
    },
    "receptor": {
      "uuid": "96076f99-7105-4a62-a732-1ea33d88f4a0"
    },
    "factura": {
      "fecha": "2026-01-21 15:58:20",
      "tipo": "ingreso",
      ...
    }
  }'
```

## Logs Esperados en Request Exitoso

```
🔍 RAW REQUEST - POST /v1/cfdi/carta-porte/facturify
📋 Content-Type: application/json
📏 Content-Length: 2543 bytes
✅ JSON PARSEADO CORRECTAMENTE
🔑 Tipo del objeto parseado: <class 'dict'>
🔑 Keys del objeto: ['emisor', 'receptor', 'factura']
================================================================================
✅ PAYLOAD VALIDADO CORRECTAMENTE EN /v1/cfdi/carta-porte/facturify
🔍 Tipo de payload: <class 'app.application.dtos.facturify_format.FacturifyCartaPorteRequest'>
📄 JSON recibido y validado:
{
  "emisor": {...},
  "receptor": {...},
  "factura": {...}
}
```

## Herramientas de Testing

### Con curl
```bash
curl -X POST http://localhost:8000/v1/cfdi/carta-porte/facturify \
  -H "Content-Type: application/json" \
  -d @examples/carta_porte_facturify_format.json
```

### Con httpie
```bash
http POST http://localhost:8000/v1/cfdi/carta-porte/facturify \
  Content-Type:application/json < examples/carta_porte_facturify_format.json
```

### Con Python requests
```python
import requests
import json

with open('examples/carta_porte_facturify_format.json') as f:
    payload = json.load(f)

response = requests.post(
    'http://localhost:8000/v1/cfdi/carta-porte/facturify',
    json=payload,  # ← Usa json= NO data=
    headers={'Content-Type': 'application/json'}
)
```

## Checklist de Debugging

- [ ] El Content-Type es `application/json`
- [ ] El body es JSON válido (sin errores de sintaxis)
- [ ] El JSON NO está escapado como string
- [ ] El JSON tiene las keys principales: `emisor`, `receptor`, `factura`
- [ ] Los UUIDs son válidos (formato UUID v4)
- [ ] Las fechas están en formato ISO 8601 o compatible
- [ ] No hay comas finales en arrays u objetos
- [ ] Todas las comillas son dobles ("), no simples (')
