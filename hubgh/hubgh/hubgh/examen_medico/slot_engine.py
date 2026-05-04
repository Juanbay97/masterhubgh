# Copyright (c) 2026, Antigravity and contributors
# For license information, please see license.txt

"""
slot_engine — Generación lazy de slots disponibles para citas de examen médico.

Calcula los slots disponibles a partir de los horarios configurados en la IPS,
excluyendo días bloqueados, festivos colombianos y slots con cupo lleno.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta

# Mapping: Python weekday() → dia_semana code used in IPS Horario
# Monday=0, Tuesday=1, Wednesday=2, Thursday=3, Friday=4, Saturday=5, Sunday=6
_WEEKDAY_MAP = {0: "L", 1: "M", 2: "X", 3: "J", 4: "V", 5: "S", 6: "D"}


def get_available_slots(
	ips: dict,
	start_date: str,
	days: int = 30,
	existing_citas: list[dict] | None = None,
) -> list[dict]:
	"""
	Retorna [{fecha, hora, disponibles}] — cupos restantes por slot.

	Args:
		ips: Documento IPS como dict, con horarios y dias_bloqueados.
		start_date: Fecha de inicio en formato "YYYY-MM-DD".
		days: Ventana de búsqueda hacia adelante (días).
		existing_citas: Lista de citas existentes [{fecha_cita, hora_cita, estado}].

	Returns:
		Lista de slots disponibles con fecha, hora y cupos restantes.
	"""
	from hubgh.hubgh.examen_medico.festivos import is_colombia_holiday

	if existing_citas is None:
		existing_citas = []

	# Build a lookup for existing citas count per (fecha, hora)
	booked_count: dict[tuple[str, str], int] = {}
	for cita in existing_citas:
		if cita.get("estado") in ("Agendada", "Realizada"):
			key = (str(cita.get("fecha_cita", "")), str(cita.get("hora_cita", "")))
			booked_count[key] = booked_count.get(key, 0) + 1

	# Build set of blocked dates
	blocked_dates: set[str] = set()
	for row in ips.get("dias_bloqueados") or []:
		blocked_dates.add(str(row.get("fecha", "")))

	slots = []

	# Parse start_date
	parts = start_date.split("-")
	current = date(int(parts[0]), int(parts[1]), int(parts[2]))

	for _ in range(days):
		fecha_str = current.strftime("%Y-%m-%d")

		# Skip blocked days
		if fecha_str in blocked_dates:
			current += timedelta(days=1)
			continue

		# Skip festivos
		if is_colombia_holiday(fecha_str):
			current += timedelta(days=1)
			continue

		# Find horarios for this weekday
		dia_code = _WEEKDAY_MAP[current.weekday()]
		horarios_hoy = [
			h for h in (ips.get("horarios") or [])
			if h.get("dia_semana") == dia_code
		]

		for horario in horarios_hoy:
			intervalo = int(horario.get("intervalo_minutos", 60))
			cupos_total = int(horario.get("cupos_por_slot", 3))

			# Parse hora_inicio and hora_fin
			hora_inicio_str = str(horario.get("hora_inicio", "08:00:00"))
			hora_fin_str = str(horario.get("hora_fin", "18:00:00"))

			# Normalize to HH:MM:SS
			def _parse_time(t: str) -> datetime:
				parts_t = t.split(":")
				h = int(parts_t[0]) if len(parts_t) > 0 else 0
				m = int(parts_t[1]) if len(parts_t) > 1 else 0
				s = int(parts_t[2]) if len(parts_t) > 2 else 0
				return datetime(2000, 1, 1, h, m, s)

			t_inicio = _parse_time(hora_inicio_str)
			t_fin = _parse_time(hora_fin_str)
			t_current = t_inicio

			while t_current < t_fin:
				hora_str = t_current.strftime("%H:%M:%S")
				key = (fecha_str, hora_str)
				booked = booked_count.get(key, 0)
				disponibles = cupos_total - booked

				if disponibles > 0:
					slots.append({
						"fecha": fecha_str,
						"hora": hora_str,
						"disponibles": disponibles,
						"cupos_total": cupos_total,
					})

				t_current += timedelta(minutes=intervalo)

		current += timedelta(days=1)

	return slots


def get_booked_count(
	ips_name: str,
	fecha: str,
	hora: str,
) -> int:
	"""
	Cuenta las Citas en estado Agendada|Realizada para esta ips+fecha+hora.

	Args:
		ips_name: Nombre de la IPS.
		fecha: Fecha en formato "YYYY-MM-DD".
		hora: Hora en formato "HH:MM:SS".

	Returns:
		Cantidad de citas agendadas o realizadas en ese slot.
	"""
	import frappe

	return frappe.db.count(
		"Cita Examen Medico",
		filters={
			"ips": ips_name,
			"fecha_cita": fecha,
			"hora_cita": hora,
			"estado": ["in", ["Agendada", "Realizada"]],
		},
	)
