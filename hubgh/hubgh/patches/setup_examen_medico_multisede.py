"""Idempotent post-migrate setup for the self-service medical exam flow.

Runs once via `bench migrate`. Safe to re-run — every step checks state
before mutating, so the patch is a no-op after the first successful run
or after the operator has manually configured something.

Performs:
  1. Ensure Module Profiles + Role Profiles exist (recovers from the
     `_ensure_module_profile is_new()` bug that left some sites with
     orphan User.module_profile links).
  2. Ensure Ciudades referenced by sedes exist (Bogotá, Chía, Medellín,
     Cartagena). Creates missing rows with `nombre` only — operator can
     fill `codigo_siesa` later.
  3. Bump `cupos_por_slot` to 50 on every IPS Horario row whose value
     is below 50 (the doctype default already moved to 50 for new rows).
  4. Seed the 7 default sedes on IPS "Zonamedica MR SAS" if it exists
     and currently has 0 sedes. Maps each sede to its city + the
     `requiere_orden_servicio` flag (Bogotá: 0, otras: 1). Skipped
     silently if the IPS does not exist (operator-managed).
  5. Activate the Frappe scheduler and unpause the email queue so cron
     and outbound mail run automatically without manual intervention.
"""

import frappe


SEDES_DEFAULT = [
	{
		"nombre_sede": "Outlet Factory",
		"ciudad": "Bogotá",
		"direccion": "Av. Américas No. 62-84, locales 213-214-215",
		"telefono": "7514626 / 3168774072 / 3138536350",
		"email_notificacion": "recepcion@zonamedicaips.com",
		"requiere_orden_servicio": 0,
		"activa": 1,
	},
	{
		"nombre_sede": "Autopista Norte",
		"ciudad": "Bogotá",
		"direccion": "Carrera 45 # 105-21",
		"telefono": "7514626 / 3168774072 / 3138536350",
		"email_notificacion": "recepcion@zonamedicaips.com",
		"requiere_orden_servicio": 0,
		"activa": 1,
	},
	{
		"nombre_sede": "Soledad",
		"ciudad": "Bogotá",
		"direccion": "Avenida Carrera 28 # 41-36",
		"telefono": "7514626 / 3168774072 / 3138536350",
		"email_notificacion": "recepcion@zonamedicaips.com",
		"requiere_orden_servicio": 0,
		"activa": 1,
	},
	{
		"nombre_sede": "Accionar Salud Chía",
		"ciudad": "Chía",
		"direccion": "Cra. 1B No. 18-40, Barrio San Francisco",
		"telefono": "",
		"email_notificacion": "",
		"requiere_orden_servicio": 1,
		"activa": 1,
	},
	{
		"nombre_sede": "Medellín San Ignacio",
		"ciudad": "Medellín",
		"direccion": "[POR DEFINIR — actualizar dirección]",
		"telefono": "",
		"email_notificacion": "",
		"requiere_orden_servicio": 1,
		"activa": 1,
	},
	{
		"nombre_sede": "Medellín Aguacatala / Poblado",
		"ciudad": "Medellín",
		"direccion": "Carrera 48B # 16 Sur - 38, Sector Aguacatala",
		"telefono": "",
		"email_notificacion": "",
		"requiere_orden_servicio": 1,
		"activa": 1,
	},
	{
		"nombre_sede": "GSL Ocupacional Cartagena",
		"ciudad": "Cartagena",
		"direccion": "Avenida Lacides Segovia # 15-114, Barrio Manga",
		"telefono": "",
		"email_notificacion": "",
		"requiere_orden_servicio": 1,
		"activa": 1,
	},
]


