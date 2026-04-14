from __future__ import annotations

from typing import Any

import frappe
from frappe import _
from frappe.utils import cstr, getdate, nowdate

from hubgh.hubgh import employee_retirement_service
from hubgh.hubgh.people_ops_lifecycle import reverse_retirement_if_clear
from hubgh.hubgh.role_matrix import user_has_any_role


DISCIPLINARY_OPERATOR_ROLES = {"System Manager", "HR Labor Relations", "GH - RRLL", "Relaciones Laborales Jefe", "Gerente GH"}
DISCIPLINARY_OUTCOME_OPTIONS = ["Archivo", "Llamado de atención", "Suspensión", "Terminación"]
DISCIPLINARY_TERMINATION_REASON = "Terminación con justa causa"


def get_disciplinary_flow_context(user=None) -> dict[str, Any]:
	user = user or getattr(getattr(frappe, "session", None), "user", None) or "Guest"
	can_manage = user == "Administrator" or user_has_any_role(user, *DISCIPLINARY_OPERATOR_ROLES)
	return {
		"user": user,
		"can_manage": can_manage,
		"outcome_options": DISCIPLINARY_OUTCOME_OPTIONS,
	}


def enforce_disciplinary_access(user=None) -> dict[str, Any]:
	context = get_disciplinary_flow_context(user=user)
	if context["can_manage"]:
		return context
	frappe.throw(
		_("Solo Relaciones Laborales puede operar la bandeja disciplinaria."),
		getattr(frappe, "PermissionError", None),
	)
	raise PermissionError("Disciplinary tray restricted to Relaciones Laborales")


def get_disciplinary_tray(filters=None) -> dict[str, Any]:
	enforce_disciplinary_access()
	if isinstance(filters, str):
		filters = frappe.parse_json(filters) or {}
	filters = filters or {}
	search = cstr(filters.get("search")).strip().lower()
	status_filter = cstr(filters.get("status")).strip()
	decision_filter = _normalize_outcome(filters.get("decision"))
	pdv_filter = cstr(filters.get("pdv")).strip()
	limit = int(filters.get("limit") or 200)

	case_rows = frappe.get_all(
		"Caso Disciplinario",
		fields=[
			"name",
			"empleado",
			"fecha_incidente",
			"tipo_falta",
			"estado",
			"decision_final",
			"fecha_cierre",
			"resumen_cierre",
			"fecha_inicio_suspension",
			"fecha_fin_suspension",
			"modified",
		],
		order_by="modified desc",
		limit_page_length=max(limit * 2, limit),
	)

	employees = sorted({cstr(row.get("empleado")).strip() for row in case_rows if cstr(row.get("empleado")).strip()})
	employee_map = {}
	if employees:
		for row in frappe.get_all(
			"Ficha Empleado",
			filters={"name": ["in", employees]},
			fields=["name", "nombres", "apellidos", "cedula", "pdv", "estado"],
			limit_page_length=0,
		):
			employee_map[row.get("name")] = row

	rows = []
	for row in case_rows:
		decision = _normalize_outcome(row.get("decision_final"))
		employee = employee_map.get(row.get("empleado"), {})
		full_name = " ".join(filter(None, [cstr(employee.get("nombres")), cstr(employee.get("apellidos"))])).strip()
		search_blob = " ".join(
			[
				cstr(row.get("name")),
				cstr(row.get("empleado")),
				full_name,
				cstr(employee.get("cedula")),
				cstr(employee.get("pdv")),
				cstr(row.get("tipo_falta")),
				cstr(row.get("resumen_cierre")),
			]
		).lower()
		if search and search not in search_blob:
			continue
		if status_filter and cstr(row.get("estado")).strip() != status_filter:
			continue
		if decision_filter and decision != decision_filter:
			continue
		if pdv_filter and cstr(employee.get("pdv")).strip() != pdv_filter:
			continue

		rows.append(
			{
				"name": row.get("name"),
				"employee": row.get("empleado"),
				"employee_name": full_name or row.get("empleado") or "",
				"employee_status": employee.get("estado") or "",
				"cedula": employee.get("cedula") or "",
				"pdv": employee.get("pdv") or "",
				"incident_date": row.get("fecha_incidente") or "",
				"fault_type": row.get("tipo_falta") or "",
				"status": row.get("estado") or "",
				"decision": decision,
				"closure_date": row.get("fecha_cierre") or "",
				"closure_summary": row.get("resumen_cierre") or "",
				"suspension_start": row.get("fecha_inicio_suspension") or "",
				"suspension_end": row.get("fecha_fin_suspension") or "",
				"can_close": cstr(row.get("estado")).strip() != "Cerrado",
			}
		)
		if len(rows) >= limit:
			break

	status_summary = {}
	decision_summary = {}
	for row in rows:
		status_summary[row["status"]] = status_summary.get(row["status"], 0) + 1
		if row["decision"]:
			decision_summary[row["decision"]] = decision_summary.get(row["decision"], 0) + 1

	return {
		"status": "success",
		"rows": rows,
		"summary": {
			"total": len(rows),
			"open": status_summary.get("Abierto", 0),
			"in_progress": status_summary.get("En Proceso", 0),
			"closed": status_summary.get("Cerrado", 0),
			"suspension": decision_summary.get("Suspensión", 0),
			"termination": decision_summary.get("Terminación", 0),
		},
	}


