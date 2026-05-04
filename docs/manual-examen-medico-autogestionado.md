# Manual de configuración — Examen médico autogestionado

Este manual te guía por todo lo que GH/SST necesita configurar antes de que el flujo de **agendamiento de examen médico autogestionado** funcione en producción. Está pensado para alguien con acceso de **System Manager** o **HR SST** en HubGH.

> **Tiempo estimado:** 30-45 minutos la primera vez, 5 minutos por cada IPS o sede nueva.

---

## 1. Activar el feature flag

El módulo solo se enciende si el site_config tiene la bandera. Se hace una sola vez por site.

```bash
bench --site <tu-site> set-config -p hubgh_agendamiento_autogestionado_enabled 1
bench --site <tu-site> clear-cache
```

Si la bandera no está, en la UI de Selección no aparece la opción "Autogestionado" en el dialog de "Enviar a examen", solo "Manual".

---

## 2. Configurar la cuenta de correo saliente

Sin una cuenta SMTP configurada, los correos se quedan en `Email Queue` con error *"Por favor, configure la cuenta de correo saliente por defecto"*.

1. Ir a `/app/email-account/new`.
2. Crear con:
   - **Email ID**: la dirección desde la que sale el correo (ej. `bienestar@homeburgers.com`)
   - **Enable Outgoing**: ✓
   - **Default Outgoing**: ✓
   - **SMTP Server**: para Microsoft 365 → `smtp-mail.outlook.com`
   - **SMTP Port**: `587`
   - **Use TLS**: ✓
   - **Use SSL**: ✗ (para puerto 587). Si usás puerto 465, al revés.
   - **Username + Password**: las credenciales de la cuenta.
3. Guardar — Frappe valida la conexión SMTP. Si tira `WRONG_VERSION_NUMBER`, el problema casi siempre es TLS/SSL invertido respecto al puerto.

> **Importante:** la dirección que pongas acá será el **remitente** de todos los correos del flujo. Si querés usar una cuenta corporativa distinta a `bienestar@homeburgers.com`, configurala acá y todo el flujo se adapta.

---

## 3. CC fijos del flujo

Todos los correos que el sistema manda (al candidato y a la IPS) llevan una copia oculta a tres direcciones internas. Hoy están **hardcodeadas** en el código:

```
SST@homeburgers.com
generalistagh1@homeburgers.com
generalistagh2@homeburgers.com
```

Archivo: `hubgh/hubgh/hubgh/examen_medico/email_service.py`, constante `CC_ALWAYS`.

Si tienen que cambiar, agregar o quitar uno, editar esa lista y desplegar. (Si esto se va a tocar seguido, vale la pena moverlo a un Single doctype "Configuración Examen Médico" — flagged como deuda pero hoy alcanza con la lista.)

---

## 4. Crear / configurar la IPS y sus sedes

Hoy hay **una sola IPS** representando a Zonamédica (que opera Bogotá directamente y subcontrata aliados en otras ciudades). El doctype permite N IPS pero la convención es modelar cada entidad jurídica como una IPS y cada punto físico como una **sede** dentro de ella.

### 4.1 Abrir la IPS

`/app/ips` → click en "Zonamedica MR SAS" (o crear nueva con el botón **+ New** si arrancan otra IPS).

Campos clave del header:

| Campo | Qué poner |
|---|---|
| **Nombre** | Razón social (ej. "Zonamedica MR SAS"). Es el `name` único. |
| **Ciudad** | Ciudad principal/legal. Sirve solo de referencia — el routing real se hace por sede. |
| **Dirección** | Dirección de la oficina principal (cuando una IPS no tiene sedes en la tabla, se usa este campo como fallback). |
| **Email Notificación** | Email default que se usa cuando una sede **no tiene** override propio. |
| **Teléfono** | Teléfono general. |
| **Activa** | ✓ — si está apagada, ningún candidato es ruteado a esta IPS. |
| **Requiere Orden de Servicio** | Solo lo usa el código si la IPS no tiene sedes. Dejarlo en `0` cuando se usa el modelo multi-sede. |
| **Template Orden de Servicio (FRSN-02)** | Subir el archivo xlsx base de la IPS. **Solo necesario si al menos una sede tiene `Requiere Orden de Servicio = ✓`.** Ver sección 5. |

### 4.2 Cargar las sedes

Sección **"Sedes"** del formulario. Cada fila representa un punto físico.

