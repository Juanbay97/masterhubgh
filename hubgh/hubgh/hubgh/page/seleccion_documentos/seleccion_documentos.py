import unicodedata

import frappe
from frappe.utils import nowdate, getdate

from hubgh.hubgh.candidate_states import (
	STATE_AFILIACION,
	STATE_DOCUMENTACION,
	STATE_EXAMEN_MEDICO,
	STATE_LISTO_CONTRATAR,
	is_candidate_status,
)
from hubgh.hubgh.display_labels import get_punto_name_map, resolve_candidate_location_labels, resolve_siesa_bank_name
from hubgh.hubgh.document_service import (
	build_candidate_documents_zip,
	ensure_candidate_required_documents,
	get_person_document_rows,
	get_candidate_progress,
	hire_candidate,
	send_candidate_to_labor_relations,
	upload_person_document,
	user_has_any_role,
)
from hubgh.hubgh.permissions import user_can_access_dimension
from hubgh.hubgh.selection_document_types import (
	SELECTION_OPERATIONAL_DOCS,
	canonicalize_selection_document_name,
	get_selection_document_lookup_names,
	get_selection_operational_document_names,
)


logger = frappe.logger("hubgh.candidato")


SELECTION_REQUIRED_DOC_DEFAULTS = {
	row["document_name"]: int(row.get("is_required_for_hiring") or 0) for row in SELECTION_OPERATIONAL_DOCS
}


MEDICAL_CONCEPTS = {"Favorable", "Desfavorable", "Aplazado"}
MEDICAL_ALERT_THRESHOLD_DAYS = 3


def _normalize_text(value):
	text = str(value or "").strip().lower()
	if not text:
		return ""
	return "".join(ch for ch in unicodedata.normalize("NFKD", text) if not unicodedata.combining(ch))


def _validate_selection_access(candidate=None):
	if frappe.session.user == "Administrator":
		return
	if _has_selection_access(frappe.session.user):
		return
	if user_has_any_role(frappe.session.user, "Candidato"):
		if not candidate:
			return
		if frappe.db.get_value("Candidato", candidate, "user") == frappe.session.user:
			return
	if candidate and frappe.db.get_value("Candidato", candidate, "user") == frappe.session.user:
		return
	frappe.throw("No autorizado")


def _can_manage_candidates(user=None):
	user = user or frappe.session.user
	return user == "Administrator" or _has_selection_access(user)


def _has_selection_access(user=None):
	user = user or frappe.session.user
	return user_has_any_role(user, "HR Selection", "Gestión Humana", "GH - Bandeja General", "Gerente GH")


def _has_medical_exam_access(user=None):
	user = user or frappe.session.user
	return user_has_any_role(user, "HR SST", "SST", "HR Selection", "Gestión Humana", "GH - Bandeja General", "Gerente GH")


def _has_labor_relations_access(user=None):
	user = user or frappe.session.user
	return user_has_any_role(user, "HR Labor Relations", "GH - RRLL", "Relaciones Laborales Jefe", "Gerente GH")


def _candidate_apellidos_fallback(row):
	apellidos = (row.get("apellidos") if isinstance(row, dict) else getattr(row, "apellidos", None)) or ""
	if str(apellidos).strip():
		return str(apellidos).strip()
	primer = (row.get("primer_apellido") if isinstance(row, dict) else getattr(row, "primer_apellido", None)) or ""
	segundo = (row.get("segundo_apellido") if isinstance(row, dict) else getattr(row, "segundo_apellido", None)) or ""
	return " ".join([p.strip() for p in [primer, segundo] if p and str(p).strip()]).strip()


def _candidate_pdv_name_map(rows):
	return get_punto_name_map([(row.get("pdv_destino") if isinstance(row, dict) else getattr(row, "pdv_destino", None)) for row in (rows or [])])


def _has_uploaded_document(candidate, document_type):
	rows = get_person_document_rows(
		"Candidato",
		candidate,
		fields=["name"],
		extra_filters={
			"document_type": ["in", get_selection_document_lookup_names(document_type)],
			"status": ["in", ["Subido", "Aprobado"]],
			"file": ["is", "set"],
		},
		limit_page_length=50,
	)
	return bool(rows)


