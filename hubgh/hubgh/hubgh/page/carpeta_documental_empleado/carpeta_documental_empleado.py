import io
import hashlib
import os
import re
import unicodedata
import zipfile
from datetime import date

import frappe
from frappe.utils import cint, getdate, now_datetime
from frappe.utils.file_manager import save_file

from hubgh.hubgh.document_service import build_employee_documents_zip
from hubgh.hubgh.role_matrix import user_has_any_role


def _validate_folder_access(employee=None):
	if frappe.session.user == "Administrator":
		return
	if user_has_any_role(frappe.session.user, "System Manager", "HR Labor Relations", "GH - RRLL", "Relaciones Laborales Jefe", "Gerente GH"):
		return
	if employee and user_has_any_role(frappe.session.user, "Empleado"):
		user_employee = frappe.db.get_value("User", frappe.session.user, "employee")
		if user_employee and str(user_employee) == str(employee):
			return
	frappe.throw("No autorizado", frappe.PermissionError)


def _has_folder_write_access(user=None):
	user = user or frappe.session.user
	if user == "Administrator":
		return True
	return user_has_any_role(user, "Relaciones Laborales Jefe")


def _validate_folder_write_access(employee=None):
	_validate_folder_access(employee)
	if _has_folder_write_access():
		return
	frappe.throw("Solo Jefe RRLL puede cargar o reemplazar documentos en la carpeta documental.", frappe.PermissionError)


def _is_expired(has_expiry, valid_until):
	if not cint(has_expiry) or not valid_until:
		return False
	return getdate(valid_until) < getdate(date.today().isoformat())


def _normalize_text(value):
	text = unicodedata.normalize("NFKD", str(value or "").strip().lower())
	text = "".join(ch for ch in text if not unicodedata.combining(ch))
	return re.sub(r"\s+", " ", text)


def _field_value(row, key, default=None):
	if isinstance(row, dict):
		return row.get(key, default)
	return getattr(row, key, default)


LEGACY_PLACEHOLDER_TYPES = {"carpeta"}
DERIVED_SECTION_KEYS = {"sst_documents", "contract_documents", "disciplinary_documents"}
SOURCE_PRIORITY = {
	"Person Document": 300,
	"Contrato": 200,
	"Novedad SST": 200,
	"Caso Disciplinario": 200,
	"Persona Documento": 100,
}


def _mk_folder_item(
	section_key,
	label,
	file_url=None,
	status="Vigente",
	uploaded_on=None,
	uploaded_by=None,
	source_doctype=None,
	source_name=None,
	is_editable=0,
):
	return {
		"person_document": None,
		"document_type": label,
		"document_label": label,
		"has_expiry": 0,
		"issue_date": None,
		"valid_until": None,
		"file": file_url,
		"uploaded_on": uploaded_on,
		"uploaded_by": uploaded_by,
		"status": status,
		"is_missing": 0 if file_url else 1,
		"is_expired": 0,
		"is_extra": 1,
		"section_key": section_key,
		"source_doctype": source_doctype,
		"source_name": source_name,
		"is_editable": cint(is_editable),
	}


def _empty_extra_sections():
	return {
		"selection_rrll_documents": [],
		"sst_documents": [],
		"contract_documents": [],
		"disciplinary_documents": [],
		"other_documents": [],
	}


def _resolve_section_key(label=None, source_doctype=None):
	label = _normalize_text(label)
	source_doctype = _normalize_text(source_doctype)

	if source_doctype == _normalize_text("Contrato"):
		return "contract_documents"
	if source_doctype == _normalize_text("Novedad SST"):
		return "sst_documents"
	if source_doctype == _normalize_text("Caso Disciplinario"):
		return "disciplinary_documents"

	if any(k in label for k in ["concepto medico", "examen medico", "incapacidad", "sst", "recomendacion medica"]):
		return "sst_documents"
	if any(k in label for k in ["contrato", "otro si", "otrosi", "anexo", "adenda"]):
		return "contract_documents"
	if any(k in label for k in ["disciplin", "llamado de atencion", "sancion"]):
		return "disciplinary_documents"
	if any(k in label for k in ["carta oferta", "sagrilaft", "afiliacion", "certificado", "autorizacion", "hoja de vida", "referencia", "fotocopia"]):
		return "selection_rrll_documents"
	return "other_documents"