def close_disciplinary_case(
	*,
	case_name,
	decision,
	closure_date,
	closure_summary,
	suspension_start=None,
	suspension_end=None,
) -> dict[str, Any]:
	enforce_disciplinary_access()
	if not case_name:
		frappe.throw(_("El caso disciplinario es obligatorio."))

	case_doc = frappe.get_doc("Caso Disciplinario", case_name)
	case_doc.estado = "Cerrado"
	case_doc.decision_final = _normalize_outcome(decision)
	case_doc.fecha_cierre = closure_date
	case_doc.resumen_cierre = cstr(closure_summary).strip()
	case_doc.fecha_inicio_suspension = suspension_start if case_doc.decision_final == "Suspensión" else None
	case_doc.fecha_fin_suspension = suspension_end if case_doc.decision_final == "Suspensión" else None
	case_doc.save(ignore_permissions=True)

	return get_disciplinary_case_snapshot(case_doc.name)


def get_disciplinary_case_snapshot(case_name) -> dict[str, Any]:
	if not case_name:
		return {}
	case_doc = frappe.get_doc("Caso Disciplinario", case_name)
	return {
		"name": case_doc.name,
		"employee": case_doc.empleado,
		"status": case_doc.estado,
		"decision": _normalize_outcome(case_doc.decision_final),
		"closure_date": case_doc.fecha_cierre,
		"closure_summary": case_doc.resumen_cierre,
		"suspension_start": getattr(case_doc, "fecha_inicio_suspension", None),
		"suspension_end": getattr(case_doc, "fecha_fin_suspension", None),
	}


def sync_disciplinary_case_effects(case_doc) -> dict[str, Any]:
	if not getattr(case_doc, "empleado", None):
		return {"status": "skipped", "reason": "missing_employee"}

	decision = _normalize_outcome(getattr(case_doc, "decision_final", None))
	status = cstr(getattr(case_doc, "estado", None)).strip()
	if status != "Cerrado":
		reverse_retirement_if_clear(employee=case_doc.empleado, source_doctype="Caso Disciplinario", source_name=case_doc.name)
		return _clear_disciplinary_suspension_if_possible(case_doc.empleado, current_case=case_doc.name)

	if decision == "Terminación":
		_clear_disciplinary_suspension_if_possible(case_doc.empleado, current_case=case_doc.name)
		return employee_retirement_service.submit_employee_retirement(
			employee=case_doc.empleado,
			last_worked_date=case_doc.fecha_cierre or case_doc.fecha_incidente or nowdate(),
			reason=DISCIPLINARY_TERMINATION_REASON,
			closure_date=case_doc.fecha_cierre or nowdate(),
			closure_summary=cstr(getattr(case_doc, "resumen_cierre", None)).strip(),
			source_doctype="Caso Disciplinario",
			source_name=case_doc.name,
			enforce_access=False,
		)

	reverse_retirement_if_clear(employee=case_doc.empleado, source_doctype="Caso Disciplinario", source_name=case_doc.name)
	if decision == "Suspensión":
		return _sync_case_suspension(case_doc)

	return _clear_disciplinary_suspension_if_possible(case_doc.empleado, current_case=case_doc.name)