| Campo | Qué poner | Ejemplo |
|---|---|---|
| **Nombre de la Sede** | Cómo se llama internamente. Es lo que el candidato ve en el selector. | "Outlet Factory" |
| **Ciudad** | Link al doctype `Ciudad` — debe coincidir exacto con la que se setea en `Candidato.ciudad`. | "Bogotá" |
| **Dirección** | Dirección completa que verá el candidato. | "Av. Américas 62-84, locales 213-214-215" |
| **Teléfono** | Opcional. Aparece junto a la dirección en el portal. | "7514626 / 3168774072" |
| **Email de Notificación (override)** | Si está vacío, se usa el de la IPS. Si tiene valor, ese email recibe la notificación de citas para esta sede en lugar del de la IPS. | `recepcion@accionarsalud.com` |
| **Requiere Orden de Servicio (FRSN-02)** | ✓ → el correo a esta sede lleva el FRSN-02 xlsx adjunto. ✗ → correo simple sin adjunto. | Bogotá: ✗ · Aliadas: ✓ |
| **Activa** | ✓ — desmarcado oculta la sede del portal. | ✓ |

> **Regla de routing:**
> 1. El candidato tiene `ciudad` (ej. "Bogotá").
> 2. El sistema busca la **IPS activa** que tenga al menos **una sede activa** en esa ciudad.
> 3. En el portal, le muestra solo las sedes activas de **esa ciudad**.
> 4. Si hay **una sola sede** en la ciudad → el portal la muestra como dirección directa, sin selector.
> 5. Si hay **dos o más sedes** → aparece un selector de radio buttons al inicio.

### 4.3 Configurar Ciudades

Las sedes referencian el doctype **Ciudad**. Antes de cargar una sede de una ciudad nueva, asegurate de que la ciudad existe.

`/app/ciudad` → ver lista. Si falta, **+ New** y poná `nombre = "Manizales"`. El `name` (clave) suele ser el mismo nombre. Si va a usarse en SIESA, también poné `código siesa`.

> **Ojo con tildes:** el doctype Ciudad almacena los nombres con tilde (Bogotá, Medellín, Chía). El campo `Candidato.ciudad` actualmente es un Select hardcodeado **sin tildes** (Bogota, Medellin, Cartagena). El sistema **normaliza acentos** al hacer el match, así que "Bogota" del candidato matchea sede en "Bogotá". Pero si agregás una ciudad nueva, asegurate que la opción del Select de Candidato exista — sino el candidato no puede seleccionarla.

### 4.4 Configurar horarios

Sección **"Horarios"**. Los horarios son **a nivel IPS**, comunes a todas las sedes (limitación actual — si en el futuro cada sede maneja su propio horario, se evoluciona).

| Campo | Qué poner |
|---|---|
| **Día Semana** | L/M/X/J/V/S/D |
| **Hora Inicio** | "07:00" |
| **Hora Fin** | "11:00" — el último slot empieza a las 10:00 si el intervalo es de 60 minutos. |
| **Intervalo (min)** | "60" → un slot por hora. |
| **Cupos por Slot** | "50" — cada franja acepta hasta 50 candidatos en simultáneo. Default actualizado a 50; antes era 3. |

Cargar una fila por cada día laboral. Días no listados → no aparecen en el calendario.

### 4.5 Días bloqueados

Sección **"Días Bloqueados"** — para festivos no oficiales o cierres específicos. Los festivos colombianos oficiales se manejan automáticamente por la librería `holidays`.

### 4.6 Exámenes estándar por cargo

Sección **"Exámenes Estándar por Cargo"**. Es el catálogo que dice: *"para cargo X, la IPS hace los exámenes A, B, C"*.

Cada fila:

| Campo | Qué poner |
|---|---|
| **Cargo** | Link al doctype Cargo (autoname numérico — ej. "416" para Auxiliar de Cocina). |
| **Código Examen** | Tu código interno (ej. "EXM-INGRESO"). |
| **Nombre Examen** | Nombre humano (ej. "Examen médico con énfasis osteomuscular"). |
| **Celda Excel** | Solo si la IPS usa FRSN-02. Coordenada en el xlsx donde el sistema escribe "X". Ver sección 5. |

---

## 5. FRSN-02 (orden de servicio xlsx)

Solo aplica cuando alguna sede tiene `Requiere Orden de Servicio = ✓`.

### 5.1 Subir el template

En el formulario de la IPS, campo **"Template Orden de Servicio (FRSN-02)"**, subir el xlsx base. Frappe lo guarda en `/private/files/...`.

### 5.2 Verificar las celdas que rellena el sistema

Cuando el candidato agenda y la sede requiere orden, el sistema:

1. Abre el template en memoria.
2. Escribe los datos del candidato y de la cita en celdas fijas.
3. Adjunta el xlsx al correo de la sede.

**Celdas fijas (cableadas en el código)** — están alineadas con el FRSN-02 actual de Zonamédica. Si tu IPS usa otro formato y otras celdas, hay que ajustar el código.

