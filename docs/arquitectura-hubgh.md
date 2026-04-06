# Arquitectura de la app HubGH (Frappe)

Este documento explica la arquitectura de la aplicación **HubGH** y cómo interactúan sus módulos. También indica **dónde editar** para hacer cambios si no eres usuario técnico.

## 1. Visión general (simple)

HubGH es una app construida sobre **Frappe**, y corre dentro de un “bench” (entorno de Frappe). La app define:

- **Tipos de datos (DocTypes)**: Formularios y tablas principales.
- **Páginas (Pages)**: Vistas personalizadas como paneles 360.
- **Workspaces**: Menús y accesos de navegación.
- **Permisos y Roles**: Qué puede ver/editar cada perfil.
- **Branding y assets**: Logos, imágenes y plantillas de importación.

La base de la app vive en el directorio [`frappe-bench/apps/hubgh`](frappe-bench/apps/hubgh).

## 2. Componentes principales y cómo interactúan

### 2.1. Registro de la app y “hooks”

- El archivo de configuración principal es [`frappe-bench/apps/hubgh/hubgh/hooks.py`](frappe-bench/apps/hubgh/hubgh/hooks.py).
- Allí se declara el nombre de la app y su entrada al “Apps Screen”.
- Este archivo es el punto de integración con Frappe (no hay mucha lógica, pero es esencial para exponer la app).

### 2.2. Módulo principal

- La app define el módulo “Hubgh” en [`frappe-bench/apps/hubgh/hubgh/modules.txt`](frappe-bench/apps/hubgh/hubgh/modules.txt).
- Este módulo agrupa DocTypes, páginas y workspaces asociados.

### 2.3. DocTypes (datos principales)

Los DocTypes principales están en:

- [`frappe-bench/apps/hubgh/hubgh/hubgh/doctype`](frappe-bench/apps/hubgh/hubgh/hubgh/doctype)

Cada DocType tiene tres archivos clave:

- **JSON** (estructura de campos y permisos): p.ej. [`caso_sst.json`](frappe-bench/apps/hubgh/hubgh/hubgh/doctype/caso_sst/caso_sst.json)
- **Python** (lógica del servidor): p.ej. [`caso_sst.py`](frappe-bench/apps/hubgh/hubgh/hubgh/doctype/caso_sst/caso_sst.py)
- **JS** (comportamiento en formulario): p.ej. [`caso_sst.js`](frappe-bench/apps/hubgh/hubgh/hubgh/doctype/caso_sst/caso_sst.js)

Los DocTypes se relacionan entre sí por campos tipo “Link” (ejemplo: **Ficha Empleado** enlaza a **Punto de Venta**). Esto aparece en el JSON de cada DocType.

Además, existe un script de creación de DocTypes usado para carga inicial:

- [`setup_doctypes.py`](frappe-bench/apps/hubgh/hubgh/setup_doctypes.py) con funciones como [`setup()`](frappe-bench/apps/hubgh/hubgh/setup_doctypes.py:4)

### 2.4. Pages (vistas personalizadas)

Las páginas personalizadas están en:

- [`frappe-bench/apps/hubgh/hubgh/hubgh/page`](frappe-bench/apps/hubgh/hubgh/hubgh/page)

Ejemplos:

- Página **Punto 360**: [`punto_360.js`](frappe-bench/apps/hubgh/hubgh/hubgh/page/punto_360/punto_360.js), [`punto_360.py`](frappe-bench/apps/hubgh/hubgh/hubgh/page/punto_360/punto_360.py)
- Página **Persona 360**: [`persona_360.js`](frappe-bench/apps/hubgh/hubgh/hubgh/page/persona_360/persona_360.js), [`persona_360.py`](frappe-bench/apps/hubgh/hubgh/hubgh/page/persona_360/persona_360.py)

Estas páginas **consumen datos** de los DocTypes (por ejemplo, resúmenes por empleado o punto de venta). Por eso, si cambias un DocType, estas páginas pueden requerir ajustes.

### 2.5. Workspaces (menús y navegación)

Los workspaces definidos están en:

- [`frappe-bench/apps/hubgh/hubgh/hubgh/workspace`](frappe-bench/apps/hubgh/hubgh/hubgh/workspace)

Ejemplos:

- Gestión Humana: [`gestión_humana.json`](frappe-bench/apps/hubgh/hubgh/hubgh/workspace/gestión_humana/gestión_humana.json)
- Operación: [`operación.json`](frappe-bench/apps/hubgh/hubgh/hubgh/workspace/operación/operación.json)
- Mi Perfil: [`mi_perfil.json`](frappe-bench/apps/hubgh/hubgh/hubgh/workspace/mi_perfil/mi_perfil.json)

Los scripts de setup también crean workspaces y accesos:

- [`setup_foundation.py`](frappe-bench/apps/hubgh/hubgh/setup_foundation.py) con [`setup_workspaces()`](frappe-bench/apps/hubgh/hubgh/setup_foundation.py:16)
- [`setup_workspace.py`](frappe-bench/apps/hubgh/hubgh/setup_workspace.py) crea un workspace “HubGH” con atajos.

### 2.6. Roles y permisos

Roles y permisos se definen con scripts de setup:

- [`setup_foundation.py`](frappe-bench/apps/hubgh/hubgh/setup_foundation.py) con [`setup_roles()`](frappe-bench/apps/hubgh/hubgh/setup_foundation.py:4)
- [`setup_gh_permissions.py`](frappe-bench/apps/hubgh/hubgh/setup_gh_permissions.py) ajusta permisos para la app.

Esto define quién puede ver o editar DocTypes, páginas y workspaces.

### 2.7. Branding y assets

Logos y templates están en:

- Logos: [`public/images`](frappe-bench/apps/hubgh/hubgh/public/images)
- Templates CSV: [`public/templates`](frappe-bench/apps/hubgh/hubgh/public/templates)

El branding se aplica en:

- [`setup_foundation.py`](frappe-bench/apps/hubgh/hubgh/setup_foundation.py) con [`setup_branding()`](frappe-bench/apps/hubgh/hubgh/setup_foundation.py:72)
- [`set_branding.py`](frappe-bench/apps/hubgh/hubgh/set_branding.py) para configurar logos en el sitio.

## 3. Cómo fluye la información (interacción entre módulos)

1. **DocTypes** guardan datos centrales (empleados, puntos de venta, casos, etc.).
2. **Pages** consultan esos DocTypes para mostrar paneles y vistas 360.
3. **Workspaces** organizan accesos a DocTypes y Pages.
4. **Roles y permisos** controlan qué ve cada usuario.
5. **Branding** personaliza la experiencia visual.

En resumen: **DocTypes → Pages → Workspaces → Roles**.

## 3.1. Flujo de onboarding de candidatos y documentos (nuevo)

**Rutas públicas:**

- Onboarding de candidato: [`frappe-bench/apps/hubgh/hubgh/www/candidato.html`](frappe-bench/apps/hubgh/hubgh/www/candidato.html)
- Redirección a documentos (tras login): [`frappe-bench/apps/hubgh/hubgh/www/candidato_documentos.html`](frappe-bench/apps/hubgh/hubgh/www/candidato_documentos.html)

**Back-end (creación del candidato):**

- Endpoint público: [`create_candidate()`](frappe-bench/apps/hubgh/hubgh/www/candidato.py:11)
- DocType base: [`Candidato`](frappe-bench/apps/hubgh/hubgh/hubgh/doctype/candidato/candidato.json)
- Disponibilidad (tabla hija): [`Candidato Disponibilidad`](frappe-bench/apps/hubgh/hubgh/hubgh/doctype/candidato_disponibilidad/candidato_disponibilidad.json)

**Documentos y seguimiento:**

- Página interna (Desk): [`seleccion_documentos`](frappe-bench/apps/hubgh/hubgh/hubgh/page/seleccion_documentos/seleccion_documentos.js:1)
- Servicios: [`get_documentos()`](frappe-bench/apps/hubgh/hubgh/hubgh/page/seleccion_documentos/seleccion_documentos.py:12) y [`get_candidato_estado()`](frappe-bench/apps/hubgh/hubgh/hubgh/page/seleccion_documentos/seleccion_documentos.py:41)
- Tabla hija de documentos: [`Candidato Documento`](frappe-bench/apps/hubgh/hubgh/hubgh/doctype/candidato_documento/candidato_documento.json)

**Flujo recomendado:**

1. Candidato completa onboarding público (sin login) y se crea el registro en **Candidato**.
2. Se genera/asegura el usuario web con rol **Candidato** (en server-side).
3. El candidato inicia sesión y carga documentos en la página de **selección de documentos**.
4. Selección interna revisa estados y aprueba/rechaza documentos en Desk.