def _is_placeholder_document(label):
	return _normalize_text(label) in LEGACY_PLACEHOLDER_TYPES


def _has_archival_value(item):
	label = item.get("document_label") or item.get("document_type")
	if _is_placeholder_document(label):
		return False
	return bool(item.get("file"))


def _is_uploadable_employee_document_type(document_type):
	if not document_type:
		return False
	rows = frappe.get_all(
		"Document Type",
		filters={
			"name": document_type,
			"is_active": 1,
			"applies_to": ["in", ["Empleado", "Ambos"]],
		},
		fields=["name"],
		limit_page_length=1,
	)
	return bool(rows)


def _is_editable_document_type(document_type):
	return _is_uploadable_employee_document_type(document_type)


def _prepare_extra_item(item):
	prepared = dict(item)
	prepared["document_label"] = prepared.get("document_label") or prepared.get("document_type")
	prepared["section_key"] = _resolve_section_key(prepared.get("document_label"), prepared.get("source_doctype"))
	prepared["is_editable"] = cint(
		prepared.get("source_doctype") == "Person Document"
		and _is_editable_document_type(prepared.get("document_type") or prepared.get("document_label"))
	)
	return prepared


def _item_priority(row):
	return (
		SOURCE_PRIORITY.get(row.get("source_doctype"), 0),
		str(row.get("uploaded_on") or ""),
		str(row.get("source_name") or row.get("person_document") or ""),
	)


def _dedupe_and_group_extra_documents(extra_docs, taken_files=None):
	taken_files = {str(file_url).strip() for file_url in (taken_files or set()) if file_url}
	sections = _empty_extra_sections()
	seen_files = set(taken_files)
	seen_sources = set()

	for row in sorted((_prepare_extra_item(doc) for doc in extra_docs), key=_item_priority, reverse=True):
		if not _has_archival_value(row):
			continue

		file_key = str(row.get("file") or "").strip()
		source_key = (
			str(row.get("source_doctype") or "").strip(),
			str(row.get("source_name") or row.get("person_document") or "").strip(),
			str(row.get("document_type") or row.get("document_label") or "").strip(),
		)

		if file_key and file_key in seen_files:
			continue
		if source_key in seen_sources:
			continue

		if file_key:
			seen_files.add(file_key)
		seen_sources.add(source_key)
		sections[row["section_key"]].append(row)

	return sections


def _contract_documents(employee):
	items = []
	for row in frappe.get_all(
		"Contrato",
		filters={"empleado": employee},
		fields=["name", "contrato_firmado", "modified", "owner"],
		order_by="modified desc",
	):
		if row.contrato_firmado:
			items.append(_mk_folder_item(
				"contract_documents",
				f"Contrato firmado {row.name}",
				file_url=row.contrato_firmado,
				uploaded_on=row.modified,
				uploaded_by=row.owner,
				source_doctype="Contrato",
				source_name=row.name,
			))
	return items


def _persona_documento_documents(employee):
	"""Get documents from Persona Documento linked to this employee."""
	items = []
	
	# First try direct link to employee
	for row in frappe.get_all(
		"Persona Documento",
		filters={"persona": employee},
		fields=["name", "tipo_documento", "archivo", "estado_documento", "modified", "owner"],
		order_by="modified desc",
	):
		if _is_placeholder_document(row.tipo_documento) or not row.archivo:
			continue
		items.append(_mk_folder_item(
			"selection_rrll_documents",
			row.tipo_documento or f"Persona Documento {row.name}",
			file_url=row.archivo,
			status=row.estado_documento or ("Vigente" if row.archivo else "Pendiente"),
			uploaded_on=row.modified,
			uploaded_by=row.owner,
			source_doctype="Persona Documento",
			source_name=row.name,
		))
	return items


