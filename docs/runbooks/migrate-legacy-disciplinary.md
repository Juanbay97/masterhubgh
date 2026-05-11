# Runbook: Migración de Casos Disciplinarios Legacy

**DO NOT EXECUTE** este runbook sin autorización explícita del equipo. Leer completo antes de ejecutar.

**Patch path**: `hubgh/hubgh/patches/v2_0/migrate_legacy_disciplinary_cases.py`  
**Registrar en**: `hubgh/patches.txt` (diferido — NO registrado aún)  
**Riesgo**: Medio — crea documentos nuevos, remapea estados en tabla existente  
**Reversible**: Sí (ver §6 Rollback)  
**Tiempo estimado**: 2–15 min dependiendo de volumen de casos  

---

## 1. Qué hace la migración

El nuevo modelo requiere que cada empleado involucrado en un caso tenga su propio
documento `Afectado Disciplinario`. Los casos legacy tienen el empleado directamente
en el `Caso Disciplinario` sin Afectado asociado.

La migración:
1. Detecta todos los `Caso Disciplinario` que NO tienen ningún `Afectado Disciplinario` asociado.
2. Para cada caso, crea 1 `Afectado Disciplinario` con los datos del caso (empleado, decision, fechas).
3. Remapea `Caso.estado` según la tabla de mapeo.
4. NO borra ni modifica campos del Caso original (solo el campo `estado`).
5. El campo `Caso.empleado` queda como campo informativo deprecated (readonly).

### Mapeo de estados

| Estado legacy (Caso) | Estado nuevo (Caso) | Estado Afectado creado |
|---|---|---|
| `Abierto` | `En Triage` | `En Triage` |
| `En Proceso` | `En Deliberación` | `En Deliberación` |
| `Cerrado` | `Cerrado` | `Cerrado` |
| Cualquier otro | `En Triage` | `En Triage` |

### Mapeo de campos

| Campo Caso (legacy) | Campo Afectado Disciplinario |
|---|---|
| `empleado` | `empleado` |
| `decision_final` (si Cerrado) | `decision_final_afectado` |
| `fecha_cierre` | `fecha_cierre_afectado` |
| `resumen_cierre` | `resumen_cierre_afectado` |
| `fecha_inicio_suspension` | `fecha_inicio_suspension` |
| `fecha_fin_suspension` | `fecha_fin_suspension` |
| `name` | `caso` (link field) |

---

## 2. Prerequisitos

- [ ] **Backup completo** antes de ejecutar (ver §3).
- [ ] **Dry-run** en sitio de desarrollo con copia de datos de producción.
- [ ] Verificar que `Afectado Disciplinario` DocType existe: `bench --site hubgh.local migrate` debe haber corrido.
- [ ] Autorización escrita del responsable del proceso (RRLL / Gerencia GH).
- [ ] Ventana de mantenimiento acordada (sin usuarios activos operando casos).
- [ ] El patch NO debe estar registrado en `patches.txt` hasta que el equipo lo autorice.

---

## 3. Backup previo

```bash
# Desde el host (fuera del docker)
docker exec docker-backend-1 bash -c "cd /home/frappe/frappe-bench && bench --site hubgh.local backup --with-files"

# Verificar que el backup se creó
docker exec docker-backend-1 ls -lh /home/frappe/frappe-bench/sites/hubgh.local/private/backups/ | tail -5

# Copiar backup al host antes de cualquier operación
# Ajustar path según timestamp del backup generado
docker cp docker-backend-1:/home/frappe/frappe-bench/sites/hubgh.local/private/backups/ ./backups_pre_migration/
```

---

## 4. Dry-run en desarrollo

```bash
# 1. Conectarse al bench console
docker exec -it docker-backend-1 bash
cd /home/frappe/frappe-bench
bench --site hubgh.local console

# 2. En el console Python — simular sin commit
import frappe

# Detectar casos candidatos
casos_sin_afectado = frappe.get_all(
    "Caso Disciplinario",
    filters=[["name", "not in", frappe.db.sql_list(
        "SELECT DISTINCT caso FROM `tabAfectado Disciplinario`"
    )]],
    fields=["name", "empleado", "estado"],
)
print(f"Casos candidatos a migrar: {len(casos_sin_afectado)}")
for c in casos_sin_afectado[:5]:
    print(f"  {c.name} | empleado={c.empleado} | estado={c.estado}")

# Salir sin commit
raise Exception("DRY RUN — no se ejecuta nada")
```

---

## 5. Ejecución

```bash
# Opción A: Via bench execute (recomendado)
docker exec -w /home/frappe/frappe-bench docker-backend-1 \
  bench --site hubgh.local execute hubgh.hubgh.patches.v2_0.migrate_legacy_disciplinary_cases.execute

# Opción B: Via bench console (si quiere inspección manual)
docker exec -it docker-backend-1 bash
cd /home/frappe/frappe-bench
bench --site hubgh.local console
# En Python:
# from hubgh.hubgh.patches.v2_0.migrate_legacy_disciplinary_cases import execute
# execute()
```

