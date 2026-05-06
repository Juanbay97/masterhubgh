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
		# Mostrar resumen de la cita ya agendada — incluye dirección de la sede
		# elegida para que el candidato sepa adónde ir sin abrir el correo viejo.
		ips_name = cita_data.get("ips") or ""
		ips_doc_dict = {}
		sede_info = {}
		try:
			if ips_name:
				ips_full = frappe.get_doc("IPS", ips_name)
				ips_doc_dict = ips_full.as_dict()
				sede_seleccionada_nombre = (cita_data.get("sede_seleccionada") or "").strip()
				if sede_seleccionada_nombre:
					for sede_row in (ips_full.sedes or []):
						if (sede_row.nombre_sede or "") == sede_seleccionada_nombre:
							sede_info = {
								"nombre_sede": sede_row.nombre_sede,
								"direccion": sede_row.direccion or "",
								"telefono": sede_row.telefono or "",
							}
							break
				# Fallback: si no hay sede_seleccionada (citas viejas) o no se
				# encontró, usar la dirección principal de la IPS.
				if not sede_info:
					sede_info = {
						"nombre_sede": "",
						"direccion": ips_doc_dict.get("direccion", "") or "",
						"telefono": ips_doc_dict.get("telefono", "") or "",
					}
		except Exception:
			ips_doc_dict = {}
			sede_info = {}

		_ctx_set(context, "mode", "booked")
		_ctx_set(context, "cita", dict(cita_data))
		_ctx_set(context, "slots", None)
		_ctx_set(context, "ips", ips_doc_dict)
		_ctx_set(context, "sede_info", sede_info)
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

		# Empezar desde mañana — hoy no da tiempo operativo para agendar.
		from datetime import timedelta
		tomorrow = date.today() + timedelta(days=1)
		start_date = tomorrow.strftime("%Y-%m-%d")
		# Calcular ventana de días según fecha_limite_agendamiento (si existe en la cita)
		days = 30
		fecha_limite = cita_data.get("fecha_limite_agendamiento")
		if fecha_limite:
			try:
				from datetime import datetime as _dt
				lim = fecha_limite if isinstance(fecha_limite, date) else _dt.strptime(str(fecha_limite), "%Y-%m-%d").date()
				delta = (lim - tomorrow).days + 1
				days = max(0, min(30, delta))
			except Exception:
				days = 30

		slots = slot_engine.get_available_slots(ips_doc, start_date, days=days) if days > 0 else []

		# Filtrar slots posteriores a la fecha límite (defensa adicional al ajuste de days)
		if fecha_limite:
			try:
				slots = [s for s in (slots or []) if str(s.get("fecha", "")) <= str(fecha_limite)]
			except Exception:
				pass

		# Calcular sedes visibles para la ciudad del candidato
		from hubgh.hubgh.examen_medico.cita_service import _get_sedes_for_ciudad

		candidato_ciudad = ""
		try:
			candidato_ciudad = frappe.db.get_value("Candidato", cita_data.get("candidato"), "ciudad") or ""
		except Exception:
			candidato_ciudad = ""
		sedes_visibles = _get_sedes_for_ciudad(ips_doc, candidato_ciudad) if ips_doc else []

		_ctx_set(context, "mode", "pending")
		_ctx_set(context, "slots", slots)
		_ctx_set(context, "cita", dict(cita_data))
		_ctx_set(context, "ips", ips_doc)
		_ctx_set(context, "token", token)
		_ctx_set(context, "sedes", sedes_visibles)
		_ctx_set(context, "fecha_limite", str(fecha_limite) if fecha_limite else "")


