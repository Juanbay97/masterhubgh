from __future__ import annotations

from typing import Any

import frappe
from frappe import _
from frappe.utils import cstr, getdate, nowdate

from hubgh.hubgh.people_ops_lifecycle import apply_retirement
from hubgh.hubgh.role_matrix import user_has_any_role


RETIREMENT_OPERATOR_ROLES = {"HR Labor Relations", "GH - RRLL", "Relaciones Laborales Jefe"}
RETIREMENT_FLOW_SOURCE_DOCTYPE = "Ficha Empleado"
RETIREMENT_REASON_OPTIONS = [
	"Renuncia",
	"Terminación con justa causa",
	"Terminación sin justa causa",
	"Mutuo acuerdo",
	"Fin de contrato",
	"Jubilación",
	"Fallecimiento",
	"Abandono",
	"Otro",
]
RETIREMENT_ACTIVE_STATUSES = {"Programado", "Ejecutado", "Revertido"}
RETIREMENT_METADATA_FIELDS = {
	"estado_retiro_operacion",
	"motivo_retiro",
	"fecha_ultimo_dia_laborado",
	"fecha_retiro_efectiva",
	"fecha_cierre_retiro",
	"detalle_retiro",
	"retiro_fuente_doctype",
	"retiro_fuente_name",
}


def get_retirement_flow_context(user=None) -> dict[str, Any]:
	user = user or getattr(getattr(frappe, "session", None), "user", None) or "Guest"
	can_manage = user == "Administrator" or user_has_any_role(user, *RETIREMENT_OPERATOR_ROLES)
	return {
		"user": user,
		"can_manage": can_manage,
		"reason_options": RETIREMENT_REASON_OPTIONS,
	}


def enforce_retirement_access(user=None) -> dict[str, Any]:
	context = get_retirement_flow_context(user=user)
	if context["can_manage"]:
		return context
	frappe.throw(
		_("Solo Relaciones Laborales puede operar el flujo de retiro de empleados."),
		getattr(frappe, "PermissionError", None),
	)
	raise PermissionError("Retirement flow restricted to Relaciones Laborales")


def submit_employee_retirement(
	*,
	employee,
	last_worked_date,
	reason,
	closure_date=None,
	closure_summary=None,
	source_doctype=None,
	source_name=None,
	enforce_access=True,
) -> dict[str, Any]:
	if enforce_access:
		enforce_retirement_access()
	if not employee:
		frappe.throw(_("El empleado es obligatorio."))
	if not last_worked_date:
		frappe.throw(_("El último día laborado es obligatorio."))
	if cstr(reason).strip() not in RETIREMENT_REASON_OPTIONS:
		frappe.throw(_("El motivo de retiro no es válido."))

	today = getdate(nowdate())
	effective_date = str(getdate(last_worked_date))
	closure_date_value = str(getdate(closure_date or nowdate()))
	closure_summary = cstr(closure_summary).strip()
	reason = cstr(reason).strip()
	snapshot = get_employee_retirement_snapshot(employee=employee, enforce_access=False)
	current_flow_status = cstr(snapshot.get("retirement", {}).get("flow_status")).strip()
	current_employee_status = cstr(snapshot.get("employee", {}).get("estado")).strip()
	reason_detail = _compose_reason_detail(reason=reason, closure_summary=closure_summary)
	source_doctype = cstr(source_doctype).strip() or RETIREMENT_FLOW_SOURCE_DOCTYPE
	source_name = cstr(source_name).strip() or employee
	metadata = {
		"estado_retiro_operacion": "Ejecutado" if getdate(effective_date) <= today else "Programado",
		"motivo_retiro": reason,
		"fecha_ultimo_dia_laborado": effective_date,
		"fecha_retiro_efectiva": effective_date,
		"fecha_cierre_retiro": closure_date_value,
		"detalle_retiro": closure_summary,
		"retiro_fuente_doctype": source_doctype,
		"retiro_fuente_name": source_name,
	}

	if current_employee_status == "Retirado" or current_flow_status == "Ejecutado":
		_update_retirement_metadata(employee, metadata)
		return {
			"status": "already_retired",
			"employee": employee,
			"retirement_date": effective_date,
			"retirement_record": get_employee_retirement_snapshot(employee=employee, enforce_access=False),
		}

	if getdate(effective_date) > today:
		_update_retirement_metadata(employee, metadata)
		return {
			"status": "scheduled",
			"employee": employee,
			"retirement_date": effective_date,
			"retirement_record": get_employee_retirement_snapshot(employee=employee, enforce_access=False),
		}

	lifecycle_result = apply_retirement(
		employee=employee,
		source_doctype=source_doctype,
		source_name=source_name,
		retirement_date=effective_date,
		reason=reason_detail,
	)
	_update_retirement_metadata(employee, metadata)
	return {
		"status": "retired",
		"employee": employee,
		"retirement_date": effective_date,
		"lifecycle": lifecycle_result,
		"retirement_record": get_employee_retirement_snapshot(employee=employee, enforce_access=False),
	}