def _person_document_by_candidate_link(employee, existing_files=None):
	"""
	Get documents from Person Document where the candidate is linked to this employee.
	This handles the case where documents were uploaded during candidate phase
	and need to appear in the employee's folder after hiring.
	
	Args:
		employee: The employee (Ficha Empleado) name
		existing_files: Set of file_urls already included to avoid duplicates
	"""
	items = []
	existing_files = existing_files or set()
	
	# Find the candidate linked to this employee
	candidate_id = frappe.db.get_value("Candidato", {"persona": employee}, "name")
	if not candidate_id:
		return items
	
	# Get Person Documents for this candidate (uploaded during selection/affiliation)
	for row in frappe.get_all(
		"Person Document",
		filters={
			"candidate": candidate_id,
			"person_type": "Candidato",
		},
		fields=["name", "document_type", "file", "status", "modified", "owner"],
		order_by="modified desc",
	):
		# Skip if already included (avoid duplicates)
		if row.file and row.file in existing_files:
			continue
		
		items.append(_mk_folder_item(
			"selection_rrll_documents",
			row.document_type or f"Person Document {row.name}",
			file_url=row.file,
			status=row.status or ("Vigente" if row.file else "Pendiente"),
			uploaded_on=row.modified,
			uploaded_by=row.owner,
			source_doctype="Person Document",
			source_name=row.name,
		))
	
	return items


def _get_candidate_for_employee(employee):
	return frappe.db.get_value("Candidato", {"persona": employee}, "name")


def _collect_employee_and_candidate_person_docs(employee, required_names=None):
	fields = [
		"name",
		"document_type",
		"employee",
		"person_type",
		"status",
		"file",
		"uploaded_by",
		"uploaded_on",
		"approved_by",
		"approved_on",
		"notes",
		"issue_date",
		"valid_until",
		"modified",
	]
	filters = {"employee": employee}
	if required_names:
		filters["document_type"] = ["in", list(required_names)]
	rows = list(frappe.get_all("Person Document", filters=filters, fields=fields, order_by="modified desc"))
	candidate = _get_candidate_for_employee(employee)
	if candidate:
		candidate_filters = {"candidate": candidate, "person_type": "Candidato"}
		if required_names:
			candidate_filters["document_type"] = ["in", list(required_names)]
		rows.extend(frappe.get_all("Person Document", filters=candidate_filters, fields=fields, order_by="modified desc"))
	return rows


def _select_freshest_doc(rows):
	if not rows:
		return None
	return sorted(
		rows,
		key=lambda row: str(
			_field_value(row, "uploaded_on") or _field_value(row, "approved_on") or _field_value(row, "modified") or ""
		),
		reverse=True,
	)[0]


def _sst_documents(employee):
	items = []
	rows = frappe.get_all(
		"Novedad SST",
		filters={"empleado": employee},
		fields=["name", "tipo_novedad", "evidencia_incapacidad", "modified", "owner"],
		order_by="modified desc",
	)
	for row in rows:
		if row.evidencia_incapacidad:
			items.append(_mk_folder_item(
				"sst_documents",
				f"SST {row.tipo_novedad or 'Novedad'} {row.name}",
				file_url=row.evidencia_incapacidad,
				uploaded_on=row.modified,
				uploaded_by=row.owner,
				source_doctype="Novedad SST",
				source_name=row.name,
			))

		doc = frappe.get_doc("Novedad SST", row.name)
		for s in (doc.seguimientos or []):
			if s.adjunto:
				items.append(_mk_folder_item(
					"sst_documents",
					f"SST Seguimiento {doc.name}",
					file_url=s.adjunto,
					uploaded_on=s.fecha_seguimiento,
					uploaded_by=s.responsable,
					source_doctype="Novedad SST",
					source_name=doc.name,
				))
		for s in (doc.prorrogas_incapacidad or []):
			if s.adjunto:
				items.append(_mk_folder_item(
					"sst_documents",
					f"SST Prórroga {doc.name}",
					file_url=s.adjunto,
					uploaded_on=s.fecha_seguimiento,
					uploaded_by=s.responsable,
					source_doctype="Novedad SST",
					source_name=doc.name,
				))
	return items