@frappe.whitelist(allow_guest=True)
def book_slot(token: str, fecha: str, hora: str, sede: str | None = None) -> dict:
	"""
	Agenda un slot para la Cita identificada por token.

	Valida el token, cuenta los cupos ya ocupados en ese slot y — si hay
	disponibilidad — actualiza la Cita a Agendada y consume el token.

	Args:
		token: Token hex de 32 caracteres del link de agendamiento.
		fecha: Fecha del slot "YYYY-MM-DD".
		hora:  Hora del slot "HH:MM" o "HH:MM:SS".
		sede:  Nombre de la sede elegida (opcional). Si la IPS tiene más de
		       una sede en la ciudad del candidato, este campo es obligatorio.

	Returns:
		{"status": "ok", "cita_name": str, "fecha": str, "hora": str, "sede": str}

	Raises:
		frappe.ValidationError: Token inválido/expirado/usado, cupo lleno,
		fecha mayor a la fecha límite, o sede faltante cuando hay múltiples.
	"""
	# Validar token — lanza ValidationError si inválido
	cita_data = token_manager.validate_token(token)
	cita_name = cita_data["name"]
	ips_name = cita_data.get("ips") or ""

	# Validar fecha — no permitir hoy ni días pasados (hoy no da tiempo
	# operativo) ni fechas posteriores a la fecha límite.
	from datetime import date as _d, timedelta as _td

	tomorrow_str = (_d.today() + _td(days=1)).strftime("%Y-%m-%d")
	if str(fecha) < tomorrow_str:
		frappe.throw(
			"La fecha seleccionada no es válida. Elegí un día a partir de mañana.",
			frappe.ValidationError,
		)
	fecha_limite = cita_data.get("fecha_limite_agendamiento")
	if fecha_limite and str(fecha) > str(fecha_limite):
		frappe.throw(
			f"La fecha seleccionada ({fecha}) es posterior a la fecha límite ({fecha_limite}).",
			frappe.ValidationError,
		)

	# Resolver sedes válidas para la ciudad del candidato
	from hubgh.hubgh.examen_medico.cita_service import _get_sedes_for_ciudad

	ips_doc = frappe.get_doc("IPS", ips_name) if ips_name else None
	candidato_ciudad = ""
	try:
		candidato_ciudad = frappe.db.get_value("Candidato", cita_data.get("candidato"), "ciudad") or ""
	except Exception:
		candidato_ciudad = ""
	sedes_visibles = _get_sedes_for_ciudad(ips_doc.as_dict(), candidato_ciudad) if ips_doc else []

	sede_elegida = (sede or "").strip()
	if len(sedes_visibles) > 1 and not sede_elegida:
		frappe.throw(
			"Debés elegir una sede antes de agendar.",
			frappe.ValidationError,
		)
	if sede_elegida and sedes_visibles:
		nombres_validos = {s.get("nombre_sede") for s in sedes_visibles}
		if sede_elegida not in nombres_validos:
			frappe.throw(
				f"La sede '{sede_elegida}' no está disponible para tu ciudad.",
				frappe.ValidationError,
			)
	# Si solo hay una sede y no se mandó, autoselect
	if not sede_elegida and len(sedes_visibles) == 1:
		sede_elegida = sedes_visibles[0].get("nombre_sede") or ""

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

	cupos_por_slot = cita_data.get("cupos_por_slot") or 50

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
			"sede_seleccionada": sede_elegida or None,
		},
	)

	# Consumir token
	from hubgh.hubgh.examen_medico.token_manager import consume_token
	consume_token(cita_name)

	# Enviar emails post-agendamiento (best-effort — no bloquear respuesta HTTP)
	try:
		from hubgh.hubgh.examen_medico.email_service import send_exam_email
		from hubgh.hubgh.examen_medico.frsn02_generator import generate_frsn02

		cita = frappe.get_doc("Cita Examen Medico", cita_name)
		candidato = frappe.get_doc("Candidato", cita.candidato)

		candidato_nombre = " ".join(filter(None, [
			getattr(candidato, "nombres", None),
			getattr(candidato, "primer_apellido", None),
			getattr(candidato, "segundo_apellido", None),
		])) or cita.candidato

		# Resolver datos de la sede elegida (con fallback al primer match si no fue forzada)
		sede_resuelta = None
		for s in (sedes_visibles or []):
			if sede_elegida and s.get("nombre_sede") == sede_elegida:
				sede_resuelta = s
				break
		if not sede_resuelta and sedes_visibles:
			sede_resuelta = sedes_visibles[0]
		if not sede_resuelta:
			# Sin sedes visibles: armar una sintética con datos de la IPS
			sede_resuelta = {
				"nombre_sede": "Sede principal",
				"direccion": getattr(ips_doc, "direccion", "") if ips_doc else "",
				"telefono": getattr(ips_doc, "telefono", "") if ips_doc else "",
				"email": getattr(ips_doc, "email_notificacion", "") if ips_doc else "",
				"requiere_orden_servicio": int(getattr(ips_doc, "requiere_orden_servicio", 0) or 0) if ips_doc else 0,
			}

		ips_nombre = getattr(ips_doc, "nombre", ips_name) if ips_doc else ips_name

		# Email 1: confirmación al candidato — template según tipo de cargo
		candidato_email = getattr(candidato, "email", None) or ""
		if candidato_email and ips_doc:
			try:
				site_url = frappe.utils.get_url()
			except Exception:
				site_url = ""
			portal_url = f"{site_url}/agendar_examen?token={token}"

			from hubgh.hubgh.examen_medico.cita_service import (
				_operativo_attachments,
				_resolve_cargo_tipo,
				_resolve_examenes_for_cargo,
			)
			cargo_cita_for_tipo = cita.cargo_al_enviar or ""
			tipo_cargo = _resolve_cargo_tipo(cargo_cita_for_tipo)
			confirm_template = (
				"examen_medico_confirmacion_administrativo"
				if tipo_cargo == "Administrativo"
				else "examen_medico_confirmacion_operativo"
			)
			# Fallback al legacy si el template específico no existe (entornos
			# que aún no corrieron el patch nuevo).
			if not frappe.db.exists("Email Template", confirm_template):
				confirm_template = "examen_medico_confirmacion"

			examenes_candidato = _resolve_examenes_for_cargo(ips_doc, cargo_cita_for_tipo)

			# Adjuntar imágenes de instrucciones solo para cargos operativos.
			confirm_attachments = (
				_operativo_attachments() if tipo_cargo != "Administrativo" else []
			)

			try:
				send_exam_email(
					template_name=confirm_template,
					recipients=[candidato_email],
					context={
						"candidato": {"nombre": candidato_nombre},
						"cita": {"fecha_cita": fecha, "hora_cita": hora},
						"ips": {
							"nombre": ips_nombre,
							"direccion": sede_resuelta.get("direccion", ""),
							"telefono": sede_resuelta.get("telefono", ""),
							"sede": sede_resuelta.get("nombre_sede", ""),
						},
						"portal_url": portal_url,
						"examenes": examenes_candidato,
					},
					attachments=confirm_attachments,
				)
				frappe.db.set_value("Cita Examen Medico", cita_name, "enviado_confirmacion", 1)
			except Exception:
				pass

		# Email 2: notificación a la sede de la IPS
		sede_email = sede_resuelta.get("email") or ""
		if sede_email and ips_doc:
			from hubgh.hubgh.examen_medico.cita_service import (
				_resolve_cargo_label,
				_resolve_examenes_for_cargo,
			)

			candidato_ciudad = getattr(candidato, "ciudad", None) or ""
			cargo_cita = cita.cargo_al_enviar or ""
			# Para el correo y el FRSN-02 mostramos el nombre legible del cargo
			# (ej. "AUXILIAR DE COCINA"), no el código numérico ("416").
			cargo_label = _resolve_cargo_label(cargo_cita) or cargo_cita
			# Lista de exámenes con fallback (cargo específico → cargo vacío).
			examenes = _resolve_examenes_for_cargo(ips_doc, cargo_cita)
			attachments = []
			if int(sede_resuelta.get("requiere_orden_servicio", 0) or 0):
				try:
					# Adapt Candidato fields to the generator contract.
					candidato_for_frsn = {
						"nombre": candidato_nombre,
						"cedula": getattr(candidato, "numero_documento", None) or cita.candidato,
						"cargo": cargo_label,
						"ciudad": candidato_ciudad,
					}
					xlsx_bytes = generate_frsn02(ips_doc.as_dict(), candidato_for_frsn)
					if xlsx_bytes:
						attachments = [{
							"fname": f"FRSN-02_{candidato.name}.xlsx",
							"fcontent": xlsx_bytes,
						}]
				except Exception:
					pass
			try:
				send_exam_email(
					template_name="examen_medico_ips_notificacion",
					recipients=[sede_email],
					context={
						"candidato": {
							"nombre": candidato_nombre,
							"cedula": cita.candidato,
							"cargo": cargo_label,
							"ciudad": candidato_ciudad,
						},
						"cita": {
							"fecha_cita": fecha,
							"hora_cita": hora,
							"sede": sede_resuelta.get("nombre_sede", ""),
							"sede_direccion": sede_resuelta.get("direccion", ""),
						},
						"examenes": examenes,
					},
					attachments=attachments,
				)
				frappe.db.set_value("Cita Examen Medico", cita_name, "enviado_ips", 1)
			except Exception:
				pass
		frappe.db.commit()
	except Exception:
		pass

	return {"status": "ok", "cita_name": cita_name, "fecha": fecha, "hora": hora, "sede": sede_elegida}