def execute():
	logger = frappe.logger("hubgh.patch.examen_medico_multisede")

	# 1. Module / Role profiles — recreate if missing.
	_ensure_profiles(logger)

	# 2. Ciudades referenciadas por sedes (+ Barranquilla por compatibilidad
	#    con valores legacy del form público).
	_ensure_ciudades(logger)

	# 3. Migrar valores legacy de Candidato.ciudad a los nombres canónicos
	#    con tilde (Bogota → Bogotá, Medellin → Medellín, Chia → Chía) ahora
	#    que el campo pasa de Select a Link → Ciudad.
	_canonicalize_candidato_ciudad(logger)

	# 4. Email Templates del flujo (5) — sync_fixtures es flaky en v15.
	_ensure_email_templates(logger)

	# 5. IPS Zonamedica MR SAS — la crea si el fixture nunca corrió.
	_ensure_ips_zonamedica(logger)

	# 6. Cupos a 50 en horarios existentes (después de 5 por si la creó).
	_bump_cupos_to_50(logger)

	# 7. Sedes default en Zonamedica MR SAS (asume IPS ya existe).
	_seed_sedes_zonamedica(logger)

	# 8. Exámenes default por tipo de cargo (Administrativo, principalmente)
	#    en IPS Zonamedica si no están todavía. Idempotente — chequea por
	#    código de examen.
	_ensure_admin_examenes_zonamedica(logger)

	# 9. Configuración Examen Médico Autogestionado — siembra inicial de
	#    emails CC si el Single está vacío (operador puede editar luego en UI).
	_ensure_configuracion_examen_medico(logger)

	# 10. Scheduler activo + cola sin pausa.
	_enable_scheduler_and_queue(logger)

	frappe.db.commit()


def _ensure_profiles(logger):
	try:
		from hubgh.access_profiles import ensure_roles_and_profiles

		ensure_roles_and_profiles()
		logger.info("examen_medico_multisede:profiles_ok")
	except Exception:
		logger.warning("examen_medico_multisede:profiles_skip", exc_info=True)


def _ensure_ciudades(logger):
	# Las 4 con sedes seed + Barranquilla porque el form público histórico
	# la ofrecía como opción. La incluimos para que el migrate de Candidatos
	# legacy con ciudad="Barranquilla" no quede roto al pasar el campo a Link.
	for nombre in ("Bogotá", "Chía", "Medellín", "Cartagena", "Barranquilla"):
		if frappe.db.exists("Ciudad", nombre):
			continue
		try:
			frappe.get_doc(
				{"doctype": "Ciudad", "nombre": nombre, "name": nombre}
			).insert(ignore_permissions=True, ignore_mandatory=True)
			logger.info(
				"examen_medico_multisede:ciudad_created", extra={"ciudad": nombre}
			)
		except Exception:
			logger.warning(
				"examen_medico_multisede:ciudad_skip",
				extra={"ciudad": nombre},
				exc_info=True,
			)


def _canonicalize_candidato_ciudad(logger):
	"""Normaliza Candidato.ciudad a los nombres con tilde del catálogo Ciudad.

	Antes el campo era un Select con valores sin tilde ('Bogota', 'Medellin',
	'Chia'). Ahora es Link → Ciudad y los registros del catálogo usan tilde.
	Updateamos en bloque para evitar LinkValidationError post-migrate.
	"""
	mapping = {
		"Bogota": "Bogotá",
		"Medellin": "Medellín",
		"Chia": "Chía",
	}
	for old, new in mapping.items():
		try:
			frappe.db.sql(
				"""
				UPDATE `tabCandidato`
				SET ciudad = %s
				WHERE ciudad = %s
				""",
				(new, old),
			)
			logger.info(
				"examen_medico_multisede:ciudad_renamed",
				extra={"from": old, "to": new},
			)
		except Exception:
			logger.warning(
				"examen_medico_multisede:ciudad_rename_skip",
				extra={"from": old, "to": new},
				exc_info=True,
			)


def _bump_cupos_to_50(logger):
	try:
		updated = frappe.db.sql(
			"""
			UPDATE `tabIPS Horario`
			SET cupos_por_slot = 50
			WHERE cupos_por_slot < 50
			"""
		)
		logger.info("examen_medico_multisede:cupos_bumped")
	except Exception:
		logger.warning("examen_medico_multisede:cupos_skip", exc_info=True)


