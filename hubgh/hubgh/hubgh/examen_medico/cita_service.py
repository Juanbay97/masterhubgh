# Copyright (c) 2026, Antigravity and contributors
# For license information, please see license.txt

"""
cita_service — Ciclo de vida de Cita Examen Medico.

Maneja creación, agendamiento y cierre de citas de examen médico:
  - create_cita_and_send_link: crea cita y envía link al candidato
  - book_slot: agenda un slot (con validación de cupos)
  - set_exam_outcome: registra resultado del examen (Realizada, Aplazada, No Asistió)
"""

from __future__ import annotations


def _normalize_city_key(value: str) -> str:
	"""Lowercase + strip accents so 'Bogotá' and 'Bogota' match."""
	import unicodedata

	if not value:
		return ""
	text = str(value).strip().lower()
	return "".join(ch for ch in unicodedata.normalize("NFKD", text) if not unicodedata.combining(ch))


def _resolve_cargo_label(codigo: str | None) -> str:
	"""Devuelve el nombre legible del Cargo a partir del código numérico.

	El doctype Cargo usa `autoname: format:{codigo}` — su `name` es el código
	numérico (ej. "416") y `nombre` la descripción ("AUXILIAR DE COCINA").
	En la cita guardamos el código (para SIESA) pero al mostrarlo en correos
	y en el FRSN-02 queremos la descripción para que sea legible.

	Si no se encuentra el Cargo o no tiene nombre, retorna el código tal cual
	(no rompe nada, peor caso muestra "416" como antes).
	"""
	import frappe

	if not codigo:
		return ""
	try:
		nombre = frappe.db.get_value("Cargo", codigo, "nombre")
		if nombre:
			return str(nombre).strip()
	except Exception:
		pass
	return str(codigo).strip()


def _resolve_cargo_tipo(codigo: str | None) -> str:
	"""Devuelve "Operativo" o "Administrativo" según el campo `tipo_cargo`
	del doctype Cargo. Default "Operativo" si no está configurado o el cargo
	no existe — más conservador (más recomendaciones)."""
	import frappe

	if not codigo:
		return "Operativo"
	try:
		tipo = frappe.db.get_value("Cargo", codigo, "tipo_cargo")
		if tipo and str(tipo).strip() in ("Operativo", "Administrativo"):
			return str(tipo).strip()
	except Exception:
		pass
	return "Operativo"


def _operativo_attachments() -> list[dict]:
	"""Carga las imágenes informativas que se adjuntan al correo del candidato
	cuando su `tipo_cargo` es "Operativo" — instrucciones de muestra coprológica
	y de uñas para el examen de KOH.

	Las imágenes viven dentro del app en `examen_medico/static/`. Si por algún
	motivo no se pueden leer (deploy parcial, permisos), se retorna lista vacía
	y el correo igual sale (las recomendaciones en texto del template ya
	cubren la información).
	"""
	import os
	import frappe

	specs = [
		("instrucciones_materia_fecal.jpg", "Instrucciones - Recoleccion muestra coprologica.jpg"),
		("instrucciones_examen_koh.jpg", "Instrucciones - Examen KOH (uñas).jpg"),
	]
	out = []
	try:
		base_dir = frappe.get_app_path("hubgh", "hubgh", "examen_medico", "static")
	except Exception:
		base_dir = None

	if not base_dir or not os.path.isdir(base_dir):
		return out

	for filename, send_name in specs:
		path = os.path.join(base_dir, filename)
		if not os.path.isfile(path):
			continue
		try:
			with open(path, "rb") as f:
				out.append({"fname": send_name, "fcontent": f.read()})
		except Exception:
			# Si una imagen falla, continuamos con la otra. El correo igual sale.
			continue
	return out