**Nota**: No registrar el patch en `patches.txt` si se ejecuta manualmente (Opción B),
ya que `bench migrate` lo marcaría como ejecutado en futuras migraciones.

---

## 6. Verificación post-migración

Ejecutar desde bench console inmediatamente después:

```python
import frappe

# 1. No deben quedar casos sin Afectado (excepto casos sin empleado)
casos_sin_afectado = frappe.db.sql("""
    SELECT c.name, c.empleado, c.estado
    FROM `tabCaso Disciplinario` c
    WHERE c.empleado IS NOT NULL
      AND c.empleado != ''
      AND NOT EXISTS (
          SELECT 1 FROM `tabAfectado Disciplinario` a WHERE a.caso = c.name
      )
""", as_dict=True)
print(f"Casos con empleado SIN Afectado post-migración: {len(casos_sin_afectado)}")
assert len(casos_sin_afectado) == 0, f"FALLO: {casos_sin_afectado}"

# 2. Verificar conteos
total_casos = frappe.db.count("Caso Disciplinario")
total_afectados = frappe.db.count("Afectado Disciplinario")
print(f"Total Casos: {total_casos}")
print(f"Total Afectados: {total_afectados}")
# total_afectados >= total_casos si todo migró (puede haber más afectados en casos multi-empleado)

# 3. Spot check — verificar un caso cerrado
casos_cerrados_sample = frappe.get_all(
    "Caso Disciplinario",
    filters={"estado": "Cerrado"},
    fields=["name"],
    limit=3,
)
for c in casos_cerrados_sample:
    afectados = frappe.get_all(
        "Afectado Disciplinario",
        filters={"caso": c.name},
        fields=["name", "estado", "decision_final_afectado"],
    )
    print(f"Caso {c.name}: {len(afectados)} afectado(s) — {[a.estado for a in afectados]}")

# 4. Verificar estados mapeados correctamente
estados_invalidos = frappe.db.sql("""
    SELECT estado, COUNT(*) as n
    FROM `tabCaso Disciplinario`
    WHERE estado NOT IN (
        'Solicitado', 'En Triage', 'Descargos Programados',
        'Citado', 'En Descargos', 'En Deliberación', 'Cerrado'
    )
    GROUP BY estado
""", as_dict=True)
print(f"Estados inválidos post-migración: {estados_invalidos}")
assert len(estados_invalidos) == 0, f"FALLO estados: {estados_invalidos}"

print("Verificación completa — migración OK")
```

---

## 7. Rollback

Si la migración produce resultados incorrectos:

```bash
# Opción A: Restaurar desde backup (destructivo — borra toda actividad post-backup)
docker exec -w /home/frappe/frappe-bench docker-backend-1 \
  bench --site hubgh.local restore /path/to/backup.sql.gz

# Opción B: Borrar solo los Afectados creados (si se pueden identificar por fecha)
# En bench console:
import frappe
from datetime import date

# Borrar afectados creados hoy (o en la ventana de migración)
afectados_migrados = frappe.get_all(
    "Afectado Disciplinario",
    filters=[["creation", ">=", "2026-XX-XX 00:00:00"]],  # fecha de migración
    fields=["name"],
)
for a in afectados_migrados:
    frappe.delete_doc("Afectado Disciplinario", a.name, force=True)

# Revertir estados de Caso (requiere tener el estado anterior — usar backup como referencia)
frappe.db.commit()
```

**Recomendación**: Usar siempre Opción A (restore desde backup) para garantizar consistencia total.

---

## 8. Tablas afectadas

| Tabla MariaDB | Operación | Número estimado de filas |
|---|---|---|
| `tabAfectado Disciplinario` | INSERT (1 por caso legacy) | = cantidad de casos con empleado |
| `tabCaso Disciplinario` | UPDATE campo `estado` | = cantidad de casos legacy |
| `tabDisciplinary Transition Log` | ninguna | — |

**Tiempo estimado por volumen**:
- <100 casos: ~30 segundos
- 100–1000 casos: ~2–5 minutos
- >1000 casos: ~10–20 minutos (considerar batch processing)

---

## 9. Preguntas frecuentes

**¿Qué pasa con casos que tienen `empleado = null`?**  
Se saltan con log de error. Requieren revisión manual.

**¿La migración es idempotente?**  
Sí — el filtro excluye casos que ya tienen Afectado. Si se corre dos veces, la segunda vez no hace nada.

**¿Afecta a los usuarios activos en ese momento?**  
No directamente, pero puede causar resultados inconsistentes en pantalla si alguien está operando un caso durante la migración. Ejecutar en ventana de mantenimiento.

**¿Hay que correr `bench migrate` después?**  
No es necesario si el patch se ejecutó manualmente. Si se registra en `patches.txt`, `bench migrate` lo marcará como ejecutado y no lo volverá a correr.