_RECOMENDACIONES_OPERATIVO = """
<p style="margin-top:18px;"><strong>Recomendaciones importantes:</strong></p>
<ul>
  <li>Uso obligatorio de tapabocas.</li>
  <li>Llevar muestra coprológica.</li>
  <li>Presentar documento de identidad en la recepción.</li>
  <li>Informar que los exámenes fueron agendados por <strong>Comidas Varpel S.A.S.</strong></li>
  <li>Si usas gafas, debes llevarlas.</li>
  <li>No es necesario asistir en ayunas.</li>
  <li>Llevar uñas limpias, cortas y sin esmalte.</li>
  <li>Llegar con 15 minutos de anticipación.</li>
  <li>Algunos exámenes se realizan en dos tiempos. No te ausentes del lugar durante el proceso. Si eres llamado y no estás presente, se cancelará la valoración.</li>
</ul>
<p>Agradecemos tu puntualidad y compromiso.</p>
""".strip()

_RECOMENDACIONES_ADMINISTRATIVO = """
<p style="margin-top:18px;"><strong>Recomendaciones importantes:</strong></p>
<ul>
  <li>Uso obligatorio de tapabocas.</li>
  <li>Presentar documento de identidad en la recepción.</li>
  <li>Informar que los exámenes fueron agendados por <strong>Comidas Varpel S.A.S.</strong></li>
  <li>Si usas gafas, debes llevarlas.</li>
  <li>No es necesario asistir en ayunas.</li>
  <li>Llegar con 15 minutos de anticipación.</li>
  <li>Algunos exámenes se realizan en dos tiempos. No te ausentes del lugar durante el proceso. Si eres llamado y no estás presente, se cancelará la valoración.</li>
</ul>
<p>Agradecemos tu puntualidad y compromiso.</p>
""".strip()

_EXAMENES_LIST_BLOCK = """
{% if examenes %}
<p style="margin-top:18px;"><strong>Exámenes que se realizarán:</strong></p>
<ul>
  {% for examen in examenes %}<li>{{ examen.nombre_examen }}</li>{% endfor %}
</ul>
{% endif %}
""".strip()

_LINK_AGENDAR_HEAD = """
<p>Hola {{ candidato.nombre }},</p>
<p>Has sido seleccionado para continuar con tu proceso de vinculación. El siguiente paso es agendar tu <strong>examen médico de ingreso</strong>.</p>
<p>Hacé clic en el botón a continuación para elegir el día y la hora que mejor te queden dentro de los horarios disponibles.</p>
<p style="text-align:center;margin:24px 0;">
  <a href="{{ portal_url }}" style="background:#1d4ed8;color:#fff;padding:12px 28px;border-radius:8px;text-decoration:none;font-weight:600;display:inline-block;">Agendar mi examen médico</a>
</p>
""".strip()

_CONFIRMACION_HEAD = """
<p>Hola {{ candidato.nombre }},</p>
<p>Tu examen médico ha quedado <strong>confirmado</strong> con los siguientes datos:</p>
<ul>
  <li><strong>Fecha:</strong> {{ cita.fecha_cita }}</li>
  <li><strong>Hora:</strong> {{ cita.hora_cita }}</li>
  <li><strong>IPS:</strong> {{ ips.nombre }}</li>
  {% if ips.sede %}<li><strong>Sede:</strong> {{ ips.sede }}</li>{% endif %}
  <li><strong>Dirección:</strong> {{ ips.direccion }}</li>
  {% if ips.telefono %}<li><strong>Teléfono:</strong> {{ ips.telefono }}</li>{% endif %}
</ul>
""".strip()

_FOOTER = '<p><em>Equipo de Gestión Humana — Home Burgers</em></p>'

_DUDAS = '<p>Si tenés alguna duda, podés escribirnos a <a href="mailto:SST@homeburgers.com">SST@homeburgers.com</a>.</p>'


def _build_template(head, examenes_block, recomendaciones, dudas, footer):
	return "\n".join([head, examenes_block, recomendaciones, dudas, footer])


