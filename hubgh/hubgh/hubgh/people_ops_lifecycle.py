from __future__ import annotations

from typing import Any

import frappe
from frappe.utils import getdate, nowdate

from hubgh.access_profiles import ensure_roles_and_profiles
from hubgh.person_identity import reconcile_person_identity, resolve_user_for_employee
from hubgh.user_groups import ensure_contextual_groups, sync_all_user_groups
from hubgh.hubgh.bienestar_automation import ensure_ingreso_followups_for_employee


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