def _resolve_examenes_for_cargo(
	ips_doc,
	cargo_codigo: str | None,
	tipo_cargo: str | None = None,
) -> list[dict]:
	"""Devuelve la lista de exámenes a realizar, con cascada de fallbacks.

	Cascade:
	  1. Filas con `cargo == codigo` exacto (específico del cargo).
	  2. Si la 1ª queda vacía, filas con `cargo` vacío y `tipo_cargo_aplica`
	     coincide con el tipo del candidato (Operativo o Administrativo).
	  3. Si la 2ª queda vacía, filas con `cargo` y `tipo_cargo_aplica`
	     ambos vacíos (fallback global).
	  4. Si la 3ª también está vacía, lista vacía.

	Cada item retornado tiene `nombre_examen`.
	"""
	rows = []
	if isinstance(ips_doc, dict):
		rows = ips_doc.get("examenes_estandar") or []
	else:
		rows = getattr(ips_doc, "examenes_estandar", None) or []

	def _row_get(row, key):
		return row.get(key) if isinstance(row, dict) else getattr(row, key, None)

	codigo = (cargo_codigo or "").strip()
	tipo = (tipo_cargo or "").strip()

	# Path 1 — match exacto por cargo
	if codigo:
		matched = [
			{"nombre_examen": _row_get(r, "nombre_examen") or ""}
			for r in rows
			if (_row_get(r, "cargo") or "").strip() == codigo
		]
		if matched:
			return matched

	# Path 2 — match por tipo de cargo
	if tipo:
		matched = [
			{"nombre_examen": _row_get(r, "nombre_examen") or ""}
			for r in rows
			if not (_row_get(r, "cargo") or "").strip()
			and (_row_get(r, "tipo_cargo_aplica") or "").strip() == tipo
		]
		if matched:
			return matched

	# Path 3 — fallback global (cargo vacío + tipo vacío)
	default = [
		{"nombre_examen": _row_get(r, "nombre_examen") or ""}
		for r in rows
		if not (_row_get(r, "cargo") or "").strip()
		and not (_row_get(r, "tipo_cargo_aplica") or "").strip()
	]
	return default


def _candidato_full_name(candidato, fallback: str = "") -> str:
	"""Resolve a candidate's display name from `nombres`/`primer_apellido`/
	`segundo_apellido`. Falls back to `apellidos` then to the provided fallback
	(typically the document name, i.e. the cédula)."""
	nombres = getattr(candidato, "nombres", None) or ""
	primer = getattr(candidato, "primer_apellido", None) or ""
	segundo = getattr(candidato, "segundo_apellido", None) or ""
	parts = [str(p).strip() for p in (nombres, primer, segundo) if p and str(p).strip()]
	if parts:
		return " ".join(parts)
	apellidos = getattr(candidato, "apellidos", None) or ""
	if str(apellidos).strip():
		return f"{nombres} {apellidos}".strip() or fallback
	return fallback


def _resolve_active_ips_for_ciudad(candidato_ciudad: str) -> str | None:
	"""Find an active IPS for the candidate's ciudad, tolerating accents and case.

	Two lookup paths:
	  1. The IPS has a `sedes` child table — match if any active sede in that
	     IPS lives in the candidate's ciudad.
	  2. Legacy: the IPS itself has `ciudad` set (one IPS = one city).

	Candidato.ciudad is currently a plain Select (no accents) while the Ciudad
	doctype/fixture stores accented names (Bogotá, Medellín). Both sides are
	normalized before comparison.
	"""
	import frappe

	if not candidato_ciudad:
		return None
	target = _normalize_city_key(candidato_ciudad)

	# Path 1: scan IPS Sede rows — return the parent IPS if any active sede
	# lives in the target ciudad.
	sede_rows = frappe.get_all(
		"IPS Sede",
		filters={"activa": 1},
		fields=["parent", "ciudad"],
	)
	matching_parents = []
	for row in sede_rows:
		if _normalize_city_key(row.ciudad) == target:
			matching_parents.append(row.parent)
	for parent in matching_parents:
		if frappe.db.get_value("IPS", parent, "activa"):
			return parent

	# Path 2 (legacy): IPS.ciudad direct match.
	exact = frappe.db.get_value("IPS", {"ciudad": candidato_ciudad, "activa": 1}, "name")
	if exact:
		return exact
	for row in frappe.get_all("IPS", filters={"activa": 1}, fields=["name", "ciudad"]):
		if _normalize_city_key(row.ciudad) == target:
			return row.name
	return None


