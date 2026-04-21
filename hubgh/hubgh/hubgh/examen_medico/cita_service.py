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


def create_cita_and_send_link(
	candidato_name: str,
	cargo: str | None = None,
) -> str:
	"""
	Crea una Cita Examen Medico y envía el link de agendamiento al candidato.

	Resuelve la IPS por ciudad del candidato. Captura cargo_postulado en
	cargo_al_enviar. Genera token y envía email con link.

	Args:
		candidato_name: Nombre del documento Candidato.
		cargo: Cargo para capturar en cargo_al_enviar. Si no se pasa,
		       usa candidato.cargo_postulado.

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

	# Auto-assign IPS by candidato's ciudad
	candidato_ciudad = getattr(candidato, "ciudad", None) or ""
	ips_name = frappe.db.get_value(
		"IPS",
		{"ciudad": candidato_ciudad, "activa": 1},
		"name",
	)
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
	portal_url = f"{site_url}/agendar-examen?token={token}"

	# Send link email (best-effort — do not fail the whole operation on email error)
	candidato_email = getattr(candidato, "email", None) or ""
	if candidato_email:
		try:
			send_exam_email(
				template_name="examen_medico_link_agendar",
				recipients=[candidato_email],
				context={
					"candidato": {"nombre": getattr(candidato, "nombre", candidato_name)},
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
		action: Para "No Asistió" — "rebook" crea nueva cita, "close" sólo cancela.
	"""
	import frappe
	from hubgh.hubgh.examen_medico.token_manager import create_token
	from hubgh.hubgh.examen_medico.email_service import send_exam_email

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
		frappe.db.set_value(
			"Cita Examen Medico",
			cita_name,
			{
				"estado": "Aplazada",
				"motivo_aplazamiento": motivo or "",
				"instrucciones_reagendamiento": instrucciones or "",
			},
		)
		# Generate new token for re-scheduling
		new_token = create_token(cita_name, expiry_days=14)

		# Send email with new link (best-effort)
		try:
			candidato = frappe.get_doc("Candidato", cita.candidato)
			try:
				site_url = frappe.utils.get_url()
			except Exception:
				site_url = ""
			portal_url = f"{site_url}/agendar-examen?token={new_token}"
			candidato_email = getattr(candidato, "email", None) or ""
			send_exam_email(
				template_name="examen_medico_aplazado",
				recipients=[candidato_email] if candidato_email else [""],
				context={
					"candidato": {"nombre": getattr(candidato, "nombre", cita.candidato)},
					"cita": {
						"motivo_aplazamiento": motivo or "",
						"instrucciones_reagendamiento": instrucciones or "",
					},
					"portal_url": portal_url,
				},
			)
		except Exception:
			pass

	elif estado == "No Asistió":
		# Cancel the old cita
		frappe.db.set_value("Cita Examen Medico", cita_name, "estado", "Cancelada")

		if action == "rebook":
			# Create a new Cita with a new token
			nueva_cita = frappe.new_doc("Cita Examen Medico")
			nueva_cita.candidato = cita.candidato
			nueva_cita.ips = cita.ips
			nueva_cita.estado = "Pendiente Agendamiento"
			nueva_cita.cargo_al_enviar = getattr(cita, "cargo_al_enviar", None) or ""
			nueva_cita.cita_anterior = cita_name
			try:
				nueva_cita.insert(ignore_permissions=True)
			except TypeError:
				nueva_cita.insert()

			# Generate new token
			new_token = create_token(nueva_cita.name, expiry_days=14)

			# Send new link email (best-effort)
			try:
				candidato = frappe.get_doc("Candidato", cita.candidato)
				try:
					site_url = frappe.utils.get_url()
				except Exception:
					site_url = ""
				portal_url = f"{site_url}/agendar-examen?token={new_token}"
				candidato_email = getattr(candidato, "email", None) or ""
				if candidato_email:
					send_exam_email(
						template_name="examen_medico_link_agendar",
						recipients=[candidato_email],
						context={
							"candidato": {"nombre": getattr(candidato, "nombre", cita.candidato)},
							"portal_url": portal_url,
							"ips": {"nombre": getattr(cita, "ips", "") or ""},
						},
					)
			except Exception:
				pass
