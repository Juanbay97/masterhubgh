"""Bloque payroll de Persona 360 — conectado al modelo v2.

Cuando el empleado tiene novedades en algún `Payroll Run` exportado,
este módulo arma el dict que el frontend de Persona 360 espera:

	{
		"employee_id": str,
		"payroll_ready": bool,
		"novelty_summary": {tipo: {count, total_amount}, ...},
		"vacation_balance": {days_remaining, calculation_note},
		"active_incapacidades": {total_estimated, note},
		"pending_deductions": {total_amount, total_items},
		"note": str,
	}

Si todavía no hay datos para el empleado, devuelve un payload vacío
sin lanzar excepciones — la página debe seguir cargando.
"""

from __future__ import annotations

from collections import defaultdict
from typing import Any

import frappe


_INCAPACIDAD_TYPES = (
	"INCAPACIDAD_ENFERMEDAD_GENERAL",
	"INCAPACIDAD_ACCIDENTE_TRABAJO",
	"INCAPACIDAD_PAGADA_EMPRESA",
	"INCAPACIDAD_MAYOR_180_DIAS",
	"LICENCIA_MATERNIDAD",
)


def _empty_block(employee_id: str, note: str = "") -> dict[str, Any]:
	return {
		"employee_id": employee_id,
		"payroll_ready": False,
		"novelty_summary": {},
		"vacation_balance": {"days_remaining": 0, "calculation_note": ""},
		"active_incapacidades": {"total_estimated": 0, "note": ""},
		"pending_deductions": {"total_amount": 0, "total_items": 0},
		"note": note or "Sin datos de nómina para este empleado.",
	}


def get_payroll_block(employee_id: str) -> dict[str, Any]:
	"""Devuelve el resumen de novedades del último Run exportado del empleado."""
	if not employee_id:
		return _empty_block("", "Empleado no especificado.")

	# Validar que el DocType nuevo exista; si no, fallback vacío.
	if not frappe.db.exists("DocType", "Payroll Novedad"):
		return _empty_block(employee_id, "Módulo de nómina no migrado.")

	# Tomamos las novedades del empleado de los últimos 12 meses sin filtrar
	# por status del Run — el operador puede ver tendencia incluso cuando un
	# Run quedó en "parsed".
	rows = frappe.db.sql(
		"""
		SELECT n.tipo_novedad, n.unidad, n.calc_status,
			n.computed_amount, n.computed_quantity, n.cantidad,
			n.fecha_desde, n.fecha_hasta, r.period_year, r.period_month, r.status
		FROM `tabPayroll Novedad` n
		INNER JOIN `tabPayroll Run` r ON r.name = n.run
		WHERE n.empleado = %s
		ORDER BY r.period_year DESC, r.period_month DESC
		LIMIT 2000
		""",
		(employee_id,),
		as_dict=True,
	)
	if not rows:
		return _empty_block(employee_id)

	latest_period = (rows[0]["period_year"], rows[0]["period_month"])
	latest_label = f"{latest_period[0]}-{int(latest_period[1] or 0):02d}"

	novelty_summary: dict[str, dict[str, float]] = defaultdict(
		lambda: {"count": 0, "total_amount": 0.0, "total_quantity": 0.0}
	)
	incap_amount = 0.0
	incap_count = 0
	deduction_amount = 0.0
	deduction_items = 0
	vacation_days = 0.0

	for row in rows:
		tipo = row["tipo_novedad"] or "OTRO"
		amount = float(row["computed_amount"] or 0.0)
		qty = float(row["computed_quantity"] or row["cantidad"] or 0.0)
		summary = novelty_summary[tipo]
		summary["count"] += 1
		summary["total_amount"] += amount
		summary["total_quantity"] += qty

		# Solo contamos las novedades del periodo más reciente para el
		# vacation_balance e incapacidades (no acumulado histórico).
		if (row["period_year"], row["period_month"]) == latest_period:
			if tipo == "VACACIONES":
				vacation_days += qty
			if tipo in _INCAPACIDAD_TYPES:
				incap_amount += amount
				incap_count += 1
			if amount < 0:
				deduction_amount += amount
				deduction_items += 1

	return {
		"employee_id": employee_id,
		"payroll_ready": True,
		"novelty_summary": {
			tipo: {
				"count": int(d["count"]),
				"total_amount": round(d["total_amount"], 2),
				"total_quantity": round(d["total_quantity"], 4),
			}
			for tipo, d in novelty_summary.items()
		},
		"vacation_balance": {
			"days_remaining": round(vacation_days, 2),
			"calculation_note": (
				f"Días tomados en {latest_label} según Payroll Run."
				if vacation_days
				else f"Sin vacaciones registradas en {latest_label}."
			),
		},
		"active_incapacidades": {
			"total_estimated": round(incap_amount, 2),
			"note": (
				f"{incap_count} novedad(es) en {latest_label}."
				if incap_count
				else f"Sin incapacidades en {latest_label}."
			),
		},
		"pending_deductions": {
			"total_amount": round(abs(deduction_amount), 2),
			"total_items": int(deduction_items),
		},
		"note": f"Último periodo: {latest_label} ({rows[0]['status']}).",
	}


@frappe.whitelist()
def get_employee_payroll_data(employee_id: str) -> dict[str, Any]:
	"""Endpoint público (Persona 360 lo llama por API)."""
	return get_payroll_block(employee_id)
