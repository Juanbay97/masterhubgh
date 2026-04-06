# Auditoría rápida de catálogos SIESA en contratación

## Hallazgos confirmados en código

1. El número de contrato se calcula en validación de contrato en [`Contrato._ensure_numero_contrato()`](../frappe-bench/apps/hubgh/hubgh/hubgh/doctype/contrato/contrato.py:12), tomando el máximo de `tabContrato` y sumando 1 con [`select max(numero_contrato)`](../frappe-bench/apps/hubgh/hubgh/hubgh/doctype/contrato/contrato.py:20).
2. El formulario de contratación captura `CCF` como Link a [`Entidad CCF Siesa`](../frappe-bench/apps/hubgh/hubgh/hubgh/doctype/entidad_ccf_siesa/entidad_ccf_siesa.json:48) en [`bandeja_contratacion.js`](../frappe-bench/apps/hubgh/hubgh/hubgh/page/bandeja_contratacion/bandeja_contratacion.js:73).
3. En snapshot de contratación, `ccf_siesa` se toma solo de `Datos Contratacion` y no hace fallback al candidato en [`affiliation_contract_snapshot()`](../frappe-bench/apps/hubgh/hubgh/hubgh/contratacion_service.py:856). Esto puede dejar el campo vacío en UI aunque exista en candidato.
4. En creación de contrato sí hay fallback a candidato para CCF en [`create_contract()`](../frappe-bench/apps/hubgh/hubgh/hubgh/contratacion_service.py:924), por lo que el problema de no guardar suele apuntar a valor inválido o catálogo inconsistente.
5. `Unidad Negocio` y `Centro Trabajo` son catálogos distintos por diseño en [`Contrato`](../frappe-bench/apps/hubgh/hubgh/hubgh/doctype/contrato/contrato.json:54) y [`Contrato`](../frappe-bench/apps/hubgh/hubgh/hubgh/doctype/contrato/contrato.json:56). Si se ven iguales, el problema probable es carga de datos maestro, no definición de modelo.

## Datos de negocio confirmados por usuario

- CCF Bogotá: `001`
- CCF Medellín: `002`

## Hipótesis principal de la inconsistencia CCF

Registros erróneos dentro de `Entidad CCF Siesa` importados desde maestro con desalineación de columnas o mezcla de secciones, lo que explica ver textos de cargo como opción CCF.

## Plan de corrección propuesto

1. Auditar registros actuales de `Entidad CCF Siesa` y detectar valores no CCF.
2. Normalizar catálogo CCF dejando únicamente:
   - `001` Bogotá
   - `002` Medellín
3. Corregir snapshot para que `ccf_siesa` tenga fallback a candidato en [`affiliation_contract_snapshot()`](../frappe-bench/apps/hubgh/hubgh/hubgh/contratacion_service.py:856).
4. Verificar que al guardar en [`create_contract()`](../frappe-bench/apps/hubgh/hubgh/hubgh/contratacion_service.py:924) se persista `entidad_ccf_siesa` en contrato y `ccf_siesa` en datos contratación.
5. Revisar carga maestra de catálogos en [`import_madre_codigos.py`](../frappe-bench/apps/hubgh/hubgh/scripts/import_madre_codigos.py:16) para evitar mezcla futura.

## Criterios de aceptación

1. Selector CCF muestra solo dos opciones válidas.
2. CCF queda guardada en `Contrato` y en `Datos Contratacion`.
3. `Unidad Negocio` y `Centro Trabajo` muestran listas correctas e independientes según sus doctypes.
4. Flujo de contratación no rompe creación ni envío a SIESA.