def _email_por_ciudad(ips_doc, ciudad: str) -> str:
	"""Lookup email override en `IPS.emails_por_ciudad` para `ciudad`.

	Match accent/case-tolerant para evitar que "Medellín" en la config no
	matchee con "Medellin" guardado en el Candidato.
	"""
	if not ciudad:
		return ""
	target = _normalize_city_key(ciudad)
	rows = (
		ips_doc.get("emails_por_ciudad")
		if isinstance(ips_doc, dict)
		else getattr(ips_doc, "emails_por_ciudad", None)
	) or []
	for row in rows:
		row_ciudad = row.get("ciudad") if isinstance(row, dict) else getattr(row, "ciudad", None)
		row_email = row.get("email") if isinstance(row, dict) else getattr(row, "email", None)
		if _normalize_city_key(row_ciudad or "") == target and row_email:
			return str(row_email).strip()
	return ""


def _get_sedes_for_ciudad(ips_doc, candidato_ciudad: str) -> list[dict]:
	"""Return active sedes of `ips_doc` whose ciudad matches `candidato_ciudad`
	(accent/case-tolerant). Each entry is a dict with the sede fields plus the
	resolved `email` and `requiere_orden_servicio` (with IPS-level fallbacks).

	Email cascade per sede:
	  1. `sede.email_notificacion` (más específico)
	  2. `IPS.emails_por_ciudad` matched por ciudad de la sede
	  3. `IPS.email_notificacion` (legacy fallback)

	If the IPS has no sedes child rows at all, returns a single synthetic
	entry built from the legacy IPS-level fields so existing single-sede IPS
	keep working.
	"""
	target = _normalize_city_key(candidato_ciudad)
	sedes_raw = ips_doc.get("sedes") or []

	def _row_get(row, key, default=None):
		return row.get(key, default) if isinstance(row, dict) else getattr(row, key, default)

	ips_email = ips_doc.get("email_notificacion") if isinstance(ips_doc, dict) else getattr(ips_doc, "email_notificacion", None)
	ips_requiere = (
		ips_doc.get("requiere_orden_servicio")
		if isinstance(ips_doc, dict)
		else getattr(ips_doc, "requiere_orden_servicio", 0)
	)
	ips_direccion = ips_doc.get("direccion") if isinstance(ips_doc, dict) else getattr(ips_doc, "direccion", "")
	ips_telefono = ips_doc.get("telefono") if isinstance(ips_doc, dict) else getattr(ips_doc, "telefono", "")
	ips_ciudad = ips_doc.get("ciudad") if isinstance(ips_doc, dict) else getattr(ips_doc, "ciudad", "")

	if not sedes_raw:
		# Legacy: no sedes table. Treat the IPS as a single sede.
		return [
			{
				"nombre_sede": "Sede principal",
				"ciudad": ips_ciudad or "",
				"direccion": ips_direccion or "",
				"telefono": ips_telefono or "",
				"email": (_email_por_ciudad(ips_doc, ips_ciudad) or ips_email or ""),
				"requiere_orden_servicio": int(ips_requiere or 0),
			}
		]

	out = []
	for row in sedes_raw:
		if not int(_row_get(row, "activa", 0) or 0):
			continue
		sede_ciudad = _row_get(row, "ciudad", "") or ""
		if _normalize_city_key(sede_ciudad) != target:
			continue
		out.append(
			{
				"nombre_sede": _row_get(row, "nombre_sede", "") or "",
				"ciudad": sede_ciudad,
				"direccion": _row_get(row, "direccion", "") or "",
				"telefono": _row_get(row, "telefono", "") or "",
				"email": (
					_row_get(row, "email_notificacion", "")
					or _email_por_ciudad(ips_doc, sede_ciudad)
					or ips_email
					or ""
				),
				"requiere_orden_servicio": int(_row_get(row, "requiere_orden_servicio", 0) or 0),
			}
		)
	return out


