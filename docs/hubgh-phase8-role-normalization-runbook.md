# HubGH Phase 8 — Normalización/Migración de Roles Legacy y Regresión de Permisos

## Objetivo

Consolidar aliases/roles legacy a un catálogo canónico HubGH, migrar asignaciones de usuario de forma idempotente y validar que los permisos críticos (App Shell, selección, RL, SST, operación y lectura documental por áreas) se mantengan consistentes.

## Alcance de Fase 8

- Catálogo canónico y mapeo legacy en [`role_matrix.py`](../frappe-bench/apps/hubgh/hubgh/hubgh/role_matrix.py).
- Migración idempotente de asignaciones de roles en [`phase8_role_normalization.py`](../frappe-bench/apps/hubgh/hubgh/patches/phase8_role_normalization.py).
- Ajustes de setup/compat transicional en [`setup_gh_permissions.py`](../frappe-bench/apps/hubgh/hubgh/setup_gh_permissions.py) y [`setup_foundation.py`](../frappe-bench/apps/hubgh/hubgh/setup_foundation.py).
- Unificación de chequeos en servicios/permisos:
  - [`document_service.py`](../frappe-bench/apps/hubgh/hubgh/hubgh/document_service.py)
  - [`permissions.py`](../frappe-bench/apps/hubgh/hubgh/hubgh/permissions.py)
  - [`contratacion_service.py`](../frappe-bench/apps/hubgh/hubgh/hubgh/contratacion_service.py)
  - [`shell.py`](../frappe-bench/apps/hubgh/hubgh/api/shell.py)
  - [`persona_360.py`](../frappe-bench/apps/hubgh/hubgh/hubgh/page/persona_360/persona_360.py)
  - [`punto_360.py`](../frappe-bench/apps/hubgh/hubgh/hubgh/page/punto_360/punto_360.py)

## Catálogo canónico y mapeo legacy

El catálogo y alias transicionales se centralizan en [`CANONICAL_ROLE_ALIASES`](../frappe-bench/apps/hubgh/hubgh/hubgh/role_matrix.py:7).

La migración `legacy -> canónico` se define en [`ROLE_MIGRATION_CANONICAL_MAP`](../frappe-bench/apps/hubgh/hubgh/hubgh/role_matrix.py:50).

Casos principales:

- `GH_Central`, `GH Central`, `Gestion Humana` -> `Gestión Humana`
- `Selección`, `Seleccion` -> `HR Selection`
- `Relaciones Laborales`, `Relaciones_Laborales` -> `HR Labor Relations`
- `SST` -> `HR SST`
- `Formación y Bienestar`, `Formacion y Bienestar` -> `HR Training & Wellbeing`
- `Jefe de tienda`, `Jefe de Punto` -> `Jefe_PDV`

## Patch de migración (idempotente)

Registrado en [`patches.txt`](../frappe-bench/apps/hubgh/hubgh/patches.txt:13) como `hubgh.patches.phase8_role_normalization`.

Lógica en [`execute()`](../frappe-bench/apps/hubgh/hubgh/patches/phase8_role_normalization.py:7):

1. Asegura existencia de rol canónico (`_ensure_role`).
2. Recorre usuarios con rol legacy.
3. Inserta rol canónico solo si no existe ya en `Has Role` para el usuario.
4. No elimina rol legacy (compatibilidad transicional, no pérdida de acceso).

### Propiedades operativas

- **Idempotente:** re-ejecutable sin duplicar `Has Role`.
- **Sin downtime funcional:** agrega roles canónicos sin retirar legacy.
- **Reversible en práctica:** el rollback puede quitar asignaciones canónicas añadidas y mantener legacy.

## Procedimiento en Staging

1. Actualizar código y migrar:

```bash
cd /workspace/frappe-bench && bench --site hubgh.test migrate
```

2. Verificar patch aplicado en logs/migración.

3. Validar muestra de usuarios:
   - Usuarios con `GH_Central` ahora deben tener también `Gestión Humana`.
   - Usuarios con `Selección` deben tener también `HR Selection`.
   - Usuarios con `Relaciones Laborales` deben tener también `HR Labor Relations`.

4. Ejecutar regresión de permisos Fase 8:

```bash
cd /workspace/frappe-bench && bench --site hubgh.test run-tests --app hubgh --module hubgh.tests.test_phase8_role_permissions
```

## Procedimiento en Producción

1. Respaldos previos:
   - Backup DB y archivos de sitio.

2. Ventana controlada y despliegue de código.

3. Ejecutar migración:

```bash
cd /workspace/frappe-bench && bench --site <site_prod> migrate
```

4. Ejecutar smoke checks de permisos:
   - App Shell: visibilidad de módulos por perfil (selección/RL/SST/operación).
   - Flujos críticos: selección (bandeja), RL (afiliación/contratación), operación (punto), SST.
   - Lectura documental por áreas (`Document Type`/`Person Document`).

5. Monitorear errores de permisos en logs durante primeras horas.

## Checklist post-migración

- [ ] No hay usuarios críticos sin acceso en módulos principales.
- [ ] Usuarios legacy siguen operando sin regresión funcional.
- [ ] Nuevos roles canónicos aparecen asignados según mapeo.
- [ ] Patch no genera duplicados en `Has Role` al re-ejecutar migrate.
- [ ] Pruebas Fase 8 en verde en staging.

## Rollback operativo (práctico)

Como la estrategia es aditiva (no destructiva):

1. Mantener código anterior de Fase 7 si se revierte release.
2. Si se requiere revertir asignaciones nuevas, eliminar de `Has Role` solo los roles canónicos agregados en la ventana de cambio, preservando roles legacy.
3. Re-ejecutar smoke checks de acceso.

> Nota: No se elimina el catálogo canónico; se recomienda rollback por release + limpieza dirigida de asignaciones si estrictamente necesario.

## Evidencia de validación técnica en esta fase

- Compilación de módulos Python modificados con `compileall` (sin errores).
- Suite de regresión Fase 8 en verde:
  - [`hubgh.tests.test_phase8_role_permissions`](../frappe-bench/apps/hubgh/hubgh/tests/test_phase8_role_permissions.py)
  - Resultado esperado: `Ran 12 tests ... OK`