def _selection_required_docs():
	canonical_names = get_selection_operational_document_names()
	rows = frappe.get_all(
		"Document Type",
		filters={
			"name": ["in", canonical_names],
			"is_active": 1,
			"applies_to": ["in", ["Candidato", "Ambos"]],
		},
		fields=["name", "is_required_for_hiring"],
	)
	by_name = {row.name: row for row in rows}
	def _required_value(name):
		row = by_name.get(name)
		return int(((row.is_required_for_hiring if row else None) or SELECTION_REQUIRED_DOC_DEFAULTS[name]) or 0)
	return [
		{
			"document_type": name,
			"required": _required_value(name),
		}
		for name in canonical_names
	]


def _selection_docs_status(candidate):
	doc_status = []
	for row in _selection_required_docs():
		doc_type = row["document_type"]
		ok = _has_uploaded_document(candidate, doc_type)
		doc_status.append({
			"document_type": doc_type,
			"required": int(row.get("required") or 0),
			"uploaded_ok": ok,
		})
	return doc_status


def _active_candidate_document_types():
	rows = frappe.get_all(
		"Document Type",
		filters={"is_active": 1, "applies_to": ["in", ["Candidato", "Ambos"]]},
		fields=["name", "document_name", "is_required_for_hiring"],
		order_by="is_required_for_hiring desc, document_name asc, name asc",
	)
	return [
		{
			"name": row.name,
			"label": row.document_name or row.name,
			"required_for_hiring": int(row.is_required_for_hiring or 0),
		}
		for row in rows
	]


def _validate_candidate_document_type(document_type):
	allowed = {row["name"] for row in _active_candidate_document_types()}
	if document_type not in allowed:
		frappe.throw("Tipo de documento inválido o inactivo para candidatos.")


def _resolve_medical_document_type(document_type=None):
	logger.info(
		"resolve_medical_document_type:start",
		extra={
			"requested_document_type": document_type,
			"user": frappe.session.user,
		},
	)
	if document_type and frappe.db.exists("Document Type", document_type):
		logger.info(
			"resolve_medical_document_type:explicit_match",
			extra={"document_type": document_type},
		)
		return document_type

	rows = frappe.get_all(
		"Document Type",
		filters={"is_active": 1, "applies_to": ["in", ["Candidato", "Ambos"]]},
		fields=["name", "document_name"],
	)
	legacy_priority_names = {
		"examen medico",
		"concepto medico",
		"concepto medico ocupacional",
		"aptitud medica",
	}

	for row in rows:
		name_norm = _normalize_text(row.name)
		doc_name_norm = _normalize_text(row.document_name)
		if name_norm in legacy_priority_names or doc_name_norm in legacy_priority_names:
			logger.info(
				"resolve_medical_document_type:legacy_priority_match",
				extra={
					"document_type": row.name,
					"document_name": row.document_name,
				},
			)
			return row.name

	for row in rows:
		label = _normalize_text(f"{row.name or ''} {row.document_name or ''}")
		if (
			("examen" in label and "med" in label)
			or ("concepto" in label and "med" in label)
			or ("aptitud" in label and "med" in label)
		):
			logger.info(
				"resolve_medical_document_type:pattern_match",
				extra={
					"document_type": row.name,
					"document_name": row.document_name,
				},
			)
			return row.name

	medical_like = [
		{
			"name": r.name,
			"document_name": r.document_name,
		}
		for r in rows
		if any(token in _normalize_text(f"{r.name or ''} {r.document_name or ''}") for token in ["med", "examen", "concepto", "aptitud"])
	]
	logger.warning(
		"resolve_medical_document_type:not_found",
		extra={
			"requested_document_type": document_type,
			"available_medical_like": medical_like,
			"total_active_candidate_doc_types": len(rows),
		},
	)

	frappe.throw("No existe un tipo de documento de examen médico activo para candidatos.")


def _candidate_has_medical_exam_doc(candidate):
	rows = get_person_document_rows(
		"Candidato",
		candidate,
		fields=["document_type"],
		extra_filters={"status": ["in", ["Subido", "Aprobado"]], "file": ["is", "set"]},
	)
	for row in rows:
		doc_type = _normalize_text(row.document_type)
		if (
			("examen" in doc_type and "med" in doc_type)
			or ("concepto" in doc_type and "med" in doc_type)
			or ("aptitud" in doc_type and "med" in doc_type)
		):
			return True
	return False


