# Copyright (c) 2026, Antigravity and contributors
# For license information, please see license.txt

"""
tasks — Tareas programadas del módulo examen_medico.

Contiene `enviar_recordatorios_examen_medico`, ejecutada por el scheduler
de Frappe a las 17:00 diariamente (cron: "0 17 * * *").

Incluye guardia horaria como cinturón-y-tirantes para el caso de que
el scheduler use "daily" en lugar de "cron".
"""

from __future__ import annotations

from datetime import datetime, timedelta, date

import frappe
from hubgh.hubgh.examen_medico.email_service import send_exam_email, get_ips_email


def enviar_recordatorios_examen_medico() -> None:
	"""
	Envía emails de recordatorio a candidatos con cita el día siguiente.

	Consulta Citas donde:
	  - fecha_cita == mañana
	  - estado == "Agendada"
	  - enviado_recordatorio == 0

	Para cada cita envía el template `examen_medico_recordatorio` y
	marca enviado_recordatorio=1.

	Incluye guardia: si datetime.now().hour != 17, retorna sin hacer nada
	(belt-and-suspenders para el caso daily fallback).
	"""
	# Belt-and-suspenders guard for "daily" scheduler fallback
	if datetime.now().hour != 17:
		return

	tomorrow = (date.today() + timedelta(days=1)).isoformat()

	citas = frappe.db.get_all(
		"Cita Examen Medico",
		filters={
			"fecha_cita": tomorrow,
			"estado": "Agendada",
			"enviado_recordatorio": 0,
		},
		fields=[
			"name",
			"candidato",
			"ips",
			"fecha_cita",
			"hora_cita",
			"cargo_al_enviar",
		],
	)

	for cita in citas:
		try:
			candidato = frappe.get_doc("Candidato", cita["candidato"])
			ips = frappe.get_doc("IPS", cita["ips"])

			context = {
				"candidato": {"nombre": candidato.nombre},
				"cita": {
					"fecha_cita": cita["fecha_cita"],
					"hora_cita": cita["hora_cita"],
				},
				"ips": {
					"nombre": ips.nombre,
					"direccion": ips.direccion,
				},
			}

			send_exam_email(
				template_name="examen_medico_recordatorio",
				recipients=[candidato.email],
				context=context,
			)

			frappe.db.set_value(
				"Cita Examen Medico",
				cita["name"],
				"enviado_recordatorio",
				1,
			)
		except Exception as exc:
			frappe.log_error(
				message=str(exc),
				title=f"Error recordatorio cita {cita.get('name')}",
			)
