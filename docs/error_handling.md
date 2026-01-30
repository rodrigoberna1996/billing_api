# Manejo de Errores

## Errores de Facturify y el SAT

La API ahora parsea y muestra claramente los errores del SAT y de validación de Facturify.

### Tipo 1: Errores del SAT/PAC

#### Ejemplo de Error Original de Facturify

```json
{
  "success": false,
  "message": "Error no detectado: (SAT: El campo DomicilioFiscalReceptor del receptor, debe encontrarse en la lista de RFC inscritos no cancelados en el SAT.)",
  "code": "CFDI40147",
  "pac": "Finkok"
}
```

#### Respuesta de la API (Mejorada)

```json
{
  "detail": {
    "message": "Error del SAT: El campo DomicilioFiscalReceptor del receptor, debe encontrarse en la lista de RFC inscritos no cancelados en el SAT.",
    "type": "external_service_error",
    "hint": "Verifica los datos fiscales del receptor y emisor en el SAT"
  }
}
```

### Tipo 2: Errores de Validación de Facturify

#### Ejemplo de Error Original de Facturify

```json
{
  "code": 33,
  "message": "Los datos proporcionados no cumplen las reglas de validación",
  "errors": [
    {
      "field": "factura.serie",
      "message": "La serie que envió, no existe.",
      "code": 34
    }
  ]
}
```

#### Respuesta de la API (Mejorada)

```json
{
  "detail": {
    "message": "Los datos proporcionados no cumplen las reglas de validación:\n• factura.serie: La serie que envió, no existe.",
    "type": "external_service_error",
    "hint": "Verifica los datos fiscales del receptor y emisor en el SAT"
  }
}
```

#### Con Múltiples Errores

```json
{
  "code": 33,
  "message": "Los datos proporcionados no cumplen las reglas de validación",
  "errors": [
    {
      "field": "factura.serie",
      "message": "La serie que envió, no existe.",
      "code": 34
    },
    {
      "field": "receptor.rfc",
      "message": "El RFC no es válido.",
      "code": 35
    }
  ]
}
```

**Respuesta de la API:**

```json
{
  "detail": {
    "message": "Los datos proporcionados no cumplen las reglas de validación:\n• factura.serie: La serie que envió, no existe.\n• receptor.rfc: El RFC no es válido.",
    "type": "external_service_error",
    "hint": "Verifica los datos fiscales del receptor y emisor en el SAT"
  }
}
```

### Logs del Servidor

El servidor ahora registra información detallada del error:

```
ERROR Facturify error: Error del SAT: El campo DomicilioFiscalReceptor del receptor, debe encontrarse en la lista de RFC inscritos no cancelados en el SAT.
ERROR Error details: {
  'success': False,
  'error_code': 'CFDI40147',
  'pac': 'Finkok',
  'original_message': 'Error no detectado: (SAT: ...)',
  'sat_message': 'El campo DomicilioFiscalReceptor del receptor, debe encontrarse en la lista de RFC inscritos no cancelados en el SAT.',
  'friendly_message': 'El código postal del receptor no está registrado en el SAT',
  'user_message': 'El código postal del receptor no está registrado en el SAT. Detalle: El campo DomicilioFiscalReceptor del receptor, debe encontrarse en la lista de RFC inscritos no cancelados en el SAT.'
}
```

## Códigos de Error Comunes del SAT

| Código | Descripción | Solución |
|--------|-------------|----------|
| `CFDI40147` | Código postal del receptor no registrado en el SAT | Verifica que el código postal del receptor esté activo en el SAT |
| `CFDI40148` | RFC del receptor no activo en el SAT | Verifica que el RFC del receptor esté dado de alta y activo |
| `CFDI40149` | Régimen fiscal del receptor no válido | Verifica el régimen fiscal del receptor |
| `CFDI33101` | RFC del emisor no activo en el SAT | Verifica que el RFC del emisor esté activo |
| `CFDI33102` | Certificado del emisor no válido | Renueva o verifica el certificado de sello digital |
| `CFDI33103` | Sello digital no válido | Verifica la configuración del certificado |

## Tipos de Errores

### 1. Errores de Validación (`ValidationError`)

Errores de negocio o validación de datos antes de enviar a Facturify.

**Ejemplo:**
```json
{
  "detail": "El emisor no cuenta con UUID valido en Facturify"
}
```

### 2. Errores de Servicio Externo (`ExternalServiceError`)

Errores provenientes de Facturify o el SAT.

**Ejemplo:**
```json
{
  "detail": {
    "message": "Error del SAT: El campo DomicilioFiscalReceptor del receptor, debe encontrarse en la lista de RFC inscritos no cancelados en el SAT.",
    "type": "external_service_error",
    "hint": "Verifica los datos fiscales del receptor y emisor en el SAT"
  }
}
```

### 3. Errores de Entidad No Encontrada (`EntityNotFound`)

Cuando no se encuentra un recurso solicitado.

**Ejemplo:**
```json
{
  "detail": "Factura no encontrada"
}
```

## Debugging

Para debugging detallado, revisa los logs del servidor. Cada error incluye:

1. **Mensaje para el usuario**: Extraído y limpio del mensaje del SAT
2. **Código de error**: Código específico del SAT o PAC
3. **PAC**: Proveedor de certificación (Finkok, etc.)
4. **Mensaje original**: Respuesta completa de Facturify
5. **Mensaje del SAT**: Texto extraído entre paréntesis
6. **Mensaje amigable**: Descripción en lenguaje claro (cuando está disponible)

## Recomendaciones

1. **Valida datos fiscales**: Antes de enviar, verifica que el RFC y código postal estén activos en el SAT
2. **Revisa los logs**: Los logs del servidor contienen información detallada del error
3. **Consulta el catálogo del SAT**: Para códigos de error específicos, consulta la documentación oficial del SAT
4. **Prueba en sandbox**: Usa el ambiente de pruebas de Facturify antes de producción
