import json
import re

import frappe
from frappe.utils import now_datetime

from hubgh.hubgh.people_ops_flags import resolve_backbone_mode


SUPPORTED_AREAS = {"seleccion", "rrll", "sst", "bienestar", "documental", "operacion"}
SUPPORTED_SENSITIVITY = {"operational", "documental", "disciplinary", "clinical", "financial"}
AREA_ALIASES = {
	"nomina": "nomina",
	"payroll": "nomina",
}
SENSITIVITY_ALIASES = {
	"sst_clinical": "clinical",
	"payroll_clinical": "clinical",
	"payroll_sensible": "financial",
	"sensitive": "disciplinary",
}

SUPPORTED_AREAS = SUPPORTED_AREAS | {"nomina"}


def _doc_value(doc, fieldname, default=None):
	if isinstance(doc, dict):
		return doc.get(fieldname, default)
	return getattr(doc, fieldname, default)


def _build_event_key(source_doctype, source_name, taxonomy):
	return f"{str(source_doctype or '').strip()}::{str(source_name or '').strip()}::{str(taxonomy or '').strip().lower()}"


def _normalize_area(area):
	value = str(area or "operacion").strip().lower()
	return AREA_ALIASES.get(value, value)


def _normalize_sensitivity(sensitivity):
	value = str(sensitivity or "operational").strip().lower()
	value = SENSITIVITY_ALIASES.get(value, value)
	if value in SUPPORTED_SENSITIVITY:
		return value
	return "operational"


def _normalize_taxonomy(area, taxonomy):
	tax = str(taxonomy or "").strip().lower()
	prefix = f"{area}."
	if tax.startswith(prefix):
		return tax, False
	if not tax:
		return f"{area}.evento", True
	tail = tax.split(".", 1)[-1].strip()
	if not tail:
		tail = "evento"
	return f"{area}.{tail}", True


def publish_people_ops_event(payload):
	raw_area = str(payload.get("area") or "operacion").strip().lower()
	area = _normalize_area(raw_area)
	mode = resolve_backbone_mode(area if area in SUPPORTED_AREAS else None)
	warnings = []
	errors = []

	if area not in SUPPORTED_AREAS:
		errors.append(f"unsupported_area:{raw_area or 'empty'}")
		area = "operacion"

	sensitivity = _normalize_sensitivity(payload.get("sensitivity"))
	if str(payload.get("sensitivity") or "").strip().lower() not in SUPPORTED_SENSITIVITY:
		warnings.append(f"sensitivity_normalized:{payload.get('sensitivity') or 'empty'}->{sensitivity}")

	taxonomy, taxonomy_rewritten = _normalize_taxonomy(area, payload.get("taxonomy"))
	if taxonomy_rewritten:
		warnings.append(f"taxonomy_normalized:{payload.get('taxonomy') or 'empty'}->{taxonomy}")

	if mode == "off":
		return None
	if errors and mode == "enforce":
		frappe.logger("hubgh.people_ops_backbone").warning(
			"people_ops_event_rejected",
			extra={
				"area": raw_area,
				"mode": mode,
				"errors": errors,
			},
		)
		return None

	if errors:
		warnings.extend(errors)

	if not frappe.db.exists("DocType", "People Ops Event"):
		return None

	event_key = str(payload.get("event_key") or "").strip()
	if not event_key:
		event_key = _build_event_key(payload.get("source_doctype"), payload.get("source_name"), taxonomy)

	existing = frappe.db.exists("People Ops Event", {"event_key": event_key})
	if existing:
		return existing

	refs_json = json.dumps(payload.get("refs") or {}, ensure_ascii=True, sort_keys=True)
	row = {
		"doctype": "People Ops Event",
		"event_key": event_key,
		"persona": payload.get("persona"),
		"area": area,
		"taxonomy": taxonomy,
		"sensitivity": sensitivity,
		"state": payload.get("state") or "",
		"severity": payload.get("severity") or "",
		"source_doctype": payload.get("source_doctype") or "Unknown",
		"source_name": payload.get("source_name") or "Unknown",
		"refs_json": refs_json,
		"occurred_on": payload.get("occurred_on") or now_datetime(),
		"backbone_mode": mode,
		"contract_version": payload.get("contract_version") or "v1",
		"warning_message": payload.get("warning_message") or ("; ".join(warnings) if mode == "warn" and warnings else ""),
	}

	try:
		doc = frappe.get_doc(row)
		doc.insert(ignore_permissions=True)
		return doc.name
	except Exception:
		frappe.log_error(frappe.get_traceback(), "people_ops_event_publish_failed")
		return None


def publish_from_gh_novedad(doc, method=None):
	descripcion = str(_doc_value(doc, "descripcion", "") or "")
	tipo = str(_doc_value(doc, "tipo", "Otro") or "Otro")
	is_ingreso = "ingreso formalizado" in descripcion.lower()
	persona = _doc_value(doc, "persona")
	refs = {
		"punto": _doc_value(doc, "punto"),
		"cola_destino": _doc_value(doc, "cola_destino"),
	}

	if is_ingreso:
		refs.update(_resolve_ingreso_lineage_refs(persona=persona, descripcion=descripcion))

	return publish_people_ops_event(
		{
			"persona": persona,
			"area": "rrll" if is_ingreso else "operacion",
			"taxonomy": "rrll.ingreso_formalizado" if is_ingreso else f"operacion.gh_novedad.{tipo.strip().lower()}",
			"sensitivity": "operational",
			"state": _doc_value(doc, "estado"),
			"severity": tipo,
			"source_doctype": "GH Novedad",
			"source_name": _doc_value(doc, "name"),
			"refs": refs,
			"occurred_on": _doc_value(doc, "fecha_inicio"),
		}
	)