def _disciplinary_documents(employee):
	items = []
	case_names = [r.name for r in frappe.get_all("Caso Disciplinario", filters={"empleado": employee}, fields=["name"], order_by="modified desc")]
	if not case_names:
		return items

	for f in frappe.get_all(
		"File",
		filters={
			"attached_to_doctype": "Caso Disciplinario",
			"attached_to_name": ["in", case_names],
			"file_url": ["is", "set"],
		},
		fields=["name", "attached_to_name", "file_url", "modified", "owner"],
		order_by="modified desc",
	):
		items.append(_mk_folder_item(
			"disciplinary_documents",
			f"Caso Disciplinario {f.attached_to_name}",
			file_url=f.file_url,
			uploaded_on=f.modified,
			uploaded_by=f.owner,
			source_doctype="Caso Disciplinario",
			source_name=f.attached_to_name,
		))
	return items


def _required_document_types():
	return frappe.get_all(
		"Document Type",
		filters={
			"is_active": 1,
			"applies_to": ["in", ["Empleado", "Ambos"]],
			"requires_for_employee_folder": 1,
		},
		fields=["name", "document_name", "has_expiry", "sort_order"],
		order_by="sort_order asc, modified asc",
	)


def _editable_employee_document_types():
	rows = frappe.get_all(
		"Document Type",
		filters={
			"is_active": 1,
			"applies_to": ["in", ["Empleado", "Ambos"]],
		},
		fields=["name", "document_name", "requires_for_employee_folder", "has_expiry", "sort_order"],
		order_by="sort_order asc, modified asc",
	)
	items = []
	for row in rows:
		document_type = row.name
		items.append({
			"name": document_type,
			"label": row.document_name or document_type,
			"section_key": _resolve_section_key(row.document_name or document_type, "Person Document"),
			"has_expiry": cint(row.has_expiry),
			"requires_for_employee_folder": cint(row.requires_for_employee_folder),
			"sort_order": cint(row.sort_order),
		})
	return items


def _employee_rows(search=None, branch=None, employment_status=None, limit_start=0, limit_page_length=50):
	limit_start = cint(limit_start or 0)
	limit_page_length = cint(limit_page_length or 50)
	filters = {}
	or_filters = None
	if branch:
		filters["pdv"] = branch
	if employment_status == "active":
		filters["estado"] = ["!=", "Retirado"]
	elif employment_status == "retired":
		filters["estado"] = "Retirado"
	if search:
		term = f"%{search.strip()}%"
		or_filters = {
			"name": ["like", term],
			"cedula": ["like", term],
			"pdv": ["like", term],
			"nombres": ["like", term],
			"apellidos": ["like", term],
		}

	return frappe.get_all(
		"Ficha Empleado",
		fields=["name", "nombres", "apellidos", "cedula", "pdv", "estado"],
		filters=filters,
		or_filters=or_filters,
		order_by="modified desc",
		limit_start=limit_start,
		limit_page_length=limit_page_length,
	)