def create_cita_manual(
	candidato_name: str,
	cargo: str,
	sede: str | None = None,
	fecha_cita: str | None = None,
	hora_cita: str | None = None,
	cita_anterior: str | None = None,
) -> str:
	"""Crea una Cita Examen Medico para flujo manual (agendada por GH).

	Por defecto la cita queda en estado "Pendiente Agendamiento" con
	fecha/hora/sede vacías — Selección Documentos sólo dispara el envío,
	GH/SST completa los datos desde la bandeja de seguimiento.

	Si los 3 datos vienen, la cita se crea ya en estado "Agendada".

	Resuelve la IPS por ciudad del candidato. Captura cargo en
	cargo_al_enviar.

	Args:
		candidato_name: Nombre del Candidato.
		cargo: Cargo del candidato.
		sede: Sede de IPS (opcional). Persistida via db.set_value
			(bypass de read_only).
		fecha_cita: Fecha YYYY-MM-DD (opcional).
		hora_cita: Hora HH:MM o HH:MM:SS (opcional).

	Returns:
		Nombre de la cita creada.

	Raises:
		frappe.ValidationError: Si no hay IPS activa para la ciudad del
		candidato.
	"""
	import frappe

	candidato = frappe.get_doc("Candidato", candidato_name)
	candidato_ciudad = getattr(candidato, "ciudad", None) or ""
	ips_name = _resolve_active_ips_for_ciudad(candidato_ciudad)
	if not ips_name:
		frappe.throw(
			f"No hay IPS activa configurada para la ciudad '{candidato_ciudad}'. "
			"Contacte al administrador del sistema para configurar una IPS.",
			frappe.ValidationError,
		)

	tiene_agendamiento = bool(fecha_cita and hora_cita)

	cita = frappe.new_doc("Cita Examen Medico")
	cita.candidato = candidato_name
	cita.ips = ips_name
	cita.estado = "Agendada" if tiene_agendamiento else "Pendiente Agendamiento"
	if tiene_agendamiento:
		cita.fecha_agendamiento = frappe.utils.now_datetime()
	cita.cargo_al_enviar = cargo or ""
	if fecha_cita:
		cita.fecha_cita = fecha_cita
	if hora_cita:
		cita.hora_cita = hora_cita
	if cita_anterior:
		cita.cita_anterior = cita_anterior
	try:
		cita.insert(ignore_permissions=True)
	except TypeError:
		cita.insert()

	# sede_seleccionada es read_only=1 en el DocType. Bypass via db.set_value.
	if sede:
		frappe.db.set_value(
			"Cita Examen Medico",
			cita.name,
			"sede_seleccionada",
			sede,
			update_modified=False,
		)

	return cita.name


