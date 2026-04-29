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

# States where an afectado is still pending (not yet started descargos)
_PENDING_AFECTADO_STATES = {"Citado", "Descargos Programados", "En Triage", "Pendiente Triage"}


# ===========================================================================
# Phase 5 — Bandeja helpers
# ===========================================================================


def _get_afectado_nombre(empleado: str) -> str:
	"""Returns full name of an employee, falling back to the ID."""
	if not empleado:
		return ""
	row = frappe.db.get_value(
		"Ficha Empleado",
		empleado,
		["nombres", "apellidos"],
		as_dict=True,
	)
	if not row:
		return empleado
	if isinstance(row, dict):
		nombres = cstr(row.get("nombres", ""))
		apellidos = cstr(row.get("apellidos", ""))
	else:
		nombres = cstr(getattr(row, "nombres", ""))
		apellidos = cstr(getattr(row, "apellidos", ""))
	return " ".join(filter(None, [nombres, apellidos])).strip() or empleado


def compute_proxima_accion(caso_estado: str, afectados: list[dict], *, citacion_vencida: bool = False) -> str:
	"""
	Compute the next recommended action for a caso based on its estado
	and the list of its afectados.

	Args:
		caso_estado: The Caso Disciplinario estado string.
		afectados: List of dicts/namespaces with at least {"estado": str, "empleado": str}.
		citacion_vencida: Whether any citacion is overdue — prefixes result with ⚠ URGENTE.

	Returns:
		Human-readable next action string.
	"""
	def _nombre(af):
		emp = af.get("empleado") if isinstance(af, dict) else getattr(af, "empleado", "")
		return _get_afectado_nombre(emp)

	def _af_estado(af):
		return cstr(af.get("estado") if isinstance(af, dict) else getattr(af, "estado", "")).strip()

	resultado = ""

	if caso_estado == "En Triage":
		resultado = "Hacer triage"
	elif caso_estado == "Descargos Programados":
		first = next((a for a in afectados if _af_estado(a) in ("Descargos Programados", "En Triage")), None)
		nombre = _nombre(first) if first else (afectados[0] and _nombre(afectados[0]) if afectados else "")
		resultado = f"Emitir citación para {nombre}" if nombre else "Emitir citaciones"
	elif caso_estado == "Citado":
		first = next((a for a in afectados if _af_estado(a) == "Citado"), afectados[0] if afectados else None)
		nombre = _nombre(first) if first else ""
		resultado = f"Conducir descargos de {nombre}" if nombre else "Conducir descargos"
	elif caso_estado == "En Descargos":
		first = next((a for a in afectados if _af_estado(a) == "En Descargos"), afectados[0] if afectados else None)
		nombre = _nombre(first) if first else ""
		resultado = f"Completar acta de {nombre}" if nombre else "Completar actas"
	elif caso_estado == "En Deliberación":
		pendientes = [a for a in afectados if _af_estado(a) == "En Deliberación"]
		if not pendientes and afectados:
			pendientes = afectados
		first = pendientes[0] if pendientes else None
		nombre = _nombre(first) if first else ""
		resultado = f"Deliberar sobre {nombre}" if nombre else "Deliberar"
	elif caso_estado == "Cerrado":
		resultado = ""
	else:
		# Solicitado or unknown
		resultado = "Revisar caso"

	if citacion_vencida and resultado:
		resultado = f"⚠ URGENTE: {resultado}"

	return resultado


def detect_citacion_vencida(caso_name: str, afectado_names: list[str]) -> bool:
	"""
	Returns True if any Citacion Disciplinaria linked to the given afectados has
	fecha_programada_descargos < today AND the afectado is still in a pending state
	(Citado or Descargos Programados).
	"""
	if not afectado_names:
		return False

	today = getdate(nowdate())
	citaciones = frappe.get_all(
		"Citacion Disciplinaria",
		filters={"afectado": ["in", afectado_names]},
		fields=["name", "afectado", "fecha_programada_descargos", "estado"],
	)
	for cit in citaciones:
		fecha = cit.fecha_programada_descargos if isinstance(cit, dict) else getattr(cit, "fecha_programada_descargos", None)
		if not fecha:
			continue
		if getdate(fecha) >= today:
			continue
		afectado_name = cit.get("afectado") if isinstance(cit, dict) else getattr(cit, "afectado", None)
		if not afectado_name:
			continue
		afectado_estado = frappe.db.get_value("Afectado Disciplinario", afectado_name, "estado") or ""
		if cstr(afectado_estado).strip() in _PENDING_AFECTADO_STATES:
			return True
	return False


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