def _employee_required_summary(employee_name, required_types_map):
	required_names = list(required_types_map.keys())
	uploaded_required = {}
	vencidos = 0
	
	# Count documents directly linked to employee
	uploaded_any_count = frappe.db.count(
		"Person Document",
		{
			"employee": employee_name,
			"file": ["is", "set"],
		},
	)
	
	# Also count documents from candidate phase linked to this employee
	candidate_id = _get_candidate_for_employee(employee_name)
	if candidate_id:
		candidate_doc_count = frappe.db.count(
			"Person Document",
			{
				"candidate": candidate_id,
				"person_type": "Candidato",
				"file": ["is", "set"],
			},
		)
		uploaded_any_count += candidate_doc_count
	
	if required_names:
		person_docs = [row for row in _collect_employee_and_candidate_person_docs(employee_name, required_names) if row.file]
		
		for row in person_docs:
			doc_type = _field_value(row, "document_type")
			if doc_type in uploaded_required:
				continue
			uploaded_required[doc_type] = row
			has_expiry = cint(_field_value(required_types_map.get(doc_type), "has_expiry", 0))
			if _is_expired(has_expiry, _field_value(row, "valid_until")):
				vencidos += 1

	total_required = len(required_names)
	uploaded_count = len(uploaded_required)
	missing_count = max(total_required - uploaded_count, 0)
	progress = int(round((uploaded_count / total_required) * 100, 0)) if total_required else 100

	return {
		"total_required": total_required,
		"uploaded_count": uploaded_count,
		"uploaded_any_count": cint(uploaded_any_count),
		"missing_count": missing_count,
		"expired_count": vencidos,
		"progress_percent": progress,
	}


@frappe.whitelist()
def get_employees_with_docs_status(search=None, branch=None, employment_status=None, limit_start=0, limit_page_length=50):
	_validate_folder_access()
	required_types = _required_document_types()
	required_map = {d.name: d for d in required_types}
	rows = _employee_rows(search=search, branch=branch, employment_status=employment_status, limit_start=limit_start, limit_page_length=limit_page_length)

	data = []
	for row in rows:
		summary = _employee_required_summary(row.name, required_map)
		full_name = f"{row.nombres or ''} {row.apellidos or ''}".strip() or row.name
		data.append({
			"employee": row.name,
			"employee_name": full_name,
			"id_number": row.cedula,
			"branch": row.pdv,
			"employment_status": row.estado,
			**summary,
		})

	return {
		"rows": data,
		"filters": {"employment_status": employment_status},
		"required_document_types": [
			{
				"name": d.name,
				"label": d.document_name or d.name,
				"has_expiry": cint(d.has_expiry),
				"sort_order": cint(d.sort_order),
			}
			for d in required_types
		],
	}