@frappe.whitelist()
def list_candidates(search=None):
	_validate_selection_access()
	filters = {}
	is_manager = _can_manage_candidates()
	if not is_manager:
		filters["user"] = frappe.session.user
	if search:
		filters["numero_documento"] = ["like", f"%{search}%"]

	rows = frappe.get_all(
		"Candidato",
		filters=filters,
		fields=[
			"name",
			"nombres",
			"apellidos",
			"primer_apellido",
			"segundo_apellido",
			"numero_documento",
			"pdv_destino",
			"cargo_postulado",
			"creation",
			"estado_proceso",
			"concepto_medico",
			"fecha_envio_examen_medico",
		],
		order_by="creation desc",
	)
	pdv_name_map = _candidate_pdv_name_map(rows)
	data = []
	for row in rows:
		if is_candidate_status(row.estado_proceso, "Rechazado", STATE_AFILIACION, STATE_LISTO_CONTRATAR, "Contratado"):
			continue
		ensure_candidate_required_documents(row.name)
		progress = get_candidate_progress(row.name)
		sagrilaft_ok = _has_uploaded_document(row.name, "SAGRILAFT")
		data.append({
			"name": row.name,
			"full_name": f"{row.nombres or ''} {_candidate_apellidos_fallback(row) or ''}".strip(),
			"numero_documento": row.numero_documento,
			"pdv_destino": row.pdv_destino,
			"pdv_destino_nombre": pdv_name_map.get(row.pdv_destino, row.pdv_destino or ""),
			"cargo_postulado": row.cargo_postulado,
			"creation": row.creation,
			"estado_proceso": row.estado_proceso,
			"concepto_medico": row.concepto_medico,
			"fecha_envio_examen_medico": row.fecha_envio_examen_medico,
			"sagrilaft_ok": sagrilaft_ok,
			"avance_porcentaje": progress["percent"],
			"documentos_ok": progress["required_ok"],
			"documentos_total": progress["required_total"],
			"completo": progress["is_complete"],
			"can_manage": is_manager,
		})
	return data


@frappe.whitelist()
def candidate_detail(candidate):
	_validate_selection_access(candidate)
	ensure_candidate_required_documents(candidate)
	cand = frappe.get_doc("Candidato", candidate)

	docs = get_person_document_rows(
		"Candidato",
		candidate,
		fields=["name", "document_type", "status", "file", "uploaded_by", "uploaded_on", "approved_by", "approved_on", "notes"],
		order_by="modified desc",
	)
	progress = get_candidate_progress(candidate)
	selection_docs = []
	candidate_docs = []
	selection_doc_names = set(get_selection_operational_document_names())
	for d in docs:
		if canonicalize_selection_document_name(d.document_type) in selection_doc_names:
			selection_docs.append(d)
		else:
			candidate_docs.append(d)
	selection_doc_status = _selection_docs_status(candidate)
	selection_docs_complete = all((not row["required"]) or row["uploaded_ok"] for row in selection_doc_status)
	upload_doc_types = _active_candidate_document_types()
	location_labels = resolve_candidate_location_labels(
		pais=cand.procedencia_pais,
		departamento=cand.procedencia_departamento,
		ciudad=cand.procedencia_ciudad,
	)
	pdv_destino_nombre = get_punto_name_map([getattr(cand, "pdv_destino", None)]).get(getattr(cand, "pdv_destino", None), getattr(cand, "pdv_destino", "") or "") if getattr(cand, "pdv_destino", None) else ""
	return {
		"candidate": {
			"name": cand.name,
			"full_name": f"{cand.nombres or ''} {_candidate_apellidos_fallback(cand) or ''}".strip(),
			"numero_documento": cand.numero_documento,
			"estado_proceso": cand.estado_proceso,
			"concepto_medico": cand.concepto_medico,
			"fecha_envio_examen_medico": cand.fecha_envio_examen_medico,
			"direccion": cand.direccion,
			"barrio": cand.barrio,
			"ciudad": cand.ciudad,
			"localidad": cand.localidad or cand.localidad_otras,
			"procedencia_pais": location_labels.get("pais") or cand.procedencia_pais,
			"procedencia_pais_codigo": cand.procedencia_pais,
			"procedencia_departamento": location_labels.get("departamento") or cand.procedencia_departamento,
			"procedencia_departamento_codigo": cand.procedencia_departamento,
			"procedencia_ciudad": location_labels.get("ciudad") or cand.procedencia_ciudad,
			"procedencia_ciudad_codigo": cand.procedencia_ciudad,
			"banco_siesa": resolve_siesa_bank_name(cand.banco_siesa),
			"banco_siesa_codigo": cand.banco_siesa,
			"pdv_destino": getattr(cand, "pdv_destino", None),
			"pdv_destino_nombre": pdv_destino_nombre,
			"tipo_cuenta_bancaria": cand.tipo_cuenta_bancaria,
			"numero_cuenta_bancaria": cand.numero_cuenta_bancaria,
		},
		"progress": progress,
		"documents": docs,
		"candidate_documents": candidate_docs,
		"selection_documents": selection_docs,
		"selection_doc_status": selection_doc_status,
		"selection_docs_complete": selection_docs_complete,
		"upload_doc_types": upload_doc_types,
	}