def get_disciplinary_tray(filters=None, start: int = 0, limit: int = 0) -> dict[str, Any]:
	enforce_disciplinary_access()

	if isinstance(filters, str):
		filters = frappe.parse_json(filters) or {}
	filters = filters or {}
	search = cstr(filters.get("search")).strip().lower()

	# Support both legacy "status" key and new "estado" key
	status_filter = cstr(filters.get("estado") or filters.get("status")).strip()
	# Support both legacy "decision" key and new "outcome" key
	decision_filter = _normalize_outcome(filters.get("outcome") or filters.get("decision"))
	pdv_filter = cstr(filters.get("pdv")).strip()
	date_from = filters.get("date_from") or ""
	date_to = filters.get("date_to") or ""
	limit = int(filters.get("limit") or limit or 200)
	start = int(filters.get("start") or start or 0)

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

	# Fetch all afectados for all cases (single batch query)
	caso_names = [cstr(row.get("name")) for row in case_rows if row.get("name")]
	afectados_by_caso: dict[str, list] = {}
	if caso_names:
		for af in frappe.get_all(
			"Afectado Disciplinario",
			filters={"caso": ["in", caso_names]},
			fields=["name", "caso", "empleado", "estado", "decision_final_afectado"],
			limit_page_length=0,
		):
			caso_k = cstr(af.get("caso") if isinstance(af, dict) else getattr(af, "caso", "")).strip()
			afectados_by_caso.setdefault(caso_k, []).append(af)

	# Fetch all afectado names for vencida detection
	all_afectado_names = [
		cstr(af.get("name") if isinstance(af, dict) else getattr(af, "name", "")).strip()
		for afs in afectados_by_caso.values()
		for af in afs
	]

	# Batch fetch citaciones to avoid N+1
	citaciones_by_afectado: dict[str, list] = {}
	if all_afectado_names:
		for cit in frappe.get_all(
			"Citacion Disciplinaria",
			filters={"afectado": ["in", all_afectado_names]},
			fields=["name", "afectado", "fecha_programada_descargos", "estado"],
			limit_page_length=0,
		):
			afectado_k = cstr(cit.get("afectado") if isinstance(cit, dict) else getattr(cit, "afectado", "")).strip()
			citaciones_by_afectado.setdefault(afectado_k, []).append(cit)

	# Build employee map from afectados' empleados only
	all_emp_ids = set()
	for afs in afectados_by_caso.values():
		for af in afs:
			emp = cstr(af.get("empleado") if isinstance(af, dict) else getattr(af, "empleado", "")).strip()
			if emp:
				all_emp_ids.add(emp)

	employee_map: dict[str, Any] = {}
	if all_emp_ids:
		for emp_row in frappe.get_all(
			"Ficha Empleado",
			filters={"name": ["in", list(all_emp_ids)]},
			fields=["name", "nombres", "apellidos", "cedula", "pdv", "estado"],
			limit_page_length=0,
		):
			employee_map[cstr(emp_row.get("name") if isinstance(emp_row, dict) else getattr(emp_row, "name", "")).strip()] = emp_row

	today = getdate(nowdate())

	def _emp_full_name(emp_id: str) -> str:
		emp = employee_map.get(emp_id, {})
		if isinstance(emp, dict):
			return " ".join(filter(None, [cstr(emp.get("nombres")), cstr(emp.get("apellidos"))])).strip()
		return " ".join(filter(None, [cstr(getattr(emp, "nombres", "")), cstr(getattr(emp, "apellidos", ""))])).strip()

	def _emp_field(emp_id: str, field: str, default="") -> str:
		emp = employee_map.get(emp_id, {})
		if isinstance(emp, dict):
			return cstr(emp.get(field, default))
		return cstr(getattr(emp, field, default))

	def _detect_vencida_inline(afectados: list, caso_afectado_names: list[str]) -> bool:
		if not caso_afectado_names:
			return False
		for af_name in caso_afectado_names:
			cits = citaciones_by_afectado.get(af_name, [])
			af_estado = ""
			# Get estado from the afectados list
			for af in afectados:
				n = cstr(af.get("name") if isinstance(af, dict) else getattr(af, "name", "")).strip()
				if n == af_name:
					af_estado = cstr(af.get("estado") if isinstance(af, dict) else getattr(af, "estado", "")).strip()
					break
			if af_estado not in _PENDING_AFECTADO_STATES:
				continue
			for cit in cits:
				fecha = cit.get("fecha_programada_descargos") if isinstance(cit, dict) else getattr(cit, "fecha_programada_descargos", None)
				if fecha and getdate(fecha) < today:
					return True
		return False

	all_rows = []
	for row in case_rows:
		caso_name = cstr(row.get("name")).strip()
		caso_estado = cstr(row.get("estado")).strip()

		afectados = afectados_by_caso.get(caso_name, [])
		afectado_names_local = [
			cstr(af.get("name") if isinstance(af, dict) else getattr(af, "name", "")).strip()
			for af in afectados
		]

		# Determine outcome from afectados
		raw_decision = None
		for af in afectados:
			d = af.get("decision_final_afectado") if isinstance(af, dict) else getattr(af, "decision_final_afectado", None)
			if d:
				raw_decision = d
				break
		outcome = _normalize_outcome(raw_decision)

		# PDV: from first afectado's employee
		pdv = ""
		if afectados:
			first_emp = cstr(afectados[0].get("empleado") if isinstance(afectados[0], dict) else getattr(afectados[0], "empleado", "")).strip()
			pdv = _emp_field(first_emp, "pdv") if first_emp else ""

		# Afectados summary
		afectado_empleados = [
			cstr(af.get("empleado") if isinstance(af, dict) else getattr(af, "empleado", "")).strip()
			for af in afectados
		]
		preview_names = [_emp_full_name(e) or e for e in afectado_empleados[:3] if e]
		afectados_summary = {
			"count": len(afectados),
			"preview": preview_names,
		}

		# fecha_ultimo_movimiento
		fecha_ultimo_movimiento = cstr(row.get("modified")).strip()

		# citacion_vencida
		citacion_vencida = _detect_vencida_inline(afectados, afectado_names_local)

		# proxima_accion — always computed from afectados
		proxima_accion = compute_proxima_accion(caso_estado, afectados, citacion_vencida=citacion_vencida)

		# Build search blob from afectados only
		afectados_names_str = " ".join(preview_names)
		afectados_cedulas = " ".join(
			_emp_field(e, "cedula")
			for e in afectado_empleados
			if e
		)
		search_blob = " ".join(
			[
				caso_name,
				pdv,
				cstr(row.get("tipo_falta")),
				cstr(row.get("resumen_cierre")),
				afectados_names_str,
				afectados_cedulas,
			]
		).lower()

		# Apply filters
		if search and search not in search_blob:
			continue
		if status_filter and caso_estado != status_filter:
			continue
		if decision_filter and outcome != decision_filter:
			continue
		if pdv_filter and pdv != pdv_filter:
			continue
		if date_from and row.get("fecha_incidente") and cstr(row.get("fecha_incidente")) < date_from:
			continue
		if date_to and row.get("fecha_incidente") and cstr(row.get("fecha_incidente")) > date_to:
			continue

		all_rows.append(
			{
				"name": caso_name,
				"pdv": pdv,
				"incident_date": cstr(row.get("fecha_incidente")),
				"fault_type": cstr(row.get("tipo_falta")),
				"estado": caso_estado,
				"status": caso_estado,
				"outcome": outcome,
				"decision": outcome,
				"closure_date": cstr(row.get("fecha_cierre")),
				"closure_summary": cstr(row.get("resumen_cierre")),
				"suspension_start": cstr(row.get("fecha_inicio_suspension")),
				"suspension_end": cstr(row.get("fecha_fin_suspension")),
				"can_close": caso_estado != "Cerrado",
				"afectados_summary": afectados_summary,
				"proxima_accion": proxima_accion,
				"citacion_vencida": citacion_vencida,
				"fecha_ultimo_movimiento": fecha_ultimo_movimiento,
			}
		)

	total_count = len(all_rows)
	# Apply pagination: start offset + limit window
	rows = all_rows[start: start + limit] if limit else all_rows[start:]

	status_summary: dict[str, int] = {}
	decision_summary: dict[str, int] = {}
	for row in all_rows:
		s = row["estado"]
		status_summary[s] = status_summary.get(s, 0) + 1
		if row["outcome"]:
			decision_summary[row["outcome"]] = decision_summary.get(row["outcome"], 0) + 1

	return {
		"status": "success",
		"rows": rows,
		"start": start,
		"summary": {
			"total": total_count,
			"open": status_summary.get("Abierto", 0),
			"en_triage": status_summary.get("En Triage", 0),
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
	"""
	Dispatch effects for a closed Caso Disciplinario or Afectado Disciplinario.

	Accepts either:
	  - Caso Disciplinario (legacy path): reads .empleado, .decision_final, .estado, .fecha_cierre.
	  - Afectado Disciplinario (new path): reads .empleado, .decision_final_afectado, .estado,
	    .fecha_cierre_afectado, .fecha_inicio_suspension, .fecha_fin_suspension.
	"""
	is_afectado = getattr(case_doc, "doctype", None) == "Afectado Disciplinario"

	if is_afectado:
		empleado = getattr(case_doc, "empleado", None)
		if not empleado:
			return {"status": "skipped", "reason": "missing_employee"}
		decision = _normalize_outcome(getattr(case_doc, "decision_final_afectado", None))
		status = cstr(getattr(case_doc, "estado", None)).strip()
		source_doctype = "Afectado Disciplinario"
		source_name = case_doc.name
		fecha_cierre = getattr(case_doc, "fecha_cierre_afectado", None) or nowdate()
		resumen_cierre = cstr(getattr(case_doc, "resumen_cierre_afectado", None)).strip()
	else:
		# Legacy: Caso Disciplinario
		empleado = getattr(case_doc, "empleado", None)
		if not empleado:
			return {"status": "skipped", "reason": "missing_employee"}
		decision = _normalize_outcome(getattr(case_doc, "decision_final", None))
		status = cstr(getattr(case_doc, "estado", None)).strip()
		source_doctype = "Caso Disciplinario"
		source_name = case_doc.name
		fecha_cierre = getattr(case_doc, "fecha_cierre", None) or nowdate()
		resumen_cierre = cstr(getattr(case_doc, "resumen_cierre", None)).strip()

	if status != "Cerrado":
		reverse_retirement_if_clear(employee=empleado, source_doctype=source_doctype, source_name=source_name)
		return _clear_disciplinary_suspension_if_possible(empleado, current_case=source_name)

	if decision == "Terminación":
		_clear_disciplinary_suspension_if_possible(empleado, current_case=source_name)
		# REQ-16-02: submit_employee_retirement must be atomic — rollback if it fails
		# so that the Afectado is not left in Cerrado state without the retirement processed.
		try:
			return employee_retirement_service.submit_employee_retirement(
				employee=empleado,
				last_worked_date=fecha_cierre,
				reason=DISCIPLINARY_TERMINATION_REASON,
				closure_date=fecha_cierre,
				closure_summary=resumen_cierre,
				source_doctype=source_doctype,
				source_name=source_name,
				enforce_access=False,
			)
		except Exception as exc:
			frappe.db.rollback()
			frappe.throw(
				_(
					"No se pudo procesar la terminación del empleado '{0}': {1}. "
					"El cierre del caso ha sido revertido. Intente nuevamente o contacte al administrador."
				).format(empleado, str(exc)),
				frappe.ValidationError,
			)

	reverse_retirement_if_clear(employee=empleado, source_doctype=source_doctype, source_name=source_name)
	if decision == "Suspensión":
		return _sync_case_suspension(case_doc)

	return _clear_disciplinary_suspension_if_possible(empleado, current_case=source_name)


def process_closed_disciplinary_cases() -> dict[str, Any]:
	"""
	Daily scheduler task. Processes all closed disciplinary docs with Suspensión or Terminación.

	Covers:
	  1. Caso Disciplinario (legacy path — cases without Afectado or old cases).
	  2. Afectado Disciplinario (new path — cases with Afectado).
	"""
	processed = []

	# 1. Legacy: Caso Disciplinario
	for row in frappe.get_all(
		"Caso Disciplinario",
		filters={"estado": "Cerrado", "decision_final": ["in", ["Suspensión", "Terminación"]]},
		fields=["name"],
		limit_page_length=0,
	):
		case_doc = frappe.get_doc("Caso Disciplinario", row.name)
		processed.append({"source": "caso", "name": row.name, "result": sync_disciplinary_case_effects(case_doc)})

	# 2. New: Afectado Disciplinario
	for row in frappe.get_all(
		"Afectado Disciplinario",
		filters={"estado": "Cerrado", "decision_final_afectado": ["in", ["Suspensión", "Terminación"]]},
		fields=["name"],
		limit_page_length=0,
	):
		afectado_doc = frappe.get_doc("Afectado Disciplinario", row.name)
		processed.append({"source": "afectado", "name": row.name, "result": sync_disciplinary_case_effects(afectado_doc)})

	return {"status": "ok", "processed": processed, "processed_count": len(processed)}


def _sync_case_suspension(case_doc) -> dict[str, Any]:
	"""
	Syncs suspension state on Ficha Empleado from either:
	  - Caso Disciplinario (legacy): reads .empleado, .fecha_inicio_suspension, .fecha_fin_suspension.
	  - Afectado Disciplinario (new): reads .empleado, .fecha_inicio_suspension, .fecha_fin_suspension.
	Both types have the same field names for suspension dates.
	"""
	today = getdate(nowdate())
	empleado = getattr(case_doc, "empleado", None)
	if not empleado:
		return {"status": "skipped", "reason": "missing_employee"}

	start = getdate(case_doc.fecha_inicio_suspension)
	end = getdate(case_doc.fecha_fin_suspension)
	current_status = cstr(frappe.db.get_value("Ficha Empleado", empleado, "estado")).strip()

	if current_status == "Retirado":
		return {"status": "skipped", "reason": "employee_retired"}

	if start <= today <= end:
		frappe.db.set_value("Ficha Empleado", empleado, "estado", "Suspensión", update_modified=False)
		return {"status": "active", "employee": empleado, "start": str(start), "end": str(end)}

	clear_result = _clear_disciplinary_suspension_if_possible(empleado, current_case=case_doc.name)
	return {
		"status": "scheduled" if today < start else "expired",
		"employee": empleado,
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
	"""
	Returns True if the employee has other active suspension sources besides current_case.

	Checks:
	  1. Caso Disciplinario (legacy) with decision_final=Suspensión.
	  2. Afectado Disciplinario (new) with decision_final_afectado=Suspensión.
	  3. Novedad SST.

	current_case: either a caso name "CD-..." or an afectado name "AFE-..." to exclude.
	"""
	today = getdate(nowdate())

	# 1. Legacy: Caso Disciplinario
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

	# 2. New: Afectado Disciplinario
	for row in frappe.get_all(
		"Afectado Disciplinario",
		filters={"empleado": employee, "estado": "Cerrado", "decision_final_afectado": "Suspensión"},
		fields=["name", "fecha_inicio_suspension", "fecha_fin_suspension"],
		limit_page_length=0,
	):
		if row.name == current_case:
			continue
		if not row.fecha_inicio_suspension or not row.fecha_fin_suspension:
			continue
		if getdate(row.fecha_inicio_suspension) <= today <= getdate(row.fecha_fin_suspension):
			return True

	# 3. Novedad SST
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