def create_cita_and_send_link(
	candidato_name: str,
	cargo: str | None = None,
	fecha_limite: str | None = None,
	cita_anterior: str | None = None,
) -> str:
	"""
	Crea una Cita Examen Medico y envía el link de agendamiento al candidato.

	Resuelve la IPS por ciudad del candidato. Captura cargo_postulado en
	cargo_al_enviar. Genera token y envía email con link.

	Args:
		candidato_name: Nombre del documento Candidato.
		cargo: Cargo para capturar en cargo_al_enviar. Si no se pasa,
		       usa candidato.cargo_postulado.
		fecha_limite: Fecha tope (YYYY-MM-DD) para que el candidato agende.
		              Si se pasa, se persiste en la cita y el portal filtra
		              los slots para no ofrecer fechas posteriores.

	Returns:
		Nombre del documento Cita Examen Medico creado.

	Raises:
		frappe.ValidationError: Si no hay IPS activa para la ciudad del candidato.
	"""
	import frappe
	from hubgh.hubgh.examen_medico.token_manager import create_token
	from hubgh.hubgh.examen_medico.email_service import send_exam_email

	candidato = frappe.get_doc("Candidato", candidato_name)

	# Resolve cargo
	cargo_al_enviar = cargo or getattr(candidato, "cargo_postulado", None) or ""

	# Auto-assign IPS by candidato's ciudad (accent-tolerant)
	candidato_ciudad = getattr(candidato, "ciudad", None) or ""
	ips_name = _resolve_active_ips_for_ciudad(candidato_ciudad)
	if not ips_name:
		frappe.throw(
			f"No hay IPS activa configurada para la ciudad '{candidato_ciudad}'. "
			"Contacte al administrador del sistema para configurar una IPS.",
			frappe.ValidationError,
		)

	# Create Cita document
	cita = frappe.new_doc("Cita Examen Medico")
	cita.candidato = candidato_name
	cita.ips = ips_name
	cita.estado = "Pendiente Agendamiento"
	cita.cargo_al_enviar = cargo_al_enviar
	if fecha_limite:
		cita.fecha_limite_agendamiento = fecha_limite
	if cita_anterior:
		cita.cita_anterior = cita_anterior
	# Use insert() without kwargs — tests may mock insert as a simple callable
	try:
		cita.insert(ignore_permissions=True)
	except TypeError:
		cita.insert()

	# Generate token
	token = create_token(cita.name, expiry_days=14)

	# Build token URL
	try:
		site_url = frappe.utils.get_url()
	except Exception:
		site_url = ""
	portal_url = f"{site_url}/agendar_examen?token={token}"

	# Send link email (best-effort — do not fail the whole operation on email error)
	candidato_email = getattr(candidato, "email", None) or ""
	if candidato_email:
		try:
			# Tipo de cargo decide qué template (operativo/admin) usar y qué
			# recomendaciones se incluyen.
			tipo_cargo = _resolve_cargo_tipo(cargo_al_enviar)
			template_name = (
				"examen_medico_link_agendar_administrativo"
				if tipo_cargo == "Administrativo"
				else "examen_medico_link_agendar_operativo"
			)
			# Fallback al template legacy si por algún motivo el específico no existe.
			if not frappe.db.exists("Email Template", template_name):
				template_name = "examen_medico_link_agendar"

			# Lista de exámenes que se realizarán — incluye fallback a cargo vacío.
			ips_doc_for_examenes = frappe.get_doc("IPS", ips_name)
			examenes = _resolve_examenes_for_cargo(ips_doc_for_examenes, cargo_al_enviar, tipo_cargo=tipo_cargo)

			# Las imágenes con instrucciones de muestras (coprológica + KOH)
			# NO se adjuntan acá — irían recargadas y antes de que el candidato
			# tenga fecha confirmada. Se mandan solo en el correo de confirmación
			# post-agendamiento.
			send_exam_email(
				template_name=template_name,
				recipients=[candidato_email],
				context={
					"candidato": {"nombre": _candidato_full_name(candidato, fallback=candidato_name)},
					"portal_url": portal_url,
					"ips": {"nombre": ips_name},
					"examenes": examenes,
				},
			)
		except Exception:
			pass

	return cita.name


def book_slot(token: str, fecha: str, hora: str) -> dict:
	"""
	Agenda un slot para una Cita identificada por token.

	Valida el token, verifica cupos disponibles, actualiza la Cita a Agendada
	y marca el token como usado.

	Args:
		token: Token hex de 32 caracteres del link de agendamiento.
		fecha: Fecha del slot en formato "YYYY-MM-DD".
		hora: Hora del slot en formato "HH:MM" o "HH:MM:SS".

	Returns:
		Dict con {status, cita_name, fecha, hora}.

	Raises:
		frappe.ValidationError: Si token inválido/expirado/usado.
		frappe.ValidationError: Si no hay cupos disponibles en el slot.
	"""
	import frappe
	from hubgh.hubgh.examen_medico.token_manager import validate_token, consume_token
	from hubgh.hubgh.examen_medico.email_service import send_exam_email, get_ips_email

	cita_data = validate_token(token)
	cita_name = cita_data["name"]
	ips_name = cita_data.get("ips")

	# Check cupos — count existing Agendada|Realizada for this slot
	booked = frappe.db.get_value(
		"Cita Examen Medico",
		{"ips": ips_name, "fecha_cita": fecha, "hora_cita": hora, "estado": ["in", ["Agendada", "Realizada"]]},
		"count(name)",
	) or 0

	# Get cupos_por_slot from cita_data or default to 3
	cupos_por_slot = cita_data.get("cupos_por_slot") or 3

	if int(booked) >= int(cupos_por_slot):
		frappe.throw("Cupo ocupado para el slot seleccionado.", frappe.ValidationError)

	# Normalize hora
	if hora and len(hora.split(":")) == 2:
		hora = hora + ":00"

	# Update cita
	frappe.db.set_value(
		"Cita Examen Medico",
		cita_name,
		{
			"estado": "Agendada",
			"fecha_cita": fecha,
			"hora_cita": hora,
		},
	)

	# Mark token as used
	consume_token(cita_name)

	return {"status": "ok", "cita_name": cita_name, "fecha": fecha, "hora": hora}