@frappe.whitelist()
def list_upload_document_types():
	_validate_selection_access()
	return _active_candidate_document_types()


@frappe.whitelist()
def upload_candidate_document(candidate, document_type, file_url, notes=None):
	_validate_selection_access(candidate)
	_validate_candidate_document_type(document_type)
	numero_documento = frappe.db.get_value("Candidato", candidate, "numero_documento")
	doc = upload_person_document(
		"Candidato",
		candidate,
		document_type,
		file_url,
		notes,
		numero_documento=numero_documento,
	)
	if getattr(frappe.local, "message_log", None):
		frappe.local.message_log = []
	return {"name": doc.name, "status": doc.status}


@frappe.whitelist()
def send_to_labor_relations(candidate, pdv_destino=None, fecha_tentativa_ingreso=None):
	_validate_selection_access(candidate)
	cand = frappe.get_doc("Candidato", candidate)
	if (cand.concepto_medico or "") != "Favorable":
		frappe.throw("No se puede enviar a RRLL: el concepto médico debe ser Favorable.")
	if not _has_uploaded_document(candidate, "SAGRILAFT"):
		frappe.throw("No se puede enviar a RRLL: falta documento SAGRILAFT.")
	return send_candidate_to_labor_relations(candidate, pdv_destino=pdv_destino, fecha_tentativa_ingreso=fecha_tentativa_ingreso)


@frappe.whitelist()
def send_to_medical_exam(candidate):
	_validate_selection_access(candidate)
	if not _can_manage_candidates():
		frappe.throw("No autorizado")
	frappe.db.set_value(
		"Candidato",
		candidate,
		{
			"estado_proceso": STATE_EXAMEN_MEDICO,
			"fecha_envio_examen_medico": nowdate(),
			"concepto_medico": "Pendiente",
		},
	)
	return {"ok": True, "status": STATE_EXAMEN_MEDICO}


@frappe.whitelist()
def reject_candidate(candidate, motivo_rechazo):
	_validate_selection_access(candidate)
	if not _can_manage_candidates():
		frappe.throw("No autorizado")
	motivo = (motivo_rechazo or "").strip()
	if not motivo:
		frappe.throw("El motivo de rechazo es obligatorio.")

	frappe.db.set_value(
		"Candidato",
		candidate,
		{
			"estado_proceso": "Rechazado",
			"motivo_rechazo": motivo,
			"concepto_medico": "Desfavorable"
			if is_candidate_status(frappe.db.get_value("Candidato", candidate, "estado_proceso"), STATE_EXAMEN_MEDICO)
			else frappe.db.get_value("Candidato", candidate, "concepto_medico"),
		},
	)

	user = frappe.db.get_value("Candidato", candidate, "user")
	if user and frappe.db.exists("User", user):
		frappe.db.set_value("User", user, "enabled", 0)

	return {"ok": True, "status": "Rechazado"}


def _medical_alert_responsible():
	for role in ("HR SST", "SST", "System Manager"):
		users = frappe.get_all("Has Role", filters={"role": role, "parenttype": "User"}, pluck="parent", limit=1)
		if users:
			return users[0]
	return None