@frappe.whitelist()
def get_employee_documents(employee):
	_validate_folder_access(employee)
	if not employee:
		return {"employee": None, "documents": []}

	emp = frappe.get_doc("Ficha Empleado", employee)
	required_types = _required_document_types()
	required_map = {d.name: d for d in required_types}

	person_docs = _collect_employee_and_candidate_person_docs(employee)

	doc_by_type = {}
	extra_docs = []
	for row in person_docs:
		if row.document_type in required_map:
			doc_by_type.setdefault(row.document_type, []).append(row)
		elif row.document_type not in required_map and row.file and not _is_placeholder_document(row.document_type):
			extra_docs.append(row)

	results = []
	for d in required_types:
		row = _select_freshest_doc(doc_by_type.get(d.name) or [])
		has_file = bool(row and row.file)
		expired = _is_expired(d.has_expiry, row.valid_until if row else None)
		status = "Faltante"
		if has_file and expired:
			status = "Vencido"
		elif has_file:
			status = "Vigente"

		results.append({
			"person_document": row.name if row else None,
			"can_replace": cint(bool(row and str(getattr(row, "employee", "") or "") == str(employee))),
			"document_type": d.name,
			"document_label": d.document_name or d.name,
			"has_expiry": cint(d.has_expiry),
			"issue_date": row.issue_date if row else None,
			"valid_until": row.valid_until if row else None,
			"file": row.file if row else None,
			"uploaded_on": row.uploaded_on if row else None,
			"uploaded_by": row.uploaded_by if row else None,
			"status": status,
			"is_missing": status == "Faltante",
			"is_expired": status == "Vencido",
			"is_extra": 0,
			"section_key": "required_documents",
			"source_doctype": "Person Document" if row else None,
			"source_name": row.name if row else None,
			"is_editable": cint(_is_editable_document_type(d.name)),
		})

	required_results = list(results)

	for row in extra_docs:
		results.append({
			"person_document": row.name,
			"can_replace": cint(str(getattr(row, "employee", "") or "") == str(employee)),
			"document_type": row.document_type,
			"document_label": row.document_type,
			"has_expiry": 0,
			"issue_date": row.issue_date,
			"valid_until": row.valid_until,
			"file": row.file,
			"uploaded_on": row.uploaded_on,
			"uploaded_by": row.uploaded_by,
			"status": "Vigente" if row.file else (row.status or "Faltante"),
			"is_missing": 0 if row.file else 1,
			"is_expired": 0,
			"is_extra": 1,
			"section_key": _resolve_section_key(row.document_type, "Person Document"),
			"source_doctype": "Person Document",
			"source_name": row.name,
			"is_editable": cint(_is_editable_document_type(row.document_type)),
		})

	extra_results = [r for r in results if cint(r.get("is_extra")) == 1]
	taken_files = {r.get("file") for r in required_results if r.get("file")}
	extra_candidates = list(extra_results)
	extra_candidates.extend(_persona_documento_documents(employee))
	extra_candidates.extend(_contract_documents(employee))
	extra_candidates.extend(_sst_documents(employee))
	extra_candidates.extend(_disciplinary_documents(employee))
	extra_split = _dedupe_and_group_extra_documents(extra_candidates, taken_files=taken_files)

	summary = _employee_required_summary(employee, required_map)
	return {
		"employee": {
			"name": emp.name,
			"employee_name": f"{emp.nombres or ''} {emp.apellidos or ''}".strip() or emp.name,
			"id_number": emp.cedula,
			"branch": emp.pdv,
			"employment_status": getattr(emp, "estado", None),
		},
		"summary": summary,
		"required_documents": required_results,
		"extra_documents": extra_results,
		"selection_rrll_documents": extra_split["selection_rrll_documents"],
		"sst_documents": extra_split["sst_documents"],
		"contract_documents": extra_split["contract_documents"],
		"disciplinary_documents": extra_split["disciplinary_documents"],
		"other_documents": extra_split["other_documents"],
		"permissions": {
			"can_upload": cint(_has_folder_write_access()),
		},
		"documents": results,
	}


@frappe.whitelist()
def get_uploadable_document_types(employee=None):
	_validate_folder_write_access(employee)
	return {
		"can_upload": cint(_has_folder_write_access()),
		"items": _editable_employee_document_types(),
	}


def _upsert_employee_document(employee, document_type, file_url, issue_date=None, valid_until=None, person_document=None):
	if not employee or not document_type or not file_url:
		frappe.throw("employee, document_type y file_url son obligatorios")
	if not _is_uploadable_employee_document_type(document_type):
		frappe.throw("El tipo documental no está habilitado para carga manual en la carpeta del empleado")

	if person_document:
		doc = frappe.get_doc("Person Document", person_document)
		if str(doc.employee or "") != str(employee):
			frappe.throw("El documento no pertenece al empleado enviado")
	else:
		existing = frappe.get_all(
			"Person Document",
			filters={"employee": employee, "document_type": document_type},
			fields=["name"],
			order_by="modified desc",
			limit_page_length=1,
		)
		doc = frappe.get_doc("Person Document", existing[0].name) if existing else frappe.get_doc({
			"doctype": "Person Document",
			"person_type": "Empleado",
			"person_doctype": "Ficha Empleado",
			"person": employee,
			"employee": employee,
			"document_type": document_type,
			"status": "Subido",
		})

	doc.person_type = "Empleado"
	doc.person_doctype = "Ficha Empleado"
	doc.person = employee
	doc.employee = employee
	doc.document_type = document_type
	doc.file = file_url
	doc.status = "Subido"
	doc.uploaded_by = frappe.session.user
	doc.uploaded_on = now_datetime()
	if issue_date:
		doc.issue_date = issue_date
	if valid_until is not None:
		doc.valid_until = valid_until

	if doc.name:
		doc.save(ignore_permissions=True)
	else:
		doc.insert(ignore_permissions=True)

	return {
		"name": doc.name,
		"file": doc.file,
		"status": doc.status,
	}


