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


def _resolve_examenes_for_cargo(ips_doc, cargo_codigo: str | None) -> list[dict]:
	"""Devuelve la lista de exámenes a realizar para el cargo del candidato.

	Estrategia con fallback:
	  1. Filas de IPS Examen Estandar Por Cargo donde `cargo == codigo` exacto.
	  2. Si la lista anterior queda vacía, filas con `cargo` vacío (configuradas
	     como "aplica a todos los cargos como default").
	  3. Si la 2ª también está vacía, lista vacía (el correo no muestra exámenes).

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
	# Path 1 — match exacto por cargo
	matched = [
		{"nombre_examen": _row_get(r, "nombre_examen") or ""}
		for r in rows
		if (_row_get(r, "cargo") or "").strip() == codigo and codigo
	]
	if matched:
		return matched
	# Path 2 — fallback a filas con cargo vacío
	default = [
		{"nombre_examen": _row_get(r, "nombre_examen") or ""}
		for r in rows
		if not (_row_get(r, "cargo") or "").strip()
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


def _get_sedes_for_ciudad(ips_doc, candidato_ciudad: str) -> list[dict]:
	"""Return active sedes of `ips_doc` whose ciudad matches `candidato_ciudad`
	(accent/case-tolerant). Each entry is a dict with the sede fields plus the
	resolved `email` and `requiere_orden_servicio` (with IPS-level fallbacks).

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
				"email": ips_email or "",
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
				"email": (_row_get(row, "email_notificacion", "") or ips_email or ""),
				"requiere_orden_servicio": int(_row_get(row, "requiere_orden_servicio", 0) or 0),
			}
		)
	return out


def create_cita_and_send_link(
	candidato_name: str,
	cargo: str | None = None,
	fecha_limite: str | None = None,
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
			examenes = _resolve_examenes_for_cargo(ips_doc_for_examenes, cargo_al_enviar)

			# Para cargos operativos adjuntar las 2 imágenes con instrucciones
			# (muestra coprológica + KOH). Para administrativos, sin adjuntos.
			attachments = _operativo_attachments() if tipo_cargo != "Administrativo" else []

			send_exam_email(
				template_name=template_name,
				recipients=[candidato_email],
				context={
					"candidato": {"nombre": _candidato_full_name(candidato, fallback=candidato_name)},
					"portal_url": portal_url,
					"ips": {"nombre": ips_name},
					"examenes": examenes,
				},
				attachments=attachments,
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
	Registra el resultado del examen médico.

	Args:
		cita_name: Nombre del documento Cita Examen Medico.
		estado: Estado final — "Realizada", "Aplazada", "No Asistió".
		concepto: Concepto médico para Realizada — "Favorable" o "Desfavorable".
		motivo: Motivo de aplazamiento (para Aplazada).
		instrucciones: Instrucciones de reagendamiento (para Aplazada).
		action: Para "No Asistió" — "close" cancela la cita. (El reagendamiento
		        ya no es automático: si GH quiere reagendar al candidato, vuelve
		        a usar "Enviar a examen" desde Selección, lo que crea una nueva
		        cita y envía un nuevo link desde cero.)
	"""
	import frappe

	cita = frappe.get_doc("Cita Examen Medico", cita_name)

	if estado == "Realizada":
		frappe.db.set_value("Cita Examen Medico", cita_name, "estado", "Realizada")
		if concepto in ("Favorable", "Desfavorable"):
			frappe.db.set_value("Cita Examen Medico", cita_name, "concepto_resultado", concepto)
			# Write to Candidato
			frappe.db.set_value(
				"Candidato",
				cita.candidato,
				"concepto_medico",
				concepto,
			)

	elif estado == "Aplazada":
		# Marca la cita como Aplazada y registra motivo/instrucciones para que
		# SST tenga la trazabilidad. NO envía correo automático ni regenera
		# link — si hay que reagendar, GH lo hace desde Selección con un
		# nuevo "Enviar a examen".
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
		# Cancela la cita. No reagenda automáticamente.
		# El parámetro `action` se mantiene en la firma por compatibilidad
		# pero ya no dispara la creación de una nueva cita.
		frappe.db.set_value("Cita Examen Medico", cita_name, "estado", "Cancelada")