| Dato | Celda |
|---|---|
| Fecha de solicitud | D10 |
| Nombre del trabajador | E13 |
| Cédula | E14 |
| Cargo | N13 |
| Ciudad | M14 |
| "X" en Tipo Ingreso | H16 |

Archivo: `hubgh/hubgh/hubgh/examen_medico/frsn02_generator.py`, constantes `DEFAULT_CELL_MAP` y `DEFAULT_TIPO_EXAMEN_INGRESO_CELL`.

### 5.3 Marcar exámenes en el FRSN-02

En la tabla **"Exámenes Estándar por Cargo"**, cada fila tiene un campo **"Celda Excel"**.

Cuando el cargo del candidato matchea la fila, el sistema escribe "X" en esa celda del xlsx.

Ejemplo (cargo Auxiliar de Cocina, FRSN-02 actual):

| Examen | Celda |
|---|---|
| Examen médico con énfasis osteomuscular | A27 |
| Optometría | A31 |
| KOH | A43 |
| Coprológico | A45 |
| Frotis de garganta | A47 |

Para mapear las celdas: abrí el FRSN-02 en Excel, ubicá la fila de cada examen y la columna donde va la marca (típicamente columna A en el formato Zonamédica).

### 5.4 Verificación rápida del template

Para chequear que el sistema rellena bien sin tener que correr el flujo completo:

1. Subí el template.
2. Configurá un cargo con sus celdas en la tabla de exámenes.
3. Andá a `/app/cita-examen-medico` y abrí una cita pendiente (o creá una manual con el botón de SST).
4. Disparar el envío de prueba — el correo a la IPS aparece en `/app/email-queue`. Descargá el adjunto xlsx y verificá que las celdas estén llenas.

---

## 6. Email Templates

Los textos de los correos viven como `Email Template` en `/app/email-template`. Hay 5 templates fijos que el flujo busca por nombre:

| Nombre | Cuándo se manda | Variables Jinja |
|---|---|---|
| `examen_medico_link_agendar` | Al activar Autogestionado, lleva el link al portal. | `candidato.nombre`, `portal_url`, `ips.nombre` |
| `examen_medico_confirmacion` | Al candidato cuando agenda su slot. | `candidato.nombre`, `cita.fecha_cita`, `cita.hora_cita`, `ips.nombre`, `ips.direccion`, `ips.sede`, `portal_url` |
| `examen_medico_ips_notificacion` | A la sede de la IPS post-agendamiento. | `candidato.nombre`, `candidato.cedula`, `candidato.cargo`, `candidato.ciudad`, `cita.fecha_cita`, `cita.hora_cita`, `cita.sede`, `cita.sede_direccion`, `examenes` (lista) |
| `examen_medico_aplazado` | Reservado para uso futuro — hoy no se manda automáticamente. | — |
| `examen_medico_recordatorio` | El día antes de la cita, vía cron 17:00. | `candidato.nombre`, `cita.fecha_cita`, `cita.hora_cita`, `ips.nombre` |

Para personalizar el HTML, abrí el template y editá el campo **Response/Message** (HTML libre con Jinja).

> Si necesitás logo + estilo corporativo, la mejor práctica es usar el campo `header` con el logo y el `response` con el cuerpo. Frappe respeta HTML estándar.

---

## 7. Configuración del candidato

Para que el flujo autogestionado funcione, el Candidato debe tener:

| Campo | Por qué |
|---|---|
| `email` | Es el destinatario del link. Si está vacío, no se manda el correo (la cita igual se crea). |
| `ciudad` | Determina qué sede de qué IPS se le ofrece. Sin ciudad, el sistema lanza "No hay IPS activa configurada". |
| `cargo` | Determina los exámenes a rellenar en el FRSN-02. Sin cargo, el dialog de "Enviar a examen" lo exige. |

---

## 8. Flujo de uso (referencia rápida para Selección y SST)

### Selección — enviar a examen
1. `/app/seleccion_documentos` → card del candidato → **Enviar a examen**.
2. Modo:
   - **Manual** → solo cambia el estado a "En examen médico". SST se encarga del resto. No se manda ningún correo.
   - **Autogestionado** → se crea la cita, se manda el correo con link al candidato.
3. Si elegís Autogestionado, aparece el campo **Fecha límite para agendar** (default hoy + 7 días). El portal solo le muestra slots hasta esa fecha (sin contar hoy).

### Candidato — agendar
1. Recibe correo con link tokenizado.
2. Abre el link → portal `/agendar_examen`.
3. Si su ciudad tiene varias sedes, elige una.
4. Elige día y hora dentro de la ventana.
5. Confirma.
6. Recibe correo de confirmación. La sede recibe correo con el FRSN-02 si aplica.