def process_pending_employee_retirements() -> dict[str, Any]:
	today = str(getdate(nowdate()))
	processed = []
	skipped = []
	for row in frappe.get_all(
		"Ficha Empleado",
		filters={
			"estado_retiro_operacion": "Programado",
			"fecha_retiro_efectiva": ["<=", today],
		},
		fields=_employee_query_fields(),
		limit_page_length=0,
	):
		if cstr(_row_value(row, "estado")).strip() == "Retirado":
			_update_retirement_metadata(_row_value(row, "name"), {"estado_retiro_operacion": "Ejecutado"})
			skipped.append({"employee": _row_value(row, "name"), "reason": "already_retired"})
			continue

		reason = _compose_reason_detail(
			reason=_row_value(row, "motivo_retiro"),
			closure_summary=_row_value(row, "detalle_retiro"),
		)
		result = apply_retirement(
			employee=_row_value(row, "name"),
			source_doctype=_row_value(row, "retiro_fuente_doctype") or RETIREMENT_FLOW_SOURCE_DOCTYPE,
			source_name=_row_value(row, "retiro_fuente_name") or _row_value(row, "name"),
			retirement_date=_row_value(row, "fecha_retiro_efectiva") or today,
			reason=reason,
		)
		_update_retirement_metadata(
			_row_value(row, "name"),
			{
				"estado_retiro_operacion": "Ejecutado",
				"retiro_fuente_doctype": _row_value(row, "retiro_fuente_doctype") or RETIREMENT_FLOW_SOURCE_DOCTYPE,
				"retiro_fuente_name": _row_value(row, "retiro_fuente_name") or _row_value(row, "name"),
			},
		)
		processed.append({
			"employee": _row_value(row, "name"),
			"retirement_date": _row_value(row, "fecha_retiro_efectiva") or today,
			"lifecycle": result,
		})

	return {
		"status": "ok",
		"processed": processed,
		"processed_count": len(processed),
		"skipped": skipped,
	}


def get_employee_retirement_snapshot(*, employee, enforce_access=True) -> dict[str, Any]:
	if enforce_access:
		enforce_retirement_access()
	if not employee:
		return {}

	fields = _employee_query_fields()
	row = frappe.db.get_value("Ficha Empleado", employee, fields, as_dict=True)
	if not row:
		return {}

	flow_status = _resolve_flow_status(row)
	return {
		"employee": {
			"name": row.get("name"),
			"nombres": row.get("nombres"),
			"apellidos": row.get("apellidos"),
			"cedula": row.get("cedula"),
			"cargo": row.get("cargo"),
			"pdv": row.get("pdv"),
			"estado": row.get("estado"),
			"fecha_ingreso": row.get("fecha_ingreso"),
		},
		"retirement": {
			"flow_status": flow_status,
			"reason": row.get("motivo_retiro") or "",
			"last_worked_date": row.get("fecha_ultimo_dia_laborado") or row.get("fecha_retiro_efectiva") or "",
			"retirement_date": row.get("fecha_retiro_efectiva") or "",
			"closure_date": row.get("fecha_cierre_retiro") or "",
			"closure_summary": row.get("detalle_retiro") or "",
			"source_doctype": row.get("retiro_fuente_doctype") or "",
			"source_name": row.get("retiro_fuente_name") or "",
		},
	}