def set_exam_outcome(
	cita_name: str,
	estado: str,
	concepto: str | None = None,
	motivo: str | None = None,
	instrucciones: str | None = None,
	action: str | None = None,
) -> None:
	"""
	Registra el resultado del examen médico y cierra el ciclo del candidato.

	Args:
		cita_name: Nombre del documento Cita Examen Medico.
		estado: Estado final — "Realizada", "Aplazada", "No Asistió", "Cancelada".
		concepto: Concepto médico para Realizada — "Favorable", "Desfavorable" o "Aplazado".
		motivo: Motivo (para Aplazada / No Asistió / Cancelada / Desfavorable).
		instrucciones: Instrucciones de reagendamiento (para Aplazada).
		action: Parámetro de compatibilidad para callers legacy (sst_bandeja).
		        Ya no tiene efecto en la lógica — la acción la determina `estado`.

	Efectos sobre el Candidato:
	  - Realizada + Favorable → concepto_medico="Favorable". estado_proceso no se mueve
	    (Selección Documentos decide el avance a RRLL respetando el gate SAGRILAFT).
	  - Realizada + Desfavorable → concepto_medico="Desfavorable", estado_proceso=Rechazado,
	    motivo_rechazo poblado.
	  - Realizada + Aplazado → la cita se persiste como Aplazada (no Realizada) para
	    seguir visible en bandeja. concepto_medico="Aplazado". estado_proceso permanece.
	  - Cancelada → estado_proceso=En documentación, concepto_medico vacío,
	    fecha_envio_examen_medico vacío. El candidato vuelve a la bandeja de Selección.
	  - Aplazada / No Asistió → la cita queda visible en bandeja para reagendar.
	    El candidato permanece en examen médico.

	Nota: "No Asistió" persiste el estado literal "No Asistió". NO se mapea a "Cancelada".
	"""
	import frappe
	from hubgh.hubgh.candidate_states import STATE_DOCUMENTACION, STATE_RECHAZADO

	cita = frappe.get_doc("Cita Examen Medico", cita_name)

	if estado == "Realizada":
		# Concepto=Aplazado mapea a estado Aplazada (cita sigue abierta para reagendar).
		if concepto == "Aplazado":
			frappe.db.set_value(
				"Cita Examen Medico",
				cita_name,
				{
					"estado": "Aplazada",
					"motivo_aplazamiento": motivo or "",
					"instrucciones_reagendamiento": instrucciones or "",
				},
			)
			# concepto_medico se actualiza para trazabilidad — estado_proceso permanece.
			frappe.db.set_value("Candidato", cita.candidato, "concepto_medico", "Aplazado")
			return

		frappe.db.set_value("Cita Examen Medico", cita_name, "estado", "Realizada")
		if concepto in ("Favorable", "Desfavorable"):
			frappe.db.set_value("Cita Examen Medico", cita_name, "concepto_resultado", concepto)

		if concepto == "Favorable":
			# Solo concepto_medico — el avance a RRLL queda en manos de Selección
			# por el gate SAGRILAFT.
			frappe.db.set_value("Candidato", cita.candidato, "concepto_medico", "Favorable")

		elif concepto == "Desfavorable":
			# Auto-rechazo: cierra el ciclo del candidato sin requerir paso por Selección.
			frappe.db.set_value(
				"Candidato",
				cita.candidato,
				{
					"concepto_medico": "Desfavorable",
					"estado_proceso": STATE_RECHAZADO,
					"motivo_rechazo": (motivo or "").strip() or "Examen médico Desfavorable",
				},
			)

	elif estado == "Aplazada":
		# Marca la cita como Aplazada y registra motivo/instrucciones. La cita sigue
		# visible en bandeja para que SST/GH la reagende vía endpoint `reagendar_cita`.
		frappe.db.set_value(
			"Cita Examen Medico",
			cita_name,
			{
				"estado": "Aplazada",
				"motivo_aplazamiento": motivo or "",
				"instrucciones_reagendamiento": instrucciones or "",
			},
		)

	elif estado == "No Asistió":
		# Persiste literal "No Asistió" — no mapear a "Cancelada".
		# El parámetro `action` se mantiene en la firma por compatibilidad hacia atrás
		# (callers en sst_bandeja lo pasan) pero ya no dispara creación automática de cita.
		vals = {"estado": "No Asistió"}
		if motivo:
			vals["motivo_aplazamiento"] = motivo
		frappe.db.set_value("Cita Examen Medico", cita_name, vals)

	elif estado == "Cancelada":
		# Cancelación explícita: cita Cancelada + candidato vuelve a Selección Documentos.
		frappe.db.set_value(
			"Cita Examen Medico",
			cita_name,
			{
				"estado": "Cancelada",
				"motivo_aplazamiento": motivo or "",
			},
		)
		frappe.db.set_value(
			"Candidato",
			cita.candidato,
			{
				"estado_proceso": STATE_DOCUMENTACION,
				"concepto_medico": "Pendiente",
				"fecha_envio_examen_medico": None,
			},
		)


