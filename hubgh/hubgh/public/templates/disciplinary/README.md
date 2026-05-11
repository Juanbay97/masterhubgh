# Plantillas DOCX — Proceso Disciplinario

Esta carpeta contiene las 6 plantillas DOCX instrumentadas con variables Jinja2
para su uso con `python-docx-template` (docxtpl) en el módulo disciplinario de Hubgh.

## Plantillas requeridas

| Archivo | Descripcion | Origen |
|---|---|---|
| `citacion.docx` | Citacion para la Diligencia de Descargos | `1.CITACION PARA LA DILIGENCIA DE DESCARGOS 1 VEZ 2.0 CON EL NUEVO RIT.docx` |
| `diligencia_descargos.docx` | Acta de la sesion de descargos (Q&A) | `2.DILIGENCIA DE DESCARGOS 1 VEZ.docx` |
| `acta_cierre_sancion.docx` | Acta de cierre con sancion (Suspension) | `3.ACTA CIERRE DILIGENCIA DE DESCARGOS MODELO CON EL NUEVO RIT.docx` |
| `terminacion_justa_causa.docx` | Carta de terminacion justa causa | `4.TERMINACION JUSTA CAUSA CON EL NUEVO RIT.docx` |
| `acta_cierre_llamado.docx` | Acta de cierre - llamado de atencion | `ACTA DE CIERRE- LLAMADO DE ATENCION.docx` |
| `recordatorio_funciones.docx` | Recordatorio de funciones (memo triage) | `RECORDATORIO DE FUNCIONES (FORMATO).docx` |

## Instrumentacion (tarea humana, una sola vez)

Para cada plantilla:
1. Abrir el DOCX original en LibreOffice Writer o Microsoft Word.
2. Reemplazar los campos de texto libre por variables Jinja2 usando la sintaxis `{{ variable }}`.
3. Para listas (articulos RIT, preguntas y respuestas) usar los tags de bloque:
   - `{%p for articulo in articulos %}` ... `{%p endfor %}` (prefijo `p` = block paragraph)
4. Guardar en esta carpeta con el nombre exacto de la columna "Archivo" de la tabla anterior.
5. Hacer commit del archivo instrumentado.

## Variables por plantilla

### citacion.docx
```
{{ ciudad_emision }}
{{ fecha_citacion }}
{{ empleado.nombre }}, {{ empleado.cedula }}, {{ empleado.cargo }}, {{ empleado.pdv }}
{{ empresa.razon_social }}
{{ fecha_programada_descargos }}, {{ hora_descargos }}, {{ lugar }}
{%p for a in articulos %}Art. {{ a.numero }} — {{ a.texto }}{%p endfor %}
{{ hechos_narrados }}
{{ firmante.nombre }}, {{ firmante.cargo }}
```

### diligencia_descargos.docx
```
{{ fecha_sesion }}, {{ lugar_sesion }}
{{ empleado.* }}, {{ empresa.* }}
{{ fecha_ingreso_empleado }}, {{ cargo_actual }}, {{ jefe_inmediato }}
{{ hechos_leidos }}
{%p for qa in preguntas_respuestas %}P: {{ qa.pregunta }} R: {{ qa.respuesta }}{%p endfor %}
{{ firma_empleado }}, {{ testigo_1.nombre }}, {{ testigo_2.nombre }}
{{ firmante.* }}
```

### acta_cierre_sancion.docx
```
{{ empleado.* }}, {{ empresa.* }}, {{ fecha_emision }}
{{ fundamentos }}
{%p for a in articulos %}...{%p endfor %}
{{ sancion.tipo }}, {{ sancion.fecha_inicio }}, {{ sancion.fecha_fin }}, {{ sancion.dias }}
{{ firmante.* }}
```

### terminacion_justa_causa.docx
```
{{ empleado.* }}, {{ empresa.* }}, {{ fecha_emision }}
{{ fundamentos }}
{%p for a in articulos %}...{%p endfor %}
{{ fecha_ultimo_dia }}
{{ firmante.* }}
```

### acta_cierre_llamado.docx
```
{{ empleado.* }}, {{ empresa.* }}, {{ fecha_emision }}
{{ tipo_llamado }}, {{ fundamentos }}
{%p for a in articulos %}...{%p endfor %}
{{ firmante.* }}
```

### recordatorio_funciones.docx
```
{{ para }}, {{ de }}, {{ asunto }}, {{ fecha }}
{{ cuerpo }}
{{ empresa.* }}, {{ firmante.* }}
```

## Como verificar una plantilla instrumentada

Desde `bench console` en el docker:

```bash
docker exec -it docker-backend-1 bash
cd /home/frappe/frappe-bench
bench --site hubgh.local console
```

