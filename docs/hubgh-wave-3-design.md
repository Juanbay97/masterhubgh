# HubGH Wave 3 Design

## Objetivo

Implementar Sprint 3 (Persona 360 v2) en slices controlados, preservando compatibilidad de rutas/contratos y enfocando mejoras en:

1. Envelope de eventos unificado
2. Secciones/filtros operativos
3. Acciones contextuales con permisos finos

## Orden operativo (S3)

1. **S3.1** Envelope de evento unificado
2. **S3.2** Secciones por dimensión y filtros
3. **S3.3** Acciones contextuales y permisos finos

## Criterios de salida por slice

### S3.1
- Timeline con estructura de evento consistente entre fuentes (`Novedad Laboral`, `GH Novedad`, SST, Bienestar).
- Sin cambios de endpoint signature en [`get_persona_stats()`](frappe-bench/apps/hubgh/hubgh/hubgh/page/persona_360/persona_360.py:9).

### S3.2
- Filtros por fecha/módulo/severidad/estado funcionales en backend o compatibles con frontend existente.
- Respuesta estable para consumo en la página [`persona_360.py`](frappe-bench/apps/hubgh/hubgh/hubgh/page/persona_360/persona_360.py).

### S3.3
- Acciones visibles solo por rol autorizado.
- Sin expansión accidental de privilegios respecto a [`permissions.py`](frappe-bench/apps/hubgh/hubgh/hubgh/permissions.py).

## Guardrails no-regresión

- No romper navegación actual en Persona 360.
- No alterar permisos globales fuera de puntos de control explícitos.
- Mantener semántica de datos sensibles/clinical definida en [`user_can_access_dimension()`](frappe-bench/apps/hubgh/hubgh/hubgh/permissions.py:67).