## 3.2. Flujo de Bienestar y seguimiento 5/15/30 (S7)

Este flujo consolida el seguimiento de bienestar en dos capas: historial individual en Persona 360 y agregados por punto en Punto 360.

**Componentes clave:**

- Historial de seguimiento: [`_build_bienestar_followups()`](../frappe-bench/apps/hubgh/hubgh/hubgh/page/persona_360/persona_360.py:72)
- API Persona 360: [`get_persona_stats()`](../frappe-bench/apps/hubgh/hubgh/hubgh/page/persona_360/persona_360.py:155)
- Escalamiento de periodo de prueba: [`create_probation_escalation_if_needed()`](../frappe-bench/apps/hubgh/hubgh/hubgh/doctype/comentario_bienestar/comentario_bienestar.py:30)
- KPI de clima por punto: [`get_punto_stats()`](../frappe-bench/apps/hubgh/hubgh/hubgh/page/punto_360/punto_360.py:117)

**Contrato funcional:**

1. Cada comentario de bienestar genera checkpoints de seguimiento en 5/15/30 días.
2. Persona 360 expone un bloque aditivo `bienestar_followups` con estados `Completado`, `Pendiente`, `Vencido`.
3. Cuando el tipo de comentario es “Periodo de prueba - No aprobado”, se crea una `GH Novedad` con enrutamiento a cola RRLL.
4. Punto 360 expone métricas `kpi_clima` (visitas, cobertura, temas, aprobados/no aprobados).

**DocType impactado:**

- Se amplía el catálogo `tipo` en [`comentario_bienestar.json`](../frappe-bench/apps/hubgh/hubgh/hubgh/doctype/comentario_bienestar/comentario_bienestar.json)

## 3.3. Flujo de Formación: catálogo, cumplimiento e integración LMS (S8)

Se adiciona una capa de formación no disruptiva sobre Punto 360 con tres endpoints nuevos (todos aditivos):

- Catálogo de asignaciones: [`get_formacion_catalog_assignments()`](../frappe-bench/apps/hubgh/hubgh/hubgh/page/punto_360/punto_360.py:561)
- Cumplimiento y alertas: [`get_formacion_compliance()`](../frappe-bench/apps/hubgh/hubgh/hubgh/page/punto_360/punto_360.py:602)
- Contrato LMS-ready: [`get_lms_integration_contract()`](../frappe-bench/apps/hubgh/hubgh/hubgh/page/punto_360/punto_360.py:685)

**Reglas de arquitectura:**

1. **Asignación por contexto**: combina base + cargo/rol + punto/zona.
2. **Cumplimiento obligatorio**: calcula total, completadas, pendientes y `%`.
3. **Degradación segura**: si LMS no está disponible, el contrato responde estado `degraded` sin romper rutas existentes.
4. **Compatibilidad**: no se altera la firma histórica de [`get_punto_stats()`](../frappe-bench/apps/hubgh/hubgh/hubgh/page/punto_360/punto_360.py:117), solo se extiende información.

## 3.4. Superficies de salida (S7/S8)

**Persona 360**

- Endpoint: [`get_persona_stats()`](../frappe-bench/apps/hubgh/hubgh/hubgh/page/persona_360/persona_360.py:155)
- Bloques nuevos: `bienestar_followups`

**Punto 360**

- Endpoint base: [`get_punto_stats()`](../frappe-bench/apps/hubgh/hubgh/hubgh/page/punto_360/punto_360.py:117)
- Bloques nuevos: `kpi_clima`
- Endpoints complementarios: [`get_formacion_catalog_assignments()`](../frappe-bench/apps/hubgh/hubgh/hubgh/page/punto_360/punto_360.py:561), [`get_formacion_compliance()`](../frappe-bench/apps/hubgh/hubgh/hubgh/page/punto_360/punto_360.py:602), [`get_lms_integration_contract()`](../frappe-bench/apps/hubgh/hubgh/hubgh/page/punto_360/punto_360.py:685)

**Trazabilidad de implementación y validación**

- Wave 7: [`hubgh-wave-7-implementation-log.md`](./hubgh-wave-7-implementation-log.md), [`hubgh-wave-7-verification.md`](./hubgh-wave-7-verification.md), [`hubgh-wave-7-change-summary.md`](./hubgh-wave-7-change-summary.md)
- Wave 8: [`hubgh-wave-8-implementation-log.md`](./hubgh-wave-8-implementation-log.md), [`hubgh-wave-8-verification.md`](./hubgh-wave-8-verification.md), [`hubgh-wave-8-change-summary.md`](./hubgh-wave-8-change-summary.md)