### SST — registrar resultado
`/app/cita-examen-medico/{cita}` → manualmente actualizar el estado:
- **Realizada** + `concepto_resultado` = Favorable / Desfavorable.
- **Aplazada** + motivo + instrucciones (queda registrado, NO se manda correo automático).
- **No Asistió** → la cita se cancela.

> **Importante:** ya **no hay reagendamiento automático**. Si SST marca Aplazada o No Asistió y hay que volver a agendar, GH vuelve a "Enviar a examen → Autogestionado" desde Selección. Eso crea una nueva cita y un nuevo link desde cero.

---

## 9. Recordatorios

Hay un cron diario a las 17:00 que manda el template `examen_medico_recordatorio` a las citas Agendadas para el día siguiente.

Configuración: `hubgh/hubgh/hubgh/hooks.py`, sección `scheduler_events.cron`, key `0 17 * * *`.

Para que el cron corra, el container `docker-backend-1` (o el supervisor de tu site) debe tener el scheduler activo. En dev: `bench --site <site> enable-scheduler`. En docker-compose prod debería estar prendido por default.

---

## 10. Troubleshooting

### "No hay IPS activa configurada para la ciudad 'X'"
- Verificar que la IPS tenga `Activa = ✓`.
- Verificar que la sede en esa ciudad tenga `Activa = ✓`.
- Verificar que el nombre de la Ciudad coincida (acentos no importan, el sistema normaliza).

### Los correos quedan en `Email Queue` con `Not Sent`
- Verificar `mute_emails` y `suspend_email_queue` en site_config — ambos deben estar en `0` o ausentes.
- Verificar que la cuenta de correo saliente esté con `Default Outgoing = ✓`.
- Mirar `/app/error-log` por errores SMTP (TLS/SSL invertido, credenciales malas).
- En dev: si `hubgh_dev_email_override` está seteado, **todos** los correos van a esa única dirección con prefijo `[DEV→...]`. Removerlo en producción.

### El FRSN-02 no se adjunta
- Verificar que la sede tenga `Requiere Orden de Servicio = ✓`.
- Verificar que la IPS tenga `Template Orden de Servicio` con archivo subido.
- Verificar que el cargo del candidato exista en la tabla "Exámenes Estándar por Cargo" con sus `Celda Excel` poblados.
- Mirar `/app/error-log` filtrando por "frsn02" o "send_exam_email".

### El link del correo no abre
- Verificar `host_name` en site_config. Debe coincidir con el dominio público (ej. `https://hubgh.tudominio.com:443` o sin puerto si es 80/443 default).
- El path canónico es `/agendar_examen` (con underscore), no `agendar-examen` con guion.

### El candidato dice "ya no me deja entrar al link"
- Los tokens duran **14 días** (configurable en `cita_service.create_cita_and_send_link`, parámetro `expiry_days`).
- Si la cita ya está Agendada el portal muestra el resumen ("Tu examen ya está agendado").
- Si caducó: GH vuelve a hacer "Enviar a examen" — eso genera un nuevo token.

---

## 11. Configuración mínima de site_config para producción

```json
{
  "hubgh_agendamiento_autogestionado_enabled": 1,
  "host_name": "https://tu-dominio-publico"
}
```

**No incluir** en producción:
- `hubgh_dev_email_override` — eso desvía todos los correos a una sola cuenta. Solo para dev/QA.
- `mute_emails` — solo para entornos donde no se quiere que ningún correo salga.
- `suspend_email_queue` — pausa la cola.

---

## 12. Checklist final antes de habilitar para producción

- [ ] `hubgh_agendamiento_autogestionado_enabled = 1` en site_config.
- [ ] Cuenta de correo saliente configurada con `default_outgoing = 1`.
- [ ] CC fijos validados (constante `CC_ALWAYS` en `email_service.py`).
- [ ] IPS activa cargada con sus sedes activas, una por cada ciudad operativa.
- [ ] Cada sede con email correcto (override si difiere del default IPS).
- [ ] Template FRSN-02 subido en las IPS que lo requieran.
- [ ] Tabla "Exámenes Estándar por Cargo" poblada para cada cargo operativo, con sus `Celda Excel`.
- [ ] Email Templates personalizados al copy corporativo.
- [ ] Scheduler activo (`bench enable-scheduler`).
- [ ] Smoke test: candidato en `En documentación` → "Enviar a examen" Autogestionado → recibe correo → agenda → confirma → la sede recibe notificación.

Cuando los 10 checks pasan, el flujo está listo.