@frappe.whitelist()
def upload_document(employee, document_type, file_url, issue_date=None, valid_until=None):
	_validate_folder_write_access(employee)
	return _upsert_employee_document(
		employee=employee,
		document_type=document_type,
		file_url=file_url,
		issue_date=issue_date,
		valid_until=valid_until,
	)


@frappe.whitelist()
def replace_document(person_document, employee, document_type, file_url, issue_date=None, valid_until=None):
	_validate_folder_write_access(employee)
	return _upsert_employee_document(
		employee=employee,
		document_type=document_type,
		file_url=file_url,
		issue_date=issue_date,
		valid_until=valid_until,
		person_document=person_document,
	)


def _persist_generated_private_file(file_name, content, attached_to_doctype, attached_to_name):
	private_files_path = frappe.get_site_path("private", "files")
	os.makedirs(private_files_path, exist_ok=True)
	base_name, ext = os.path.splitext(file_name)
	safe_base = re.sub(r"[^\w\-.]+", "_", base_name).strip("._") or "archivo"
	content_hash = hashlib.md5(content).hexdigest()
	final_name = f"{safe_base}{ext}"
	absolute_path = os.path.join(private_files_path, final_name)
	idx = 2
	while os.path.exists(absolute_path):
		with open(absolute_path, "rb") as existing_file:
			if hashlib.md5(existing_file.read()).hexdigest() == content_hash:
				break
		final_name = f"{safe_base}-{idx}{ext}"
		absolute_path = os.path.join(private_files_path, final_name)
		idx += 1
	if not os.path.exists(absolute_path):
		with open(absolute_path, "wb") as output_file:
			output_file.write(content)
	file_url = f"/private/files/{final_name}"
	existing = frappe.db.get_value(
		"File",
		{
			"file_url": file_url,
			"attached_to_doctype": attached_to_doctype,
			"attached_to_name": attached_to_name,
		},
		"name",
	)
	if existing:
		return file_url
	frappe.get_doc({
		"doctype": "File",
		"file_name": final_name,
		"file_url": file_url,
		"is_private": 1,
		"attached_to_doctype": attached_to_doctype,
		"attached_to_name": attached_to_name,
		"folder": "Home/Attachments",
	}).insert(ignore_permissions=True)
	return file_url


@frappe.whitelist()
def download_employee_documents_zip(employee):
	_validate_folder_access(employee)
	data = get_employee_documents(employee)
	sections = [
		("01_requeridos", data.get("required_documents") or []),
		("02_seleccion_rrll", data.get("selection_rrll_documents") or []),
		("03_sst", data.get("sst_documents") or []),
		("04_contractuales", data.get("contract_documents") or []),
		("05_disciplinarios", data.get("disciplinary_documents") or []),
		("06_otros", data.get("other_documents") or []),
	]

	buf = io.BytesIO()
	with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
		seen = set()
		for folder, docs in sections:
			idx = 1
			for row in docs:
				file_url = row.get("file")
				if not file_url:
					continue
				abs_path = frappe.get_site_path(str(file_url).lstrip("/"))
				if not os.path.exists(abs_path):
					continue
				if (folder, file_url) in seen:
					continue
				seen.add((folder, file_url))
				ext = os.path.splitext(abs_path)[1] or ""
				safe_name = re.sub(r"[^\w\-]+", "_", str(row.get("document_label") or row.get("document_type") or "documento")).strip("_") or "documento"
				zf.write(abs_path, arcname=f"{folder}/{idx:03d}_{safe_name}{ext}")
				idx += 1

	zip_name = f"empleado_{employee}_expediente_digital.zip"
	return _persist_generated_private_file(zip_name, buf.getvalue(), "Ficha Empleado", employee)