## 3.5. Ola 1 Fundación hardening sin deuda

Esta ola congela contratos mínimos y define gates base para no romper compatibilidad mientras se endurece el backbone.

**Contratos baseline congelados (tests de contrato):**

- Persona 360: claves mínimas `info`, `timeline`, `timeline_sections`, `sst_cards`, `filters_applied`, `contextual_actions`, `bienestar_followups`.
- Punto 360: `info` con KPIs aditivos (`kpi_operativo`, `kpi_sst`, `kpi_ingreso`, `kpi_liderazgo`, `kpi_bienestar`, `kpi_clima`, `kpi_formacion`) y `actionable_hub` (`widgets`, `feeds`, `contextual_actions`).
- Dashboards por módulo (`seleccion`, `relaciones_laborales`, `sst`, `operacion`): contrato común con `module`, `meta.generated_at`, `kpis.items`, `alerts.items`, `actions`.

**Matriz mínima documental/sensibilidad (RBAC + ABAC base):**

- Operacional: documentos generales (ejemplo: `Carta Oferta`).
- Sensible: disciplinario/retiro (ejemplo: `Acta de Retiro`, `Caso Disciplinario`).
- Clínico: SST/salud (ejemplo: `Historia Clínica`, `Examen Médico`, `Incapacidad`).
- Enforcement progresivo por modo de policy (`off/warn/enforce`) para mantener compatibilidad legacy.

**Gate mínimo Selección/Onboarding -> RRLL:**

- Requisitos mínimos: concepto médico `Favorable`, documento `SAGRILAFT` cargado y datos objetivo (`pdv_destino`, `fecha_tentativa_ingreso`).
- Si falta un requisito, el handoff queda bloqueado con errores explícitos y sin side effects de estado.

**Linaje mínimo candidato -> empleado en ingreso:**

- En evento de ingreso formalizado (`rrll.ingreso_formalizado`) se adjuntan referencias de linaje (`candidate`, `employee`) y contrato asociado cuando está disponible.

**Reportes de bandejas must-have (documentados, sin ola futura):**

- Selección: `app/seleccion_documentos` y `app/bandeja_contratacion`.
- RRLL: `app/bandeja_contratacion` y `app/bandeja_afiliaciones`.
- SST: `app/sst_bandeja`.
- Operación: `app/operacion_punto_lite`.

## 4. Dónde editar para hacer cambios (guía para no técnicos)

### 4.1. Cambiar campos o etiquetas de formularios

Editar el archivo JSON del DocType:

- Ejemplo: [`ficha_empleado.json`](frappe-bench/apps/hubgh/hubgh/hubgh/doctype/ficha_empleado/ficha_empleado.json)

Ahí puedes cambiar nombres de campos, opciones de listas y validaciones básicas.

### 4.2. Cambiar comportamiento del formulario (validaciones, acciones)

Editar el archivo JS del DocType:

- Ejemplo: [`ficha_empleado.js`](frappe-bench/apps/hubgh/hubgh/hubgh/doctype/ficha_empleado/ficha_empleado.js)

Esto controla acciones en pantalla (por ejemplo, mostrar mensajes, ocultar campos, cálculos en tiempo real).

### 4.3. Cambios de lógica del servidor

Editar el archivo Python del DocType:

- Ejemplo: [`ficha_empleado.py`](frappe-bench/apps/hubgh/hubgh/hubgh/doctype/ficha_empleado/ficha_empleado.py)

Aquí se colocan validaciones de servidor o reglas de negocio críticas.

### 4.4. Cambiar páginas personalizadas

Editar la página en:

- Ejemplo: [`punto_360.js`](frappe-bench/apps/hubgh/hubgh/hubgh/page/punto_360/punto_360.js)
- Ejemplo: [`punto_360.py`](frappe-bench/apps/hubgh/hubgh/hubgh/page/punto_360/punto_360.py)

### 4.5. Cambiar menús y accesos (Workspaces)

Editar los archivos JSON de workspaces:

- [`gestión_humana.json`](frappe-bench/apps/hubgh/hubgh/hubgh/workspace/gestión_humana/gestión_humana.json)
- [`operación.json`](frappe-bench/apps/hubgh/hubgh/hubgh/workspace/operación/operación.json)
- [`mi_perfil.json`](frappe-bench/apps/hubgh/hubgh/hubgh/workspace/mi_perfil/mi_perfil.json)