def _resolve_ingreso_lineage_refs(persona=None, descripcion=None):
	refs = {}
	if persona and frappe.db.exists("Ficha Empleado", persona):
		candidate = frappe.db.get_value("Ficha Empleado", persona, "candidato_origen")
		if candidate:
			refs["candidate"] = candidate
			refs["lineage"] = {
				"candidate": candidate,
				"employee": persona,
			}

	match = re.search(r"contrato\s+([\w\-]+)", str(descripcion or ""), flags=re.IGNORECASE)
	if match:
		refs["contrato"] = match.group(1)

	return refs


def publish_from_novedad_sst(doc, method=None):
	return publish_people_ops_event(
		{
			"persona": _doc_value(doc, "empleado"),
			"area": "sst",
			"taxonomy": f"sst.novedad.{str(_doc_value(doc, 'tipo_novedad', 'otro') or 'otro').strip().lower()}",
			"sensitivity": "clinical",
			"state": _doc_value(doc, "estado"),
			"severity": _doc_value(doc, "tipo_novedad"),
			"source_doctype": "Novedad SST",
			"source_name": _doc_value(doc, "name"),
			"refs": {
				"punto": _doc_value(doc, "punto_venta"),
			},
			"occurred_on": _doc_value(doc, "fecha_inicio"),
		}
	)


def publish_from_caso_disciplinario(doc, method=None):
	estado = _doc_value(doc, "estado")
	is_closed = str(estado or "").strip().lower() == "cerrado"
	taxonomy = "rrll.disciplinario.cierre" if is_closed else "rrll.disciplinario.caso"
	return publish_people_ops_event(
		{
			"persona": _doc_value(doc, "empleado"),
			"area": "rrll",
			"taxonomy": taxonomy,
			"sensitivity": "disciplinary",
			"state": estado,
			"severity": _doc_value(doc, "tipo_falta"),
			"source_doctype": "Caso Disciplinario",
			"source_name": _doc_value(doc, "name"),
			"refs": {
				"punto": _doc_value(doc, "punto_venta"),
				"decision_final": _doc_value(doc, "decision_final"),
				"fecha_cierre": _doc_value(doc, "fecha_cierre"),
				"closure_auditable": bool(is_closed and _doc_value(doc, "decision_final") and _doc_value(doc, "fecha_cierre")),
			},
			"occurred_on": _doc_value(doc, "fecha_incidente"),
		}
	)


def publish_from_bienestar_compromiso(doc, method=None):
	return publish_people_ops_event(
		{
			"persona": _doc_value(doc, "ficha_empleado"),
			"area": "bienestar",
			"taxonomy": "bienestar.compromiso",
			"sensitivity": "operational",
			"state": _doc_value(doc, "estado"),
			"severity": "sin_mejora" if _doc_value(doc, "sin_mejora") else "con_mejora",
			"source_doctype": "Bienestar Compromiso",
			"source_name": _doc_value(doc, "name"),
			"refs": {
				"gh_novedad": _doc_value(doc, "gh_novedad"),
			},
			"occurred_on": _doc_value(doc, "fecha_compromiso"),
		}
	)


def publish_from_bienestar_alerta(doc, method=None):
	return publish_people_ops_event(
		{
			"persona": _doc_value(doc, "ficha_empleado"),
			"area": "bienestar",
			"taxonomy": "bienestar.alerta",
			"sensitivity": "operational",
			"state": _doc_value(doc, "estado"),
			"severity": _doc_value(doc, "prioridad") or _doc_value(doc, "tipo_alerta"),
			"source_doctype": "Bienestar Alerta",
			"source_name": _doc_value(doc, "name"),
			"refs": {
				"tipo_alerta": _doc_value(doc, "tipo_alerta"),
			},
			"occurred_on": _doc_value(doc, "fecha_alerta"),
		}
	)


def publish_from_person_document(doc, method=None):
	persona = _doc_value(doc, "employee") or _doc_value(doc, "person")
	return publish_people_ops_event(
		{
			"persona": persona,
			"area": "documental",
			"taxonomy": "documental.person_document",
			"sensitivity": "documental",
			"state": _doc_value(doc, "status"),
			"severity": _doc_value(doc, "document_type"),
			"source_doctype": "Person Document",
			"source_name": _doc_value(doc, "name"),
			"refs": {
				"person_type": _doc_value(doc, "person_type"),
				"person": _doc_value(doc, "person"),
			},
			"occurred_on": _doc_value(doc, "modified"),
		}
	)


def reconcile_people_ops_events_warn():
	if not frappe.db.exists("DocType", "People Ops Event"):
		return {"status": "skip", "reason": "doctype_missing", "processed": 0}

	mode = resolve_backbone_mode()
	if mode == "off":
		return {"status": "skip", "reason": "mode_off", "processed": 0}

	processed = frappe.db.count("People Ops Event", {"backbone_mode": "warn"})
	return {"status": "ok", "processed": int(processed or 0), "mode": mode}