```python
# En el console Python
from hubgh.hubgh.disciplinary_workflow_service import render_document
import frappe

# Contexto de prueba minimo para citacion.docx
ctx = {
    "ciudad_emision": "Bogotá",
    "fecha_citacion": "2026-04-23",
    "empleado": {
        "nombre": "Juan Pérez",
        "cedula": "12345678",
        "cargo": "Auxiliar de cocina",
        "pdv": "PDV Chapinero",
    },
    "empresa": {"razon_social": "Home Burgers SAS"},
    "fecha_programada_descargos": "2026-04-30",
    "hora_descargos": "10:00",
    "lugar": "Oficina RRLL",
    "articulos": [
        {"numero": "42", "texto": "Llegada tarde reiterada"},
    ],
    "hechos_narrados": "El empleado llegó tarde en 5 ocasiones durante el mes.",
    "firmante": {"nombre": "Monica RRLL", "cargo": "Gestión Humana"},
}

# Renderizar — debe retornar bytes del DOCX o lanzar error descriptivo
try:
    content = render_document("citacion.docx", ctx)
    print(f"OK — DOCX generado, tamaño: {len(content)} bytes")
except FileNotFoundError as e:
    print(f"FALLO — plantilla no encontrada: {e}")
except Exception as e:
    print(f"FALLO — error en template: {e}")
```

Si el resultado es `OK — DOCX generado`, la plantilla está correctamente instrumentada.
Si es `FALLO — plantilla no encontrada`, el archivo DOCX no está en esta carpeta.
Si es `FALLO — error en template`, revisar que todas las variables Jinja esten presentes en el DOCX.

## Contextos de prueba por plantilla

### diligencia_descargos.docx

```python
ctx = {
    "fecha_sesion": "2026-04-30",
    "lugar_sesion": "Sala de reuniones",
    "empleado": {"nombre": "...", "cedula": "...", "cargo": "...", "pdv": "..."},
    "empresa": {"razon_social": "Home Burgers SAS"},
    "fecha_ingreso_empleado": "2023-01-15",
    "cargo_actual": "Auxiliar de cocina",
    "jefe_inmediato": "Gerente PDV",
    "hechos_leidos": "Descripcion de los hechos leida al empleado.",
    "preguntas_respuestas": [
        {"pregunta": "¿Reconoce los hechos?", "respuesta": "Sí, los reconozco."},
    ],
    "firma_empleado": True,
    "testigo_1": {"nombre": ""},
    "testigo_2": {"nombre": ""},
    "firmante": {"nombre": "Monica RRLL", "cargo": "Gestión Humana"},
}
content = render_document("diligencia_descargos.docx", ctx)
```

### acta_cierre_sancion.docx

```python
ctx = {
    "empleado": {"nombre": "...", "cedula": "...", "cargo": "...", "pdv": "..."},
    "empresa": {"razon_social": "Home Burgers SAS"},
    "fecha_emision": "2026-05-02",
    "fundamentos": "Incumplimiento reiterado del reglamento interno.",
    "articulos": [{"numero": "42", "texto": "Llegada tarde reiterada"}],
    "sancion": {
        "tipo": "Suspensión",
        "fecha_inicio": "2026-05-03",
        "fecha_fin": "2026-05-05",
        "dias": 3,
    },
    "firmante": {"nombre": "Monica RRLL", "cargo": "Gestión Humana"},
}
content = render_document("acta_cierre_sancion.docx", ctx)
```

### recordatorio_funciones.docx

```python
ctx = {
    "para": "Juan Pérez",
    "de": "Monica RRLL",
    "asunto": "Recordatorio de funciones",
    "fecha": "2026-04-23",
    "cuerpo": "Por medio del presente se le recuerda al trabajador sus funciones y obligaciones.",
    "empresa": {"razon_social": "Home Burgers SAS"},
    "firmante": {"nombre": "Monica RRLL", "cargo": "Gestión Humana"},
}
content = render_document("recordatorio_funciones.docx", ctx)
```

## PREREQUISITO para Phase 2

Las plantillas instrumentadas son BLOQUEANTES para las tareas T014+ (render_document).
Sin ellas, los tests de renderizado usan mocks y la generacion real de DOCX no funciona.
La instrumentacion es responsabilidad del equipo humano (Hubgh/RRLL).

## Estado actual de instrumentacion

| Plantilla | Estado | Responsable | Fecha |
|---|---|---|---|
| `citacion.docx` | PENDIENTE — archivo no instrumentado | RRLL/GH | — |
| `diligencia_descargos.docx` | PENDIENTE | RRLL/GH | — |
| `acta_cierre_sancion.docx` | PENDIENTE | RRLL/GH | — |
| `terminacion_justa_causa.docx` | PENDIENTE | RRLL/GH | — |
| `acta_cierre_llamado.docx` | PENDIENTE | RRLL/GH | — |
| `recordatorio_funciones.docx` | PENDIENTE | RRLL/GH | — |

Una vez instrumentadas, marcar como LISTO y hacer commit.
