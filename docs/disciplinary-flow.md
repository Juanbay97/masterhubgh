# Proceso Disciplinario — Documentación Técnica

**Módulo**: Hubgh — Proceso Disciplinario  
**Change**: `disciplinary-flow-refactor`  
**Estado**: Implementado (Phases 0–10)  
**Fecha**: 2026-04-23

---

## 1. Resumen del Flujo

El módulo disciplinario gestiona investigaciones laborales desde la apertura hasta el cierre con sanción o archivo. La unidad de trabajo es el **Caso Disciplinario**, que contiene 1..N **Afectados Disciplinarios** (uno por empleado involucrado). Cada afectado sigue su propio ciclo de vida independiente.

---

## 2. Máquina de Estados — Caso Disciplinario

```
                          ┌───────────────────────────────────────────────┐
                          │                                               │
          open_case()     │                                               ▼
  NUEVA ──────────────► SOLICITADO ──── triage*() ───► EN TRIAGE ──────────────────┐
  solicitud (Jefe PDV)                  (RRLL)                                     │
                                                                                   │
                                              triage_programar_descargos()         │ triage_cerrar_*()
                                                        │                          │
                                                        ▼                          ▼
                                            DESCARGOS          CERRADO (directo)
                                            PROGRAMADOS    ◄─── (Recordatorio /
                                                │               Llamado directo)
                                                │
                                  marcar_citacion_entregada()
                                                │
                                                ▼
                                             CITADO
                                                │
                                  iniciar_descargos()
                                                │
                                                ▼
                                          EN DESCARGOS
                                                │
                                  guardar_acta_descargos()
                                                │
                                                ▼
                                          EN DELIBERACIÓN
                                                │
                              cerrar_afectado_con_sancion()
                                                │
                                     (todos los afectados cerrados)
                                                │
                                                ▼
                                            CERRADO
```

**Regla de estado mínimo (multi-afectado):**  
El estado del Caso refleja el estado MÍNIMO de avance entre todos sus Afectados activos.  
Un Caso sólo pasa a CERRADO cuando TODOS los Afectados están en estado Cerrado.

---

## 3. Máquina de Estados — Afectado Disciplinario

```
  [creación]
      │
      ▼
  EN TRIAGE ──────────────────────────────────────────────────────┐
      │                                                           │
      │ triage_programar_descargos()                             │ triage_cerrar_recordatorio()
      ▼                                                           │ triage_cerrar_llamado_directo()
  DESCARGOS PROGRAMADOS                                           │
      │                                                           ▼
      │ marcar_citacion_entregada()                           CERRADO ◄──── outcome = Recordatorio /
      ▼                                                                     Llamado de Atención Directo /
   CITADO                                                                   Archivo (sin descargos)
      │
      │ iniciar_descargos()
      ▼
  EN DESCARGOS
      │
      │ guardar_acta_descargos()
      ▼
  EN DELIBERACIÓN
      │
      │ cerrar_afectado_con_sancion(outcome=...)
      ▼
  CERRADO ◄──── outcome = Llamado de Atención /
                Suspensión / Terminación / Archivo
```

---

## 4. Outcomes y Efectos

| Outcome | Estado final Afectado | Efecto en Ficha Empleado | Genera documento |
|---|---|---|---|
| `Recordatorio de Funciones` | Cerrado | ninguno | `recordatorio_funciones.docx` |
| `Llamado de Atención Directo` | Cerrado | ninguno | `acta_cierre_llamado.docx` |
| `Llamado de Atención` | Cerrado | ninguno | `acta_cierre_llamado.docx` |
| `Suspensión` | Cerrado | `estado = Suspendido` + fechas | `acta_cierre_sancion.docx` |
| `Terminación` | Cerrado | dispara `retirement_service` | `terminacion_justa_causa.docx` |
| `Archivo` | Cerrado | ninguno | ninguno |

Los outcomes `Recordatorio de Funciones` y `Llamado de Atención Directo` se aplican desde triage (sin descargos). Los demás se aplican después de deliberación.

---

## 5. Roles y Visibilidad

| Rol | Acceso Bandeja | Ver datos Afectado | Ver datos sensibles | Ver Caso |
|---|---|---|---|---|
| `GH - RRLL` | Todos los casos | Completo | Completo | Completo |
| `GH - Bienestar` / otros GH | Restringido (permission query) | Solo proyección externa | No | Solo si asignado |
| `Gerente GH` con sensitive | Restringido | Proyección sensitive (outcome resumido) | Sí | Solo si asignado |
| Empleado (self) | No | No ve sus propios disciplinarios | No | No |
| `Jefe PDV` | No ve bandeja RRLL | No | No | Solo el que abrió (Solicitado) |

