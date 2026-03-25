# HubGH Fase 4 — Runbook de unificación documental

## Objetivo

Consolidar el flujo documental en:

- `Document Type` (configuración de requisitos)
- `Person Document` (estado/archivo por persona)

El patch de esta fase elimina dependencia funcional activa del modelo legacy (`Documento Requerido` / `Candidato Documento`) en cálculos y procesos operativos, manteniendo migración segura de datos históricos.

## Patch de migración

- Patch: `hubgh.patches.document_phase4_unification`
- Registrado en: `hubgh/patches.txt`

### Qué hace

1. Si existe `Documento Requerido`, crea o completa filas faltantes en `Document Type`.
2. Recorre candidatos y migra filas de `Candidato Documento` hacia `Person Document`.
3. La migración es idempotente:
   - usa búsqueda por `Document Type.document_name` / `legacy_documento_requerido`
   - reutiliza registro existente vía `ensure_person_document`
   - solo completa campos vacíos en `Person Document` (no sobreescribe información más nueva)

## Ejecución

Desde `frappe-bench`:

```bash
bench --site hubgh.test migrate
```

## Validaciones post-migración

### 1) Validar fuente única en progreso documental

- Verificar que `get_candidate_progress` consulte solo `Document Type` y `Person Document`.
- Confirmar que no usa `Documento Requerido` ni `Candidato Documento` para cálculo actual.

### 2) Validar bug de denominador (Contrato)

Escenario esperado:

- si `Contrato` está en `Document Type` requerido para contratación,
- debe excluirse tanto del numerador como del denominador del progreso en candidato.

Resultado esperado:

- `required_total` no incluye `Contrato`.
- `%` y `is_complete` no se degradan por `Contrato`.

### 3) Validar APIs críticas

- Página/servicios de selección (`seleccion_documentos`) listan y suben desde `Person Document`.
- Flujo RL/Contratación consulta documentos de candidato desde `Person Document`.
- Estado documental de candidato se mantiene por cálculo unificado.

## Pruebas automáticas recomendadas

```bash
bench --site hubgh.test run-tests --app hubgh --module hubgh.tests.test_document_phase4_unification
```

Incluye cobertura de:

- exclusión de `Contrato` en denominador/numerador;
- uso exclusivo de modelo unificado en cálculo de progreso;
- merge no destructivo de datos legacy al migrar.

## Notas de alcance

- Esta fase **no** implementa hardening de onboarding (Fase 5).
- Esta fase **no** normaliza roles (Fase 8).
- Se mantiene compatibilidad transicional segura: legacy se migra/ignora explícitamente, sin dependencia funcional en lógica principal.