@frappe.whitelist()
def list_medical_exam_candidates(search=None):
	if frappe.session.user != "Administrator" and not _has_medical_exam_access(frappe.session.user):
		frappe.throw("No autorizado")
	can_view_clinical = user_can_access_dimension("clinical", frappe.session.user)

	filters = {"estado_proceso": ["in", [STATE_EXAMEN_MEDICO, "En Examen Médico"]]}
	if search:
		filters["numero_documento"] = ["like", f"%{search}%"]

	rows = frappe.get_all(
		"Candidato",
		filters=filters,
		fields=[
			"name",
			"nombres",
			"apellidos",
			"primer_apellido",
			"segundo_apellido",
			"numero_documento",
			"pdv_destino",
			"cargo_postulado",
			"fecha_envio_examen_medico",
			"concepto_medico",
			"creation",
		],
		order_by="fecha_envio_examen_medico asc, creation asc",
	)
	pdv_name_map = _candidate_pdv_name_map(rows)

	responsable = _medical_alert_responsible()
	today = getdate(nowdate())
	result = [{
		"name": row.name,
		"full_name": f"{row.nombres or ''} {_candidate_apellidos_fallback(row) or ''}".strip(),
		"numero_documento": row.numero_documento,
		"pdv_destino": row.pdv_destino,
		"pdv_destino_nombre": pdv_name_map.get(row.pdv_destino, row.pdv_destino or ""),
		"cargo_postulado": row.cargo_postulado,
		"fecha_envio_examen_medico": row.fecha_envio_examen_medico,
		"concepto_medico": row.concepto_medico,
		"has_exam_document": _candidate_has_medical_exam_doc(row.name),
		"exam_scope": "vigente",
		"clinical_visible": bool(can_view_clinical),
		"dias_pendientes": max((today - getdate(row.fecha_envio_examen_medico)).days, 0) if row.fecha_envio_examen_medico else 0,
		"responsable_alerta": responsable,
	} for row in rows if (row.concepto_medico or "Pendiente") in {"", "Pendiente"}]

	# S6.1: vigente queue first with additive metadata for consumers.
	result.sort(key=lambda r: str(r.get("fecha_envio_examen_medico") or ""))
	for row in result:
		dias = int(row.get("dias_pendientes") or 0)
		row["alerta_vencimiento"] = dias >= MEDICAL_ALERT_THRESHOLD_DAYS
		row["fecha_alerta_sugerida"] = row.get("fecha_envio_examen_medico")
	return result


@frappe.whitelist()
def list_medical_exam_history(search=None):
	if frappe.session.user != "Administrator" and not _has_medical_exam_access(frappe.session.user):
		frappe.throw("No autorizado")
	can_view_clinical = user_can_access_dimension("clinical", frappe.session.user)

	filters = {"concepto_medico": ["in", ["Favorable", "Desfavorable", "Aplazado"]]}
	if search:
		filters["numero_documento"] = ["like", f"%{search}%"]

	rows = frappe.get_all(
		"Candidato",
		filters=filters,
		fields=[
			"name",
			"nombres",
			"apellidos",
			"primer_apellido",
			"segundo_apellido",
			"numero_documento",
			"pdv_destino",
			"cargo_postulado",
			"fecha_envio_examen_medico",
			"concepto_medico",
			"estado_proceso",
			"modified",
		],
		order_by="modified desc",
	)
	pdv_name_map = _candidate_pdv_name_map(rows)

	history = [{
		"name": row.name,
		"full_name": f"{row.nombres or ''} {_candidate_apellidos_fallback(row) or ''}".strip(),
		"numero_documento": row.numero_documento,
		"pdv_destino": row.pdv_destino,
		"pdv_destino_nombre": pdv_name_map.get(row.pdv_destino, row.pdv_destino or ""),
		"cargo_postulado": row.cargo_postulado,
		"fecha_envio_examen_medico": row.fecha_envio_examen_medico,
		"concepto_medico": row.concepto_medico if can_view_clinical else "Restringido",
		"estado_proceso": row.estado_proceso,
		"has_exam_document": _candidate_has_medical_exam_doc(row.name),
		"exam_scope": "historico",
		"evaluado_en": row.modified,
		"clinical_visible": bool(can_view_clinical),
	} for row in rows]

	# S6.1: keep history access explicit and deterministic.
	history.sort(key=lambda r: str(r.get("evaluado_en") or ""), reverse=True)
	return history


@frappe.whitelist()
def upload_medical_exam_document(candidate, file_url, notes=None, document_type=None):
	if frappe.session.user != "Administrator" and not _has_medical_exam_access(frappe.session.user):
		frappe.throw("No autorizado")
	doc_type = _resolve_medical_document_type(document_type=document_type)
	logger.info(
		"upload_medical_exam_document:resolved",
		extra={
			"candidate": candidate,
			"document_type": doc_type,
			"user": frappe.session.user,
		},
	)
	numero_documento = frappe.db.get_value("Candidato", candidate, "numero_documento")
	doc = upload_person_document(
		"Candidato",
		candidate,
		doc_type,
		file_url,
		notes,
		numero_documento=numero_documento,
	)
	if getattr(frappe.local, "message_log", None):
		frappe.local.message_log = []
	return {"name": doc.name, "status": doc.status, "document_type": doc_type}