**Proyección pública** (`CONCLUSION_PUBLICA_MAP`):
- `Recordatorio de Funciones` → `"Recordatorio de funciones"`
- `Llamado de Atención Directo` → `"Llamado de atención"`
- `Llamado de Atención` → `"Llamado de atención"`
- `Suspensión` → `"Sanción aplicada"`
- `Terminación` → `"Sanción aplicada"`
- `Archivo` → `"Proceso archivado"`
- `None` (caso abierto) → `"En proceso"`

---

## 6. DocTypes del Módulo

| DocType | Tipo | Propósito |
|---|---|---|
| `Caso Disciplinario` | Documento | Unidad principal de investigación |
| `Afectado Disciplinario` | Documento | Un empleado en un caso |
| `RIT Articulo` | Documento | Catálogo de artículos del RIT |
| `Articulo RIT Caso` | Child Table | Artículos RIT referenciados en un Caso |
| `Disciplinary Transition Log` | Child Table | Historial de transiciones de estado |
| `Citacion Disciplinaria` | Documento | Citación generada para un Afectado |
| `Acta Descargos` | Documento | Registro de la sesión de descargos |
| `Comunicado Sancion` | Documento | Comunicado formal de sanción |
| `Evidencia Disciplinaria` | Documento | Archivo adjunto de evidencia |

---

## 7. Variables Jinja por Plantilla DOCX

Todas las plantillas viven en `hubgh/hubgh/public/templates/disciplinary/`.  
El renderizado se hace via `disciplinary_workflow_service.render_document(template_name, context)`.

### 7.1 `citacion.docx`

**Fuente de datos**: `Citacion Disciplinaria` + `Afectado Disciplinario` + `Caso Disciplinario`

| Variable | Campo fuente |
|---|---|
| `{{ ciudad_emision }}` | Configuración de empresa |
| `{{ fecha_citacion }}` | `Citacion.fecha_emision` o `today()` |
| `{{ empleado.nombre }}` | `Ficha Empleado.nombre_completo` |
| `{{ empleado.cedula }}` | `Ficha Empleado.cedula` |
| `{{ empleado.cargo }}` | `Ficha Empleado.cargo` |
| `{{ empleado.pdv }}` | `Ficha Empleado.punto_venta` |
| `{{ empresa.razon_social }}` | `Company.company_name` |
| `{{ fecha_programada_descargos }}` | `Citacion.fecha_programada_descargos` |
| `{{ hora_descargos }}` | `Citacion.hora_descargos` |
| `{{ lugar }}` | `Citacion.lugar` |
| `{%p for a in articulos %}` | `Caso.articulos_rit` (child table) |
| `{{ a.numero }}`, `{{ a.texto }}` | `RIT Articulo.numero`, `.texto` |
| `{{ hechos_narrados }}` | `Caso.hechos_detallados` |
| `{{ firmante.nombre }}` | parámetro `firmante` de la llamada |
| `{{ firmante.cargo }}` | parámetro `firmante_cargo` |

### 7.2 `diligencia_descargos.docx`

**Fuente de datos**: `Acta Descargos` + `Afectado Disciplinario` + `Caso Disciplinario`

| Variable | Campo fuente |
|---|---|
| `{{ fecha_sesion }}` | `Acta.fecha_sesion` |
| `{{ lugar_sesion }}` | `Acta.lugar` |
| `{{ empleado.* }}` | Igual que citacion.docx |
| `{{ empresa.* }}` | Igual que citacion.docx |
| `{{ fecha_ingreso_empleado }}` | `Ficha Empleado.fecha_ingreso` |
| `{{ cargo_actual }}` | `Ficha Empleado.cargo` |
| `{{ jefe_inmediato }}` | `Ficha Empleado.jefe_inmediato` |
| `{{ hechos_leidos }}` | `Caso.hechos_detallados` |
| `{%p for qa in preguntas_respuestas %}` | `Acta.preguntas_respuestas` (child) |
| `{{ qa.pregunta }}`, `{{ qa.respuesta }}` | `Pregunta Respuesta.pregunta`, `.respuesta` |
| `{{ firma_empleado }}` | `Acta.firma_empleado` (bool) |
| `{{ testigo_1.nombre }}`, `{{ testigo_2.nombre }}` | `Acta.participantes` filtrado por rol Testigo |
| `{{ firmante.* }}` | Igual que citacion.docx |

### 7.3 `acta_cierre_sancion.docx`

**Fuente de datos**: `Comunicado Sancion` + `Afectado Disciplinario`

| Variable | Campo fuente |
|---|---|
| `{{ empleado.* }}`, `{{ empresa.* }}` | Igual |
| `{{ fecha_emision }}` | `Comunicado.fecha_emision` |
| `{{ fundamentos }}` | `Comunicado.fundamentos` |
| `{%p for a in articulos %}` | `Comunicado.articulos_rit` (child) |
| `{{ sancion.tipo }}` | `Afectado.decision_final_afectado` |
| `{{ sancion.fecha_inicio }}` | `Afectado.fecha_inicio_suspension` |
| `{{ sancion.fecha_fin }}` | `Afectado.fecha_fin_suspension` |
| `{{ sancion.dias }}` | Calculado: días entre inicio y fin |
| `{{ firmante.* }}` | Igual |