def reagendar_cita(cita_name: str) -> str:
	"""Reagenda una cita Aplazada/No Asistió creando una nueva ligada por `cita_anterior`.

	Reproduce el flujo según `Candidato.modo_agendamiento_examen`:
	  - Manual → `create_cita_manual` (queda en "Pendiente Agendamiento"; GH la agenda
	    desde la bandeja).
	  - Autogestionado → `create_cita_and_send_link` (genera token nuevo y envía link
	    al candidato).

	La cita previa NO se modifica — queda con su estado (Aplazada / No Asistió) para
	trazabilidad. Selección puede ver el encadenamiento siguiendo `cita_anterior` hacia
	atrás.

	Args:
		cita_name: Nombre de la cita previa a reagendar.

	Returns:
		Nombre de la nueva cita creada.
	"""
	import frappe

	cita_prev = frappe.get_doc("Cita Examen Medico", cita_name)
	candidato_name = cita_prev.candidato
	cargo = cita_prev.cargo_al_enviar or ""

	modo = frappe.db.get_value("Candidato", candidato_name, "modo_agendamiento_examen") or "Manual"

	if modo == "Autogestionado":
		return create_cita_and_send_link(
			candidato_name=candidato_name,
			cargo=cargo,
			cita_anterior=cita_name,
		)

	return create_cita_manual(
		candidato_name=candidato_name,
		cargo=cargo,
		cita_anterior=cita_name,
	)