### 4.6. Cambiar logos o branding

- Reemplaza imágenes en [`public/images`](frappe-bench/apps/hubgh/hubgh/public/images)
- Ajusta branding en [`setup_foundation.py`](frappe-bench/apps/hubgh/hubgh/setup_foundation.py) o [`set_branding.py`](frappe-bench/apps/hubgh/hubgh/set_branding.py)

### 4.7. Plantillas de carga masiva (CSV)

- Plantillas en [`public/templates`](frappe-bench/apps/hubgh/hubgh/public/templates)

## 5. Recomendaciones para cambios seguros

1. **Empieza por cambios pequeños** (labels, opciones de Select).
2. Si cambias un DocType, revisa páginas 360 que consumen esos datos.
3. Para cambios de permisos, revisa [`setup_gh_permissions.py`](frappe-bench/apps/hubgh/hubgh/setup_gh_permissions.py).
4. Evita editar scripts de setup si no es necesario; estos son para instalación inicial.

## 6. Resumen rápido: “Mapa mental”

- **DocTypes**: estructura de datos (formularios).
- **Pages**: dashboards/360 basados en esos datos.
- **Workspaces**: navegación y accesos.
- **Roles/Permisos**: quién puede ver/editar.
- **Branding**: imagen institucional.

Si necesitas un cambio específico, puedo indicar exactamente qué archivo tocar y qué parte editar.

## 7. Validación rápida (menú lateral + Punto/Persona 360)

1. **Roles en páginas**: confirma que `System Manager` y `Gestión Humana` estén en:
   - [`punto_360.json`](frappe-bench/apps/hubgh/hubgh/hubgh/page/punto_360/punto_360.json)
   - [`persona_360.json`](frappe-bench/apps/hubgh/hubgh/hubgh/page/persona_360/persona_360.json)
2. **Workspace visible en sidebar**: verifica que el workspace **Gestión Humana** incluya esos roles y atajos:
   - [`gestión_humana.json`](frappe-bench/apps/hubgh/hubgh/hubgh/workspace/gestión_humana/gestión_humana.json)
3. **Recargar cambios de Workspace** (si no aparecen):
   - Ejecutar recarga de DocType “Workspace” o `bench migrate` (según tu flujo de despliegue).
4. **Flujo Punto 360**:
   - Buscador siempre visible arriba (campo `Punto de Venta`).
   - Listado solo cuando no hay punto seleccionado.
   - Botón **Volver a lista** para regresar al listado.

Estos comportamientos se implementan en [`punto_360.js`](frappe-bench/apps/hubgh/hubgh/hubgh/page/punto_360/punto_360.js).
# Novedades Laborales y Estado de Empleado

## Estados de Ficha Empleado
Se amplía el catálogo de estados para reflejar ausentismo temporal y retiro definitivo:

- Activo
- Inactivo
- Vacaciones
- Incapacitado
- Licencia
- Suspensión
- Separación del Cargo (temporal)
- Recomendación Médica
- Embarazo
- Retirado (definitivo)

## Tipos de Novedad Laboral
Se amplían los tipos de novedad y su impacto esperado:

- Incapacidad → Incapacitado (temporal)
- Licencia → Licencia (temporal)
- Vacaciones → Vacaciones (temporal)
- Suspensión → Suspensión (temporal)
- Separación del Cargo → Separación del Cargo (temporal)
- Recomendación Médica → Recomendación Médica (temporal)
- Embarazo → Embarazo (temporal)
- Retiro → Retirado (definitivo)
- Otro → sin cambio automático

## Reglas de transición
- Al crear/actualizar una novedad con **impacta_estado = 1**, se mapea automáticamente el **estado_destino** según el tipo (si no se define manualmente).
- Si la novedad está **Abierta** y la fecha fin no expiró, se aplica el estado temporal en la ficha del empleado.
- Si la novedad se **Cierra** o su **fecha_fin** expiró, se revierte el estado del empleado a **Activo** (si era un estado temporal).
- Para **Retiro**, el estado pasa a **Retirado** y no se revierte automáticamente.

## UI y reportes
- **Persona 360** muestra nuevos estados y permite crear novedades desde la vista.
- **Punto 360** mantiene el headcount basado solo en **Activo**. Los estados temporales y Retirado no cuentan como activos.