### 7.4 `terminacion_justa_causa.docx`

| Variable | Campo fuente |
|---|---|
| `{{ empleado.* }}`, `{{ empresa.* }}` | Igual |
| `{{ fecha_emision }}` | `Comunicado.fecha_emision` |
| `{{ fundamentos }}` | `Comunicado.fundamentos` |
| `{%p for a in articulos %}` | `Comunicado.articulos_rit` |
| `{{ fecha_ultimo_dia }}` | `Afectado.fecha_cierre_afectado` |
| `{{ firmante.* }}` | Igual |

### 7.5 `acta_cierre_llamado.docx`

| Variable | Campo fuente |
|---|---|
| `{{ empleado.* }}`, `{{ empresa.* }}` | Igual |
| `{{ fecha_emision }}` | `Comunicado.fecha_emision` o `today()` |
| `{{ tipo_llamado }}` | `Afectado.decision_final_afectado` |
| `{{ fundamentos }}` | Parámetro `resumen_hechos` |
| `{%p for a in articulos %}` | `Caso.articulos_rit` |
| `{{ firmante.* }}` | Igual |

### 7.6 `recordatorio_funciones.docx`

| Variable | Campo fuente |
|---|---|
| `{{ para }}` | `Ficha Empleado.nombre_completo` |
| `{{ de }}` | `firmante.nombre` |
| `{{ asunto }}` | `"Recordatorio de funciones"` (literal) |
| `{{ fecha }}` | `today()` |
| `{{ cuerpo }}` | Parámetro `resumen_hechos` |
| `{{ empresa.* }}` | Igual |
| `{{ firmante.* }}` | Igual |

---

## 8. Servicios Principales

### `disciplinary_workflow_service.py`

| Función | Descripción |
|---|---|
| `open_case(empleados, hechos, articulos, rol_apertura)` | Crea Caso + N Afectados |
| `triage_programar_descargos(afectado_name, fecha, lugar, hora, firmante)` | Genera Citacion + DOCX |
| `triage_cerrar_recordatorio(afectado_name, firmante, resumen_hechos)` | Cierra afectado sin descargos |
| `triage_cerrar_llamado_directo(afectado_name, firmante, resumen_hechos)` | Cierra con llamado directo |
| `marcar_citacion_entregada(citacion_name)` | Transiciona Afectado → Citado |
| `iniciar_descargos(afectado_name)` | Crea Acta borrador → En Descargos |
| `guardar_acta_descargos(acta_name, data)` | Valida y genera DOCX del acta |
| `cerrar_afectado_con_sancion(afectado_name, outcome, ...)` | Aplica sanción + efectos + Comunicado |
| `sync_case_state_from_afectados(caso_name)` | Recalcula estado Caso según mínimo |
| `render_document(template_name, context)` | Renderiza DOCX con docxtpl |

### `disciplinary_case_service.py` (extensiones)

| Función | Descripción |
|---|---|
| `get_disciplinary_tray(filters)` | Datos para bandeja — multi-afectado |
| `compute_proxima_accion(caso, afectados, citaciones)` | Texto acción siguiente |
| `detect_citacion_vencida(afectados, citaciones_by_afectado)` | Flag vencida |
| `sync_disciplinary_case_effects(afectado_name)` | Efectos en Ficha Empleado |

---

## 9. Scheduler Jobs

| Job | Frecuencia | Descripción |
|---|---|---|
| `scheduler_alertar_citaciones_vencidas` | Diario | Alerta al RRLL si hay citaciones con fecha vencida sin entrega |
| `scheduler_enviar_resumen_rrll` | Diario | Resumen de casos activos enviado a RRLL |
| `process_closed_disciplinary_cases` | Diario | Procesa efectos de casos recién cerrados |

---

## 10. Tests

| Módulo de test | Tests | Cobertura |
|---|---|---|
| `test_rit_articulo_fixture` | 15 | Fixture RIT Articulos |
| `test_disciplinary_doctypes` | 39 | Validaciones DocType |
| `test_disciplinary_case_service` | 4 | Service layer basic |
| `test_disciplinary_workflow` | 67 | Service layer E2E |
| `test_acta_descargos` | 29 | Acta + Comunicado |
| `test_disciplinary_permissions` | 50 | Permission query |
| `test_disciplinary_bandeja` | 16 | Bandeja + próxima acción |
| `test_persona_360_disciplinary_projection` | 16 | Visibilidad por rol |
| `test_carpeta_documental_disciplinary` | 8 | Documentos en carpeta |
| `test_punto_360_disciplinary` | 3 | Conteo en punto 360 |
| **TOTAL** | **247** | |