EMAIL_TEMPLATES = [
	# Legacy / fallback — operativo por default (más conservador).
	{
		"name": "examen_medico_link_agendar",
		"subject": "Agenda tu examen médico — Home Burgers",
		"response": _build_template(_LINK_AGENDAR_HEAD, _EXAMENES_LIST_BLOCK, _RECOMENDACIONES_OPERATIVO, _DUDAS, _FOOTER),
	},
	# Por tipo de cargo
	{
		"name": "examen_medico_link_agendar_operativo",
		"subject": "Agenda tu examen médico — Home Burgers",
		"response": _build_template(_LINK_AGENDAR_HEAD, _EXAMENES_LIST_BLOCK, _RECOMENDACIONES_OPERATIVO, _DUDAS, _FOOTER),
	},
	{
		"name": "examen_medico_link_agendar_administrativo",
		"subject": "Agenda tu examen médico — Home Burgers",
		"response": _build_template(_LINK_AGENDAR_HEAD, _EXAMENES_LIST_BLOCK, _RECOMENDACIONES_ADMINISTRATIVO, _DUDAS, _FOOTER),
	},
	# Confirmación post-agendamiento — incluye fecha/hora ya confirmada
	{
		"name": "examen_medico_confirmacion",
		"subject": "Confirmación de cita — examen médico",
		"response": _build_template(_CONFIRMACION_HEAD, _EXAMENES_LIST_BLOCK, _RECOMENDACIONES_OPERATIVO, _DUDAS, _FOOTER),
	},
	{
		"name": "examen_medico_confirmacion_operativo",
		"subject": "Confirmación de cita — examen médico",
		"response": _build_template(_CONFIRMACION_HEAD, _EXAMENES_LIST_BLOCK, _RECOMENDACIONES_OPERATIVO, _DUDAS, _FOOTER),
	},
	{
		"name": "examen_medico_confirmacion_administrativo",
		"subject": "Confirmación de cita — examen médico",
		"response": _build_template(_CONFIRMACION_HEAD, _EXAMENES_LIST_BLOCK, _RECOMENDACIONES_ADMINISTRATIVO, _DUDAS, _FOOTER),
	},
	# A la IPS — incluye datos del candidato y de la sede donde se prestará el servicio
	{
		"name": "examen_medico_ips_notificacion",
		"subject": "Programación de examen médico — {{ candidato.nombre }}",
		"response": "<p>Buenas tardes.</p>\n<p>Me ayudan por favor agendando a esta persona para el día <strong>{{ cita.fecha_cita }}</strong> a las <strong>{{ cita.hora_cita }}</strong>.</p>\n<p><strong>Datos del candidato:</strong></p>\n<ul>\n  <li><strong>CC:</strong> {{ candidato.cedula }}</li>\n  <li><strong>Nombre:</strong> {{ candidato.nombre }}</li>\n  <li><strong>Cargo:</strong> {{ candidato.cargo }}</li>\n  <li><strong>Ciudad de residencia:</strong> {{ candidato.ciudad }}</li>\n</ul>\n<p><strong>Sede donde se prestará el servicio:</strong></p>\n<ul>\n  <li><strong>Sede:</strong> {{ cita.sede or '—' }}</li>\n  <li><strong>Ciudad:</strong> {{ cita.sede_ciudad or candidato.ciudad or '—' }}</li>\n  <li><strong>Dirección:</strong> {{ cita.sede_direccion or '—' }}</li>\n</ul>\n<p><strong>Exámenes a realizar:</strong></p>\n<ul>\n  {% for examen in examenes %}<li>{{ examen.nombre_examen }}</li>{% endfor %}\n</ul>\n<p><strong>Empresa que remite:</strong> Comidas Varpel S.A.S.</p>\n<p>Muchas gracias.</p>\n<p><em>SST — Home Burgers<br>SST@homeburgers.com</em></p>",
	},
	{
		"name": "examen_medico_aplazado",
		"subject": "Tu examen médico fue aplazado",
		"response": "<p>Hola {{ candidato.nombre }},</p>\n<p>Tu examen médico del <strong>{{ cita.fecha_cita }}</strong> fue aplazado.</p>\n<p><strong>Motivo:</strong> {{ motivo_aplazamiento }}</p>\n{% if instrucciones_reagendamiento %}\n<p><strong>Instrucciones:</strong> {{ instrucciones_reagendamiento }}</p>\n{% endif %}\n<p>Si tenés preguntas, escribinos a <a href=\"mailto:SST@homeburgers.com\">SST@homeburgers.com</a>.</p>\n<p><em>Equipo de Gestión Humana — Home Burgers</em></p>",
	},
	{
		"name": "examen_medico_recordatorio",
		"subject": "Recordatorio — examen médico mañana",
		"response": "<p>Hola {{ candidato.nombre }},</p>\n<p>Te recordamos que <strong>mañana {{ cita.fecha_cita }}</strong> a las <strong>{{ cita.hora_cita }}</strong> tenés tu examen médico en:</p>\n<ul>\n  <li><strong>{{ ips.nombre }}</strong></li>\n  <li>{{ ips.direccion }}</li>\n</ul>\n<p>Por favor llegá puntual con tu documento de identidad.</p>\n<p><em>Equipo de Gestión Humana — Home Burgers</em></p>",
	},
]


