# Copyright (c) 2026, Antigravity and contributors
# For license information, please see license.txt

"""
Portal público de agendamiento de examen médico.

allow_guest = True  — Frappe requiere esta variable a nivel módulo.
no_cache = 1        — Sin caché para que el token siempre se revalide.

Flujo GET:
  ?token=<hex32> → valida token → renderiza calendario de slots disponibles
  Si ya está Agendada → muestra resumen de la cita actual (mode="booked")
  Si inválido/expirado → lanza excepción (Frappe devuelve 400)

Flujo POST (book_slot):
  token + fecha + hora → valida token → verifica cupos → agenda la Cita
  Si cupo ocupado → lanza ValidationError

Nota de imports: el paquete Frappe resuelve hubgh.hubgh.examen_medico
como la ruta física hubgh/hubgh/hubgh/examen_medico/ — los tests
parchean a ese mismo nivel de módulo.

Nota de context: Frappe pasa un frappe._dict como context en producción,
pero los tests pasan un dict plano. Usamos _ctx_set() para ser compatible
con ambos (setitem / setattr).
"""

from __future__ import annotations

import frappe

from hubgh.hubgh.examen_medico import token_manager
from hubgh.hubgh.examen_medico import slot_engine

allow_guest = True
no_cache = 1


def _ctx_set(context, key, value):
	"""Set key on context whether it is a dict or an object with attributes."""
	try:
		context[key] = value
	except TypeError:
		setattr(context, key, value)


def get_context(context):
	"""
	Maneja el renderizado GET del portal de agendamiento.

	Lee ?token= de frappe.request.args (o frappe.form_dict para compatibilidad).
	Setea en context:
	  - mode="pending" + slots + ips + token  → cita aún no agendada
	  - mode="booked" + cita                  → cita ya Agendada
	Lanza frappe.ValidationError si el token es inválido/expirado/usado.
	"""
	_ctx_set(context, "no_cache", 1)

	# Leer token desde query string o form_dict
	token = ""
	try:
		token = frappe.request.args.get("token") or ""
	except Exception:
		pass
	if not token:
		try:
			token = frappe.form_dict.get("token") or ""
		except Exception:
			pass

	# Validar token — lanza ValidationError si inválido/expirado/usado/vacío
	cita_data = token_manager.validate_token(token)

	estado = (cita_data.get("estado") or "").strip()

	if estado == "Agendada":
		# Mostrar resumen de la cita ya agendada
		_ctx_set(context, "mode", "booked")
		_ctx_set(context, "cita", dict(cita_data))
		_ctx_set(context, "slots", None)
		_ctx_set(context, "ips", None)
	else:
		# Generar slots disponibles para los próximos 30 días
		from datetime import date

		ips_name = cita_data.get("ips") or ""
		ips_doc = {}
		try:
			if ips_name:
				ips_doc = frappe.get_doc("IPS", ips_name).as_dict()
		except Exception:
			ips_doc = {}

		start_date = date.today().strftime("%Y-%m-%d")
		slots = slot_engine.get_available_slots(ips_doc, start_date, days=30)

		_ctx_set(context, "mode", "pending")
		_ctx_set(context, "slots", slots)
		_ctx_set(context, "cita", dict(cita_data))
		_ctx_set(context, "ips", ips_doc)
		_ctx_set(context, "token", token)


@frappe.whitelist(allow_guest=True)
def book_slot(token: str, fecha: str, hora: str) -> dict:
	"""
	Agenda un slot para la Cita identificada por token.

	Valida el token, cuenta los cupos ya ocupados en ese slot y — si hay
	disponibilidad — actualiza la Cita a Agendada y consume el token.

	Args:
		token: Token hex de 32 caracteres del link de agendamiento.
		fecha: Fecha del slot "YYYY-MM-DD".
		hora:  Hora del slot "HH:MM" o "HH:MM:SS".

	Returns:
		{"status": "ok", "cita_name": str, "fecha": str, "hora": str}

	Raises:
		frappe.ValidationError: Token inválido/expirado/usado, o cupo lleno.
	"""
	# Validar token — lanza ValidationError si inválido
	cita_data = token_manager.validate_token(token)
	cita_name = cita_data["name"]
	ips_name = cita_data.get("ips") or ""

	# Contar citas ya agendadas/realizadas para este slot
	booked = frappe.db.get_value(
		"Cita Examen Medico",
		{
			"ips": ips_name,
			"fecha_cita": fecha,
			"hora_cita": hora,
			"estado": ["in", ["Agendada", "Realizada"]],
		},
		"count(name)",
	) or 0

	cupos_por_slot = cita_data.get("cupos_por_slot") or 3

	if int(booked) >= int(cupos_por_slot):
		frappe.throw("Cupo ocupado para el slot seleccionado.", frappe.ValidationError)

	# Normalizar hora a HH:MM:SS
	if hora and len(hora.split(":")) == 2:
		hora = hora + ":00"

	# Actualizar Cita
	frappe.db.set_value(
		"Cita Examen Medico",
		cita_name,
		{
			"estado": "Agendada",
			"fecha_cita": fecha,
			"hora_cita": hora,
		},
	)

	# Consumir token
	from hubgh.hubgh.examen_medico.token_manager import consume_token
	consume_token(cita_name)

	return {"status": "ok", "cita_name": cita_name, "fecha": fecha, "hora": hora}