@frappe.whitelist()
def set_medical_concept(candidate, concepto_medico, notes=None):
	if frappe.session.user != "Administrator" and not _has_medical_exam_access(frappe.session.user):
		frappe.throw("No autorizado")
	concept = (concepto_medico or "").strip().title()
	if concept not in MEDICAL_CONCEPTS:
		frappe.throw("Concepto médico inválido. Usa Favorable, Desfavorable o Aplazado.")

	updates = {"concepto_medico": concept}
	updates["estado_proceso"] = STATE_EXAMEN_MEDICO
	frappe.db.set_value("Candidato", candidate, updates)

	if notes:
		frappe.get_doc({
			"doctype": "Comment",
			"comment_type": "Comment",
			"reference_doctype": "Candidato",
			"reference_name": candidate,
			"content": f"Concepto médico actualizado a {concept}: {notes}",
		}).insert(ignore_permissions=True)

	return {
		"ok": True,
		"concepto_medico": concept,
		"estado_proceso": updates["estado_proceso"],
		"next_recommended": "send_to_labor_relations" if concept == "Favorable" else None,
	}


@frappe.whitelist()
def list_rejected_candidates(search=None):
	if frappe.session.user != "Administrator" and not _has_selection_access(frappe.session.user):
		frappe.throw("No autorizado")

	filters = {"estado_proceso": "Rechazado"}
	if search:
		filters["numero_documento"] = ["like", f"%{search}%"]

	rows = frappe.get_all(
		"Candidato",
		filters=filters,
		fields=[
			"name",
			"nombres",
			"apellidos",
			"primer_apellido",
			"segundo_apellido",
			"numero_documento",
			"motivo_rechazo",
			"modified",
		],
		order_by="modified desc",
	)

	return [{
		"name": row.name,
		"full_name": f"{row.nombres or ''} {_candidate_apellidos_fallback(row) or ''}".strip(),
		"numero_documento": row.numero_documento,
		"motivo_rechazo": row.motivo_rechazo,
		"fecha_rechazo": row.modified,
	} for row in rows]


@frappe.whitelist()
def reactivate_candidate(candidate):
	_validate_selection_access(candidate)
	if not _can_manage_candidates():
		frappe.throw("No autorizado")

	frappe.db.set_value(
		"Candidato",
		candidate,
		{
			"estado_proceso": STATE_DOCUMENTACION,
			"motivo_rechazo": None,
		},
	)

	user = frappe.db.get_value("Candidato", candidate, "user")
	if user and frappe.db.exists("User", user):
		frappe.db.set_value("User", user, "enabled", 1)

	return {"ok": True, "status": STATE_DOCUMENTACION}


@frappe.whitelist()
def labor_relations_candidates():
	if frappe.session.user != "Administrator" and not _has_labor_relations_access(frappe.session.user):
		frappe.throw("No autorizado")

	rows = frappe.get_all(
		"Candidato",
		filters={"estado_proceso": ["in", [STATE_LISTO_CONTRATAR, "Listo para Contratar"]]},
		fields=["name", "nombres", "apellidos", "primer_apellido", "segundo_apellido", "numero_documento", "creation", "estado_proceso"],
		order_by="creation asc",
	)
	return [{
		"name": r.name,
		"full_name": f"{r.nombres or ''} {_candidate_apellidos_fallback(r) or ''}".strip(),
		"numero_documento": r.numero_documento,
		"creation": r.creation,
		"estado_proceso": r.estado_proceso,
	} for r in rows]


@frappe.whitelist()
def attach_contract(candidate, file_url, notes=None):
	if frappe.session.user != "Administrator" and not _has_labor_relations_access(frappe.session.user):
		frappe.throw("No autorizado")
	return upload_person_document("Candidato", candidate, "Contrato", file_url, notes).name


@frappe.whitelist()
def mark_hired(candidate):
	return hire_candidate(candidate)


@frappe.whitelist()
def employee_folder(employee):
	rows = frappe.get_all(
		"Person Document",
		filters={"employee": employee},
		fields=["name", "document_type", "status", "file", "uploaded_by", "uploaded_on", "approved_by", "approved_on", "notes", "person", "person_type"],
		order_by="modified desc",
	)
	return rows


@frappe.whitelist()
def download_candidate_documents_zip(candidate):
	_validate_selection_access(candidate)
	return build_candidate_documents_zip(candidate)