def _ensure_email_templates(logger):
	"""Crea o actualiza los templates del flujo. Force-update porque las
	recomendaciones de copy cambian con frecuencia y es más útil para el
	operador tener las versiones canónicas que custom-edits perdidos."""
	for tpl in EMAIL_TEMPLATES:
		try:
			if frappe.db.exists("Email Template", tpl["name"]):
				doc = frappe.get_doc("Email Template", tpl["name"])
				doc.subject = tpl["subject"]
				doc.response = tpl["response"]
				doc.use_html = 1
				doc.save(ignore_permissions=True)
				logger.info(
					"examen_medico_multisede:email_template_updated",
					extra={"name": tpl["name"]},
				)
			else:
				frappe.get_doc({
					"doctype": "Email Template",
					"name": tpl["name"],
					"subject": tpl["subject"],
					"response": tpl["response"],
					"use_html": 1,
				}).insert(ignore_permissions=True, ignore_mandatory=True)
				logger.info(
					"examen_medico_multisede:email_template_created",
					extra={"name": tpl["name"]},
				)
		except Exception:
			logger.warning(
				"examen_medico_multisede:email_template_skip",
				extra={"name": tpl["name"]},
				exc_info=True,
			)


def _ensure_ips_zonamedica(logger):
	"""Crea la IPS Zonamedica MR SAS desde cero con horarios y exámenes
	estándar default si no existe (sync_fixtures de Frappe v15 puede fallar
	silencioso). Si ya existe, no la toca."""
	ips_name = "Zonamedica MR SAS"
	if frappe.db.exists("IPS", ips_name):
		return

	# Bogotá tiene que existir como Ciudad para el Link de la IPS — esto
	# se asegura en _ensure_ciudades, que corre antes en execute().
	if not frappe.db.exists("Ciudad", "Bogotá"):
		logger.warning(
			"examen_medico_multisede:zonamedica_skip_no_ciudad_bogota",
		)
		return

	try:
		ips = frappe.get_doc({
			"doctype": "IPS",
			"name": ips_name,
			"nombre": ips_name,
			"ciudad": "Bogotá",
			"direccion": "Calle 40 # 26 A 50 Barrio La Soledad",
			"email_notificacion": "recepcion@zonamedicaips.com",
			"telefono": "7514626 / 3168774072 / 3138536350",
			"activa": 1,
			"requiere_orden_servicio": 0,
			"horarios": [
				{"dia_semana": d, "hora_inicio": "07:00:00", "hora_fin": "11:00:00", "intervalo_minutos": 60, "cupos_por_slot": 50}
				for d in ("L", "M", "X", "J", "V")
			],
			"emails_por_ciudad": [
				{"ciudad": "Cartagena", "email": "ejecutivocuenta@zonamedicaips.com"},
				{"ciudad": "Medellín", "email": "ejecutivocuenta@zonamedicaips.com"},
			],
			"examenes_estandar": [
				# Cargo específico (Auxiliar de Cocina) — overrides para ese cargo.
				{"cargo": "416", "codigo_examen": "EXM-INGRESO", "nombre_examen": "Examen médico con énfasis osteomuscular", "celda_excel": ""},
				{"cargo": "416", "codigo_examen": "EXM-OPTO", "nombre_examen": "Optometría", "celda_excel": ""},
				{"cargo": "416", "codigo_examen": "EXM-KOH", "nombre_examen": "KOH", "celda_excel": ""},
				{"cargo": "416", "codigo_examen": "EXM-COPRO", "nombre_examen": "Coprológico", "celda_excel": ""},
				{"cargo": "416", "codigo_examen": "EXM-FROTIS-G", "nombre_examen": "Frotis de garganta", "celda_excel": ""},
				# Default Administrativos (aplica a todos los cargos con tipo_cargo=Administrativo).
				{"tipo_cargo_aplica": "Administrativo", "codigo_examen": "EXM-HC-INGRESO", "nombre_examen": "Historia clínica digital INGRESO", "celda_excel": ""},
				{"tipo_cargo_aplica": "Administrativo", "codigo_examen": "EXM-OPTO-ADM", "nombre_examen": "Consulta Optometría", "celda_excel": ""},
				{"tipo_cargo_aplica": "Administrativo", "codigo_examen": "EXM-OSTEO-ADM", "nombre_examen": "Osteomuscular", "celda_excel": ""},
			],
		})
		ips.insert(ignore_permissions=True, ignore_mandatory=True)
		logger.info("examen_medico_multisede:zonamedica_created")
	except Exception:
		logger.warning(
			"examen_medico_multisede:zonamedica_create_failed",
			exc_info=True,
		)