def get_retirement_tray(filters=None) -> dict[str, Any]:
	enforce_retirement_access()
	if isinstance(filters, str):
		filters = frappe.parse_json(filters) or {}
	filters = filters or {}
	search = cstr(filters.get("search")).strip().lower()
	status_filter = cstr(filters.get("status")).strip()
	limit = int(filters.get("limit") or 200)
	today = getdate(nowdate())

	rows = []
	for row in frappe.get_all(
		"Ficha Empleado",
		fields=_employee_query_fields(),
		order_by="modified desc",
		limit_page_length=max(limit * 2, limit),
	):
		flow_status = _resolve_flow_status(row)
		if not flow_status:
			continue
		if status_filter and flow_status != status_filter:
			continue
		search_blob = " ".join(
			[
				cstr(_row_value(row, "name")),
				cstr(_row_value(row, "nombres")),
				cstr(_row_value(row, "apellidos")),
				cstr(_row_value(row, "cedula")),
				cstr(_row_value(row, "motivo_retiro")),
			]
		).lower()
		if search and search not in search_blob:
			continue

		retirement_date = _row_value(row, "fecha_retiro_efectiva")
		is_effective = bool(retirement_date and getdate(retirement_date) <= today)
		rows.append(
			{
				"employee": _row_value(row, "name"),
				"full_name": " ".join(filter(None, [cstr(_row_value(row, "nombres")), cstr(_row_value(row, "apellidos"))])).strip(),
				"cedula": _row_value(row, "cedula") or "",
				"cargo": _row_value(row, "cargo") or "",
				"pdv": _row_value(row, "pdv") or "",
				"employee_status": _row_value(row, "estado") or "",
				"flow_status": flow_status,
				"reason": _row_value(row, "motivo_retiro") or "",
				"last_worked_date": _row_value(row, "fecha_ultimo_dia_laborado") or _row_value(row, "fecha_retiro_efectiva") or "",
				"retirement_date": retirement_date or "",
				"closure_date": _row_value(row, "fecha_cierre_retiro") or "",
				"closure_summary": _row_value(row, "detalle_retiro") or "",
				"source_doctype": _row_value(row, "retiro_fuente_doctype") or "",
				"source_name": _row_value(row, "retiro_fuente_name") or "",
				"belongs_to_company": not is_effective,
			}
		)
		if len(rows) >= limit:
			break

	status_summary = {}
	for row in rows:
		status_summary[row["flow_status"]] = status_summary.get(row["flow_status"], 0) + 1

	return {
		"status": "success",
		"rows": rows,
		"summary": {
			"total": len(rows),
			"scheduled": status_summary.get("Programado", 0),
			"executed": status_summary.get("Ejecutado", 0),
			"reverted": status_summary.get("Revertido", 0),
			"legacy_retired": status_summary.get("Legado Retirado", 0),
		},
		"filters_applied": {
			"search": search,
			"status": status_filter,
			"limit": limit,
		},
	}


def _resolve_flow_status(row) -> str:
	status = cstr(_row_value(row, "estado_retiro_operacion")).strip()
	if status in RETIREMENT_ACTIVE_STATUSES:
		return status
	if cstr(_row_value(row, "estado")).strip() == "Retirado":
		return "Legado Retirado"
	return ""


def _employee_query_fields() -> list[str]:
	base_fields = [
		"name",
		"nombres",
		"apellidos",
		"cedula",
		"cargo",
		"pdv",
		"estado",
		"fecha_ingreso",
	]
	optional_fields = sorted(field for field in RETIREMENT_METADATA_FIELDS if field in _get_employee_supported_fields())
	return base_fields + optional_fields


def _get_employee_supported_fields() -> set[str]:
	try:
		meta = frappe.get_meta("Ficha Empleado")
	except Exception:
		return set(RETIREMENT_METADATA_FIELDS)
	return {field.fieldname for field in getattr(meta, "fields", []) if getattr(field, "fieldname", None)}


def _update_retirement_metadata(employee, updates: dict[str, Any]) -> None:
	available_fields = _get_employee_supported_fields()
	applicable = {key: value for key, value in (updates or {}).items() if key in available_fields}
	if applicable:
		frappe.db.set_value("Ficha Empleado", employee, applicable, update_modified=False)


def _compose_reason_detail(*, reason, closure_summary=None) -> str:
	parts = [cstr(reason).strip()]
	if cstr(closure_summary).strip():
		parts.append(cstr(closure_summary).strip())
	return ". ".join(part for part in parts if part)


def _row_value(row, fieldname, default=None):
	if isinstance(row, dict):
		return row.get(fieldname, default)
	return getattr(row, fieldname, default)