def notify_ips_cita_agendada(cita_name: str) -> bool:
	"""Envía el correo de notificación a la IPS con los datos de la cita.

	Resuelve sede, exámenes y orden de servicio (FRSN-02 si aplica). Best-effort:
	no relanza excepciones — en caso de fallo loguea via frappe.log_error y retorna False.

	Side effects en éxito:
	  - `enviado_ips = 1`
	  - `fecha_envio = now_datetime()`

	Args:
		cita_name: Nombre del Cita Examen Medico.

	Returns:
		True si se envió el correo, False si no hubo destinatario o falló.
	"""
	import frappe

	from hubgh.hubgh.examen_medico.email_service import send_exam_email
	from hubgh.hubgh.examen_medico.frsn02_generator import generate_frsn02

	try:
		cita = frappe.get_doc("Cita Examen Medico", cita_name)
	except Exception:
		return False

	ips_name = cita.ips
	if not ips_name:
		return False

	try:
		ips_doc = frappe.get_doc("IPS", ips_name)
	except Exception:
		return False

	candidato_name = cita.candidato
	try:
		candidato = frappe.get_doc("Candidato", candidato_name)
	except Exception:
		return False

	candidato_nombre = " ".join(filter(None, [
		getattr(candidato, "nombres", None),
		getattr(candidato, "primer_apellido", None),
		getattr(candidato, "segundo_apellido", None),
	])) or candidato_name
	candidato_ciudad = getattr(candidato, "ciudad", "") or ""

	# Resolver sede elegida en la cita; fallback a sintética con datos IPS
	sedes_visibles = _get_sedes_for_ciudad(ips_doc.as_dict(), candidato_ciudad)
	sede_nombre = cita.sede_seleccionada or ""
	sede_resuelta = None
	for s in sedes_visibles or []:
		if sede_nombre and s.get("nombre_sede") == sede_nombre:
			sede_resuelta = s
			break
	if not sede_resuelta and sedes_visibles:
		sede_resuelta = sedes_visibles[0]
	if not sede_resuelta:
		sede_resuelta = {
			"nombre_sede": sede_nombre or "Sede principal",
			"direccion": getattr(ips_doc, "direccion", "") or "",
			"telefono": getattr(ips_doc, "telefono", "") or "",
			"email": getattr(ips_doc, "email_notificacion", "") or "",
			"requiere_orden_servicio": int(getattr(ips_doc, "requiere_orden_servicio", 0) or 0),
		}

	sede_email = sede_resuelta.get("email") or ""
	if not sede_email:
		return False

	cargo_cita = cita.cargo_al_enviar or ""
	cargo_label = _resolve_cargo_label(cargo_cita) or cargo_cita
	tipo_cargo = _resolve_cargo_tipo(cargo_cita)
	examenes = _resolve_examenes_for_cargo(ips_doc, cargo_cita, tipo_cargo=tipo_cargo)

	attachments = []
	if int(sede_resuelta.get("requiere_orden_servicio", 0) or 0):
		try:
			candidato_for_frsn = {
				"nombre": candidato_nombre,
				"cedula": getattr(candidato, "numero_documento", None) or candidato_name,
				"cargo": cargo_label,
				"ciudad": candidato_ciudad,
			}
			xlsx_bytes = generate_frsn02(ips_doc.as_dict(), candidato_for_frsn)
			if xlsx_bytes:
				attachments = [{
					"fname": f"FRSN-02_{candidato_name}.xlsx",
					"fcontent": xlsx_bytes,
				}]
		except Exception:
			pass

	# Normalizar hora a HH:MM para mostrar en el correo
	hora_display = _format_hora_hhmm(cita.hora_cita)

	try:
		send_exam_email(
			template_name="examen_medico_ips_notificacion",
			recipients=[sede_email],
			context={
				"candidato": {
					"nombre": candidato_nombre,
					"cedula": getattr(candidato, "numero_documento", None) or candidato_name,
					"cargo": cargo_label,
					"ciudad": candidato_ciudad,
				},
				"cita": {
					"fecha_cita": cita.fecha_cita,
					"hora_cita": hora_display,
					"sede": sede_resuelta.get("nombre_sede", ""),
					"sede_direccion": sede_resuelta.get("direccion", ""),
					"sede_ciudad": sede_resuelta.get("ciudad", "") or candidato_ciudad,
				},
				"examenes": examenes,
			},
			attachments=attachments,
		)
	except Exception:
		try:
			frappe.log_error(frappe.get_traceback(), "notify_ips_cita_agendada")
		except Exception:
			pass
		return False

	frappe.db.set_value(
		"Cita Examen Medico",
		cita_name,
		{
			"enviado_ips": 1,
			"fecha_envio": frappe.utils.now_datetime(),
		},
		update_modified=True,
	)
	return True


def _format_hora_hhmm(value) -> str:
	"""Formatea un valor de Time (timedelta | time | str | None) como 'HH:MM'.

	Devuelve string vacío si el valor es None/falso. Tolera microsegundos
	y formatos parciales (HH:MM, HH:MM:SS, HH:MM:SS.ffffff).
	"""
	import datetime as _dt

	if not value:
		return ""
	if isinstance(value, _dt.timedelta):
		total = int(value.total_seconds())
		hh = (total // 3600) % 24
		mm = (total % 3600) // 60
		return f"{hh:02d}:{mm:02d}"
	if isinstance(value, _dt.time):
		return value.strftime("%H:%M")
	text = str(value).strip()
	if not text:
		return ""
	# string formats: "HH:MM" | "HH:MM:SS" | "HH:MM:SS.ffffff"
	parts = text.split(":")
	if len(parts) >= 2:
		try:
			hh = int(parts[0])
			mm = int(parts[1])
			return f"{hh:02d}:{mm:02d}"
		except ValueError:
			return text
	return text