EXAMENES_DEFAULT_BY_TIPO = [
	# Administrativos — set reducido (Tecnico Mantenimiento, Gerente, etc.)
	{"tipo_cargo_aplica": "Administrativo", "codigo_examen": "EXM-HC-INGRESO", "nombre_examen": "Historia clínica digital INGRESO"},
	{"tipo_cargo_aplica": "Administrativo", "codigo_examen": "EXM-OPTO-ADM", "nombre_examen": "Consulta Optometría"},
	{"tipo_cargo_aplica": "Administrativo", "codigo_examen": "EXM-OSTEO-ADM", "nombre_examen": "Osteomuscular"},
	# Operativos default — para cargos operativos que no tienen override
	# específico (los con cargo='416' tienen su propio set y ese gana en path 1).
	{"tipo_cargo_aplica": "Operativo", "codigo_examen": "EXM-OP-OSTEO", "nombre_examen": "Examen médico con énfasis osteomuscular"},
	{"tipo_cargo_aplica": "Operativo", "codigo_examen": "EXM-OP-OPTO", "nombre_examen": "Optometría"},
	{"tipo_cargo_aplica": "Operativo", "codigo_examen": "EXM-OP-KOH", "nombre_examen": "KOH"},
	{"tipo_cargo_aplica": "Operativo", "codigo_examen": "EXM-OP-COPRO", "nombre_examen": "Coprológico"},
	{"tipo_cargo_aplica": "Operativo", "codigo_examen": "EXM-OP-FROTIS", "nombre_examen": "Frotis de garganta"},
]


def _ensure_admin_examenes_zonamedica(logger):
	"""Garantiza que IPS Zonamedica MR SAS tenga las filas de exámenes default
	por tipo de cargo (Administrativo + Operativo). Idempotente — si una fila
	con el mismo código_examen ya existe, no se duplica."""
	ips_name = "Zonamedica MR SAS"
	if not frappe.db.exists("IPS", ips_name):
		return
	try:
		ips = frappe.get_doc("IPS", ips_name)
		existing_codes = {
			(getattr(r, "codigo_examen", "") or "").strip()
			for r in (ips.examenes_estandar or [])
		}
		added = 0
		for ex in EXAMENES_DEFAULT_BY_TIPO:
			if ex["codigo_examen"] in existing_codes:
				continue
			ips.append("examenes_estandar", {
				"tipo_cargo_aplica": ex["tipo_cargo_aplica"],
				"codigo_examen": ex["codigo_examen"],
				"nombre_examen": ex["nombre_examen"],
				"celda_excel": "",
			})
			added += 1
		if added:
			ips.save(ignore_permissions=True)
			logger.info(
				"examen_medico_multisede:default_examenes_seeded",
				extra={"count": added},
			)
	except Exception:
		logger.warning(
			"examen_medico_multisede:default_examenes_skip",
			exc_info=True,
		)


