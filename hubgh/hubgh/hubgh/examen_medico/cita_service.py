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
			send_exam_email(
				template_name="examen_medico_link_agendar",
				recipients=[candidato_email],
				context={
					"candidato": {"nombre": _candidato_full_name(candidato, fallback=candidato_name)},
					"portal_url": portal_url,
					"ips": {"nombre": ips_name},
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
