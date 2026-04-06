from __future__ import annotations

from typing import Any

import frappe
from frappe.utils import cstr, getdate, nowdate

from hubgh.access_profiles import ensure_roles_and_profiles
from hubgh.person_identity import reconcile_person_identity, resolve_user_for_employee
from hubgh.user_groups import ensure_contextual_groups, sync_all_user_groups
from hubgh.hubgh.bienestar_automation import ensure_ingreso_followups_for_employee


RRLL_RETIREMENT_ROLES = {"System Manager", "HR Labor Relations", "GH - RRLL", "Gerente GH"}


def finalize_hiring(contract_doc) -> dict[str, Any]:
	ensure_roles_and_profiles()
	pdv_name = getattr(contract_doc, "pdv_destino", None)
	city_name = frappe.db.get_value("Punto de Venta", pdv_name, "ciudad") if pdv_name else None
	ensure_contextual_groups(pdv_name=pdv_name, city=city_name)
	sync_all_user_groups()

	employee = contract_doc._ensure_employee() if hasattr(contract_doc, "_ensure_employee") else getattr(contract_doc, "empleado", None)
	if not employee:
		frappe.throw("No se pudo resolver el empleado para formalizar la contratación.")

	candidate_user = frappe.db.get_value("Candidato", contract_doc.candidato, "user") if getattr(contract_doc, "candidato", None) else None
	identity = reconcile_person_identity(
		employee=employee,
		user=candidate_user,
		document=getattr(contract_doc, "numero_documento", None),
		email=getattr(contract_doc, "email", None),
		allow_create_user=not bool(candidate_user),
		user_defaults={
			"first_name": getattr(contract_doc, "nombres", None),
			"last_name": getattr(contract_doc, "apellidos", None),
			"enabled": 1,
			"send_welcome_email": 0,
			"user_type": "System User",
		},
		user_roles=["Empleado", "Candidato"],
	)
	if identity.user:
		_promote_user_to_employee(identity.user, employee, contract_doc)

	if hasattr(contract_doc, "_sync_employee_operational_data"):
		contract_doc._sync_employee_operational_data(employee)

	employee_doc = frappe.get_doc("Ficha Empleado", employee)
	if getattr(contract_doc, "fecha_ingreso", None):
		employee_doc.fecha_ingreso = contract_doc.fecha_ingreso
	if getattr(contract_doc, "email", None):
		employee_doc.email = contract_doc.email
	if getattr(contract_doc, "pdv_destino", None):
		employee_doc.pdv = contract_doc.pdv_destino
	if getattr(contract_doc, "cargo", None):
		employee_doc.cargo = contract_doc.cargo
	if getattr(contract_doc, "tipo_jornada", None):
		employee_doc.tipo_jornada = contract_doc.tipo_jornada
	if (employee_doc.estado or "") != "Activo":
		employee_doc.estado = "Activo"
	employee_doc.save(ignore_permissions=True)
	ensure_contextual_groups(pdv_name=getattr(employee_doc, "pdv", None), city=frappe.db.get_value("Punto de Venta", getattr(employee_doc, "pdv", None), "ciudad") if getattr(employee_doc, "pdv", None) else None)
	sync_all_user_groups()

	if hasattr(contract_doc, "db_set"):
		contract_doc.db_set("empleado", employee)
		contract_doc.db_set("estado_contrato", "Activo")
	else:
		contract_doc.empleado = employee
		contract_doc.estado_contrato = "Activo"

	if getattr(contract_doc, "candidato", None):
		candidate_updates = {"persona": employee, "estado_proceso": "Contratado"}
		if identity.user:
			candidate_updates["user"] = identity.user
		frappe.db.set_value("Candidato", contract_doc.candidato, candidate_updates, update_modified=False)

	_ensure_employee_document_folder(employee)
	ensure_ingreso_followups_for_employee(employee_doc, from_source=f"Contrato {getattr(contract_doc, 'name', '')}".strip())
	if hasattr(contract_doc, "_publish_ingreso_event"):
		contract_doc._publish_ingreso_event(employee)

	return {
		"employee": employee,
		"user": identity.user,
		"status": "hired",
	}


def apply_retirement(*, employee, source_doctype, source_name, retirement_date=None, reason=None, contract_status="Retirado") -> dict[str, Any]:
	if not employee:
		return {}

	retirement_date = str(retirement_date or nowdate())
	frappe.db.set_value("Ficha Empleado", employee, "estado", "Retirado", update_modified=False)
	identity = resolve_user_for_employee(employee)
	user_name = identity.user if identity else None
	if user_name:
		frappe.db.set_value("User", user_name, {"enabled": 0, "user_type": "System User", "employee": employee}, update_modified=False)

	_deactivate_tarjeta_empleado_if_exists(employee)
	_sync_contract_retirement(employee, contract_status=contract_status)
	payroll_case = _ensure_payroll_liquidation_case(employee, retirement_date)
	_emit_trace_event(
		employee=employee,
		source_doctype=source_doctype,
		source_name=source_name,
		retirement_date=retirement_date,
		reason=reason,
		action="retiro",
	)

	return {
		"employee": employee,
		"source_doctype": source_doctype,
		"source_name": source_name,
		"retirement_date": retirement_date,
		"contract_status": contract_status,
		"user_enabled": 0 if user_name else None,
		"card_active": 0,
		"payroll_case": payroll_case,
	}