def _seed_sedes_zonamedica(logger):
	ips_name = "Zonamedica MR SAS"
	if not frappe.db.exists("IPS", ips_name):
		logger.info(
			"examen_medico_multisede:zonamedica_absent",
			extra={"hint": "operator must create IPS Zonamedica MR SAS to use the default sedes"},
		)
		return

	doc = frappe.get_doc("IPS", ips_name)
	existing_sedes = doc.get("sedes") or []
	if existing_sedes:
		logger.info(
			"examen_medico_multisede:zonamedica_has_sedes",
			extra={"count": len(existing_sedes)},
		)
		return

	for sede in SEDES_DEFAULT:
		# Skip rows whose ciudad is missing — patch should not create stale links.
		if not frappe.db.exists("Ciudad", sede["ciudad"]):
			logger.warning(
				"examen_medico_multisede:sede_skip_missing_ciudad",
				extra={"sede": sede["nombre_sede"], "ciudad": sede["ciudad"]},
			)
			continue
		doc.append("sedes", sede)

	try:
		doc.save(ignore_permissions=True)
		logger.info(
			"examen_medico_multisede:sedes_seeded",
			extra={"count": len(doc.get("sedes") or [])},
		)
	except Exception:
		logger.warning("examen_medico_multisede:sedes_save_failed", exc_info=True)


CC_EMAILS_DEFAULT = [
	{"email": "SST@homeburgers.com", "nombre": "SST", "activo": 1},
	{"email": "generalistagh1@homeburgers.com", "nombre": "Generalista GH 1", "activo": 1},
	{"email": "generalistagh2@homeburgers.com", "nombre": "Generalista GH 2", "activo": 1},
]


def _ensure_configuracion_examen_medico(logger):
	"""Seed `Configuracion Examen Medico Autogestionado` Single con CC defaults.

	Idempotente:
	  - Si el doctype todavía no existe (primera migración antes de que
	    Frappe haya sincronizado el JSON), salimos silenciosamente.
	  - Si el Single ya tiene filas en `cc_emails`, no tocamos nada — el
	    operador ya configuró su lista vía UI.
	  - Si el Single existe pero está vacío, sembramos los 3 emails por
	    defecto (SST + 2 generalistas).
	"""
	try:
		if not frappe.db.table_exists("Configuracion Examen Medico Autogestionado"):
			logger.info("examen_medico_multisede:cc_config_table_missing_skip")
			return

		doc = frappe.get_single("Configuracion Examen Medico Autogestionado")

		existing = list(doc.get("cc_emails") or [])
		if existing:
			logger.info(
				"examen_medico_multisede:cc_config_present_skip count=%d",
				len(existing),
			)
			return

		for entry in CC_EMAILS_DEFAULT:
			doc.append("cc_emails", entry)

		doc.flags.ignore_permissions = True
		doc.save(ignore_permissions=True)
		logger.info(
			"examen_medico_multisede:cc_config_seeded count=%d",
			len(CC_EMAILS_DEFAULT),
		)
	except Exception:
		logger.warning(
			"examen_medico_multisede:cc_config_skip", exc_info=True
		)


def _enable_scheduler_and_queue(logger):
	try:
		# Pause/unpause flags live in DefaultValue; reading via get_default works
		# after migration. Setting both ensures cron + email queue run.
		frappe.db.set_default("pause_scheduler", 0)
		frappe.db.set_default("suspend_email_queue", 0)
		logger.info("examen_medico_multisede:scheduler_unpaused")
	except Exception:
		logger.warning(
			"examen_medico_multisede:scheduler_skip", exc_info=True
		)
