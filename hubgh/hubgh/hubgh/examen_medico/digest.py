# Copyright (c) 2026, Antigravity and contributors
# For license information, please see license.txt

"""
digest — Resumen diario de exámenes médicos para SST y generalistas.

Reemplaza el CC fijo que antes se mandaba a SST + 2 generalistas en CADA
correo individual del flujo de examen médico. Ese patrón multiplicaba x4
el consumo de créditos en Resend (cada CC = 1 envelope SMTP separado).

Ahora se genera UN solo correo al final del día (17:00, vía scheduler)
con dos secciones:
  1. Candidatos agendados hoy.
  2. Candidatos a quienes se les envió el link y aún no han agendado.

Si ambas listas están vacías, no se envía nada (no spamear con digest vacío).
"""

from __future__ import annotations

from datetime import datetime, timedelta

import frappe


DIGEST_RECIPIENTS_FALLBACK: list[str] = [
	"SST@homeburgers.com",
	"generalistagh1@homeburgers.com",
	"generalistagh2@homeburgers.com",
]


def _load_digest_recipients() -> list[str]:
	"""
	Lee los destinatarios del digest desde el Single
	'Configuracion Examen Medico Autogestionado'.

	Reutiliza la tabla `cc_emails` que antes alimentaba el CC fijo de
	send_exam_email. La semántica cambió: ya no son "CC ocultos" sino
	"suscriptores del digest diario".

	Returns:
		Lista de emails activos. Si el doctype no existe o la tabla está
		vacía, retorna DIGEST_RECIPIENTS_FALLBACK.
	"""
	try:
		config = frappe.get_cached_doc("Configuracion Examen Medico Autogestionado")
		emails: list[str] = []
		for row in config.get("cc_emails") or []:
			activo = row.get("activo") if isinstance(row, dict) else getattr(row, "activo", 1)
			email = row.get("email") if isinstance(row, dict) else getattr(row, "email", None)
			if activo and email:
				email = str(email).strip()
				if email and email not in emails:
					emails.append(email)
		if emails:
			return emails
	except Exception:
		pass

	return list(DIGEST_RECIPIENTS_FALLBACK)


def _query_agendados_hoy() -> list[dict]:
	"""
	Citas confirmadas hoy (campo fecha_agendamiento dentro del día actual).
	"""
	hoy = frappe.utils.today()
	inicio = f"{hoy} 00:00:00"
	fin = f"{hoy} 23:59:59"

	return frappe.db.get_all(
		"Cita Examen Medico",
		filters={
			"fecha_agendamiento": ["between", [inicio, fin]],
			"estado": "Agendada",
		},
		fields=[
			"name",
			"candidato",
			"ips",
			"fecha_cita",
			"hora_cita",
			"sede_seleccionada",
			"cargo_al_enviar",
		],
		order_by="fecha_agendamiento ASC",
	)


def _query_pendientes() -> list[dict]:
	"""
	Citas en estado 'Pendiente Agendamiento' (link enviado, no agendaron aún).
	No se filtra por antigüedad: SST decide si hacer follow-up con rezagados.
	"""
	return frappe.db.get_all(
		"Cita Examen Medico",
		filters={"estado": "Pendiente Agendamiento"},
		fields=[
			"name",
			"candidato",
			"ips",
			"creation",
			"cargo_al_enviar",
		],
		order_by="creation DESC",
	)


def _enrich_rows(rows: list[dict]) -> list[dict]:
	"""
	Agrega `candidato_nombre` (legible) y `ips_nombre` a cada fila.
	Best-effort: si falla un lookup, deja el name como string.

	Para pendientes calcula `dias_pendiente` desde creation.
	"""
	hoy = frappe.utils.now_datetime()
	enriched = []
	for row in rows:
		r = dict(row)
		# Nombre legible del candidato
		try:
			c = frappe.get_cached_doc("Candidato", row["candidato"])
			nombre = " ".join(filter(None, [
				getattr(c, "nombres", None),
				getattr(c, "primer_apellido", None),
				getattr(c, "segundo_apellido", None),
			])) or row["candidato"]
			r["candidato_nombre"] = nombre
			r["candidato_cedula"] = getattr(c, "numero_documento", None) or row["candidato"]
		except Exception:
			r["candidato_nombre"] = row["candidato"]
			r["candidato_cedula"] = row["candidato"]

		# Nombre legible de la IPS
		try:
			ips = frappe.get_cached_doc("IPS", row["ips"])
			r["ips_nombre"] = getattr(ips, "nombre", None) or row["ips"]
		except Exception:
			r["ips_nombre"] = row.get("ips", "")

		# Días pendiente (solo aplica a pendientes; agendados lo ignoran)
		creation = row.get("creation")
		if creation:
			try:
				if isinstance(creation, str):
					creation_dt = datetime.fromisoformat(creation.split(".")[0])
				else:
					creation_dt = creation
				delta = hoy - creation_dt
				r["dias_pendiente"] = max(0, delta.days)
			except Exception:
				r["dias_pendiente"] = None

		enriched.append(r)
	return enriched


def enviar_digest_diario_examenes() -> None:
	"""
	Envía el resumen diario a SST/generalistas.

	Ejecutado por el scheduler de Frappe a las 17:00 (cron "0 17 * * *").
	Si no hay agendados ni pendientes, no envía nada.
	No relanza excepciones; loguea con frappe.log_error.
	"""
	# Belt-and-suspenders: si Frappe corre el cron en otro horario (ej. "daily"),
	# evitamos enviar el digest dos veces en el día.
	if datetime.now().hour != 17:
		return

	try:
		agendados = _enrich_rows(_query_agendados_hoy())
		pendientes = _enrich_rows(_query_pendientes())

		if not agendados and not pendientes:
			return

		recipients = _load_digest_recipients()
		if not recipients:
			return

		from frappe.utils.jinja import render_template

		template_doc = frappe.get_doc("Email Template", "examen_medico_digest_diario")
		context = {
			"fecha": frappe.utils.format_date(frappe.utils.today(), "dd/MM/yyyy"),
			"agendados": agendados,
			"pendientes": pendientes,
			"total_agendados": len(agendados),
			"total_pendientes": len(pendientes),
		}
		subject = render_template(template_doc.subject or "", context)
		message = render_template(
			template_doc.response or template_doc.message or "",
			context,
		)

		frappe.sendmail(
			recipients=recipients,
			subject=subject,
			message=message,
		)
	except Exception as exc:
		frappe.log_error(
			message=str(exc),
			title="enviar_digest_diario_examenes error",
		)