def reverse_retirement_if_clear(*, employee, source_doctype, source_name) -> dict[str, Any]:
	if not employee:
		return {"reversed": False, "reason": "missing_employee"}
	if _has_other_active_retirement_sources(employee, source_doctype=source_doctype, source_name=source_name):
		return {"reversed": False, "reason": "other_sources_active"}

	frappe.db.set_value("Ficha Empleado", employee, "estado", "Activo", update_modified=False)
	identity = resolve_user_for_employee(employee)
	user_name = identity.user if identity else None
	if user_name:
		frappe.db.set_value("User", user_name, {"enabled": 1, "user_type": "System User", "employee": employee}, update_modified=False)
	_reactivate_tarjeta_empleado_if_exists(employee)
	_sync_contract_retirement(employee, contract_status="Activo")
	_emit_trace_event(
		employee=employee,
		source_doctype=source_doctype,
		source_name=source_name,
		retirement_date=nowdate(),
		action="reintegro",
	)
	return {"reversed": True, "employee": employee, "user": user_name}


def _promote_user_to_employee(user_name, employee, contract_doc) -> None:
	user_doc = frappe.get_doc("User", user_name)
	user_doc.user_type = "System User"
	user_doc.enabled = 1
	if hasattr(user_doc, "employee"):
		user_doc.employee = employee
	if getattr(contract_doc, "email", None):
		user_doc.email = contract_doc.email
	if getattr(contract_doc, "numero_documento", None):
		user_doc.username = contract_doc.numero_documento
	if getattr(contract_doc, "nombres", None):
		user_doc.first_name = contract_doc.nombres
	if getattr(contract_doc, "apellidos", None):
		user_doc.last_name = contract_doc.apellidos
	roles = {row.role if hasattr(row, "role") else row.get("role") for row in getattr(user_doc, "roles", [])}
	roles.update({"Empleado", "Candidato"})
	user_doc.set("roles", [{"role": role} for role in sorted(role for role in roles if role)])
	user_doc.save(ignore_permissions=True)


def _ensure_employee_document_folder(employee) -> None:
	if frappe.db.exists("Persona Documento", {"persona": employee, "tipo_documento": "Carpeta"}):
		return
	frappe.get_doc(
		{
			"doctype": "Persona Documento",
			"persona": employee,
			"tipo_documento": "Carpeta",
			"estado_documento": "Pendiente",
		}
	).insert(ignore_permissions=True)


def _sync_contract_retirement(employee, contract_status):
	for row in frappe.get_all(
		"Contrato",
		filters={"empleado": employee},
		fields=["name"],
		limit_page_length=0,
	):
		frappe.db.set_value("Contrato", row.name, "estado_contrato", contract_status, update_modified=False)


def _ensure_payroll_liquidation_case(employee, retirement_date):
	if not frappe.db.exists("DocType", "Payroll Liquidation Case"):
		return None
	from hubgh.hubgh.doctype.payroll_liquidation_case.payroll_liquidation_case import create_liquidation_case

	case_doc = create_liquidation_case(employee, retirement_date=retirement_date)
	return getattr(case_doc, "name", None)


def _deactivate_tarjeta_empleado_if_exists(employee):
	if not frappe.db.exists("DocType", "Tarjeta Empleado"):
		return
	meta = frappe.get_meta("Tarjeta Empleado")
	fields = {field.fieldname for field in meta.fields}
	updates = {}
	if "activo" in fields:
		updates["activo"] = 0
	if "estado" in fields:
		updates["estado"] = "Inactivo"
	if updates:
		frappe.db.set_value("Tarjeta Empleado", {"empleado": employee}, updates, update_modified=False)


def _reactivate_tarjeta_empleado_if_exists(employee):
	if not frappe.db.exists("DocType", "Tarjeta Empleado"):
		return
	meta = frappe.get_meta("Tarjeta Empleado")
	fields = {field.fieldname for field in meta.fields}
	updates = {}
	if "activo" in fields:
		updates["activo"] = 1
	if "estado" in fields:
		updates["estado"] = "Activa"
	if updates:
		frappe.db.set_value("Tarjeta Empleado", {"empleado": employee}, updates, update_modified=False)


def _has_other_active_retirement_sources(employee, *, source_doctype, source_name):
	for row in frappe.get_all(
		"Novedad SST",
		filters={"empleado": employee, "estado_destino": "Retirado", "estado": ["in", ["Cerrada", "Cerrado"]]},
		fields=["name"],
		limit_page_length=0,
	):
		if source_doctype == "Novedad SST" and row.name == source_name:
			continue
		return True
	for row in frappe.get_all(
		"Caso Disciplinario",
		filters={"empleado": employee, "estado": "Cerrado", "decision_final": "Terminación"},
		fields=["name"],
		limit_page_length=0,
	):
		if source_doctype == "Caso Disciplinario" and row.name == source_name:
			continue
		return True
	return False


def _emit_trace_event(*, employee, source_doctype, source_name, retirement_date, action, reason=None):
	if not frappe.db.exists("DocType", "GH Novedad"):
		return
	description = _build_trace_description(action, source_doctype, source_name, reason=reason)
	if frappe.db.exists(
		"GH Novedad",
		{"persona": employee, "tipo": "Otro", "descripcion": ["like", f"%{source_doctype} {source_name}%"]},
	):
		return
	frappe.get_doc(
		{
			"doctype": "GH Novedad",
			"persona": employee,
			"tipo": "Otro",
			"cola_origen": "GH-RRLL",
			"cola_destino": "GH-RRLL",
			"estado": "Cerrada",
			"fecha_inicio": retirement_date,
			"fecha_fin": retirement_date,
			"descripcion": description,
		}
	).insert(ignore_permissions=True)


def _build_trace_description(action, source_doctype, source_name, reason=None):
	action_label = "Retiro controlado" if action == "retiro" else "Reintegro compensado"
	base = f"{action_label} desde {source_doctype} {source_name}"
	if cstr(reason).strip():
		return f"{base}. {cstr(reason).strip()}"
	return base