def process_closed_disciplinary_cases() -> dict[str, Any]:
	processed = []
	for row in frappe.get_all(
		"Caso Disciplinario",
		filters={"estado": "Cerrado", "decision_final": ["in", ["Suspensión", "Terminación"]]},
		fields=["name"],
		limit_page_length=0,
	):
		case_doc = frappe.get_doc("Caso Disciplinario", row.name)
		processed.append({"case": row.name, "result": sync_disciplinary_case_effects(case_doc)})
	return {"status": "ok", "processed": processed, "processed_count": len(processed)}


def _sync_case_suspension(case_doc) -> dict[str, Any]:
	today = getdate(nowdate())
	start = getdate(case_doc.fecha_inicio_suspension)
	end = getdate(case_doc.fecha_fin_suspension)
	current_status = cstr(frappe.db.get_value("Ficha Empleado", case_doc.empleado, "estado")).strip()

	if current_status == "Retirado":
		return {"status": "skipped", "reason": "employee_retired"}

	if start <= today <= end:
		frappe.db.set_value("Ficha Empleado", case_doc.empleado, "estado", "Suspensión", update_modified=False)
		return {"status": "active", "employee": case_doc.empleado, "start": str(start), "end": str(end)}

	clear_result = _clear_disciplinary_suspension_if_possible(case_doc.empleado, current_case=case_doc.name)
	return {
		"status": "scheduled" if today < start else "expired",
		"employee": case_doc.empleado,
		"start": str(start),
		"end": str(end),
		"clear_result": clear_result,
	}


def _clear_disciplinary_suspension_if_possible(employee, *, current_case=None) -> dict[str, Any]:
	current_status = cstr(frappe.db.get_value("Ficha Empleado", employee, "estado")).strip()
	if current_status != "Suspensión":
		return {"status": "noop", "employee": employee, "reason": "employee_not_suspended"}
	if _has_other_active_suspension_sources(employee, current_case=current_case):
		return {"status": "kept", "employee": employee, "reason": "other_sources_active"}
	frappe.db.set_value("Ficha Empleado", employee, "estado", "Activo", update_modified=False)
	return {"status": "cleared", "employee": employee}


def _has_other_active_suspension_sources(employee, *, current_case=None) -> bool:
	today = getdate(nowdate())
	for row in frappe.get_all(
		"Caso Disciplinario",
		filters={"empleado": employee, "estado": "Cerrado", "decision_final": "Suspensión"},
		fields=["name", "fecha_inicio_suspension", "fecha_fin_suspension"],
		limit_page_length=0,
	):
		if row.name == current_case:
			continue
		if not row.fecha_inicio_suspension or not row.fecha_fin_suspension:
			continue
		if getdate(row.fecha_inicio_suspension) <= today <= getdate(row.fecha_fin_suspension):
			return True

	for row in frappe.get_all(
		"Novedad SST",
		filters={"empleado": employee, "estado_destino": "Suspensión"},
		fields=["estado", "fecha_fin"],
		limit_page_length=0,
	):
		if cstr(row.get("estado")).strip().lower() in {"cerrada", "cerrado"}:
			continue
		if row.get("fecha_fin") and getdate(row.get("fecha_fin")) < today:
			continue
		return True
	return False


def _normalize_outcome(value) -> str:
	value = cstr(value).strip()
	legacy_map = {"Llamado de Atención": "Llamado de atención"}
	return legacy_map.get(value, value)
