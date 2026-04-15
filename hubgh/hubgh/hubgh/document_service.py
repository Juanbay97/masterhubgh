import io
import os
import re
import unicodedata
import zipfile

import frappe
from frappe import _
from frappe.utils import now
from frappe.utils.file_manager import save_file

from hubgh.hubgh.candidate_states import (
	STATE_AFILIACION,
	STATE_CONTRATADO,
	STATE_DOCUMENTACION,
	STATE_EXAMEN_MEDICO,
	STATE_LISTO_CONTRATAR,
	get_candidate_status_options,
	is_candidate_status,
	resolve_candidate_status_for_storage,
)
from hubgh.hubgh.doctype.document_type.document_type import get_effective_area_roles
from hubgh.hubgh.people_ops_handoffs import validate_selection_to_rrll_gate
from hubgh.hubgh.people_ops_policy import evaluate_dimension_access, resolve_document_dimension
from hubgh.hubgh.role_matrix import roles_have_any, user_has_any_role
from hubgh.hubgh.selection_document_types import canonicalize_selection_document_name


_MULTI_UPLOAD_DOCUMENT_TYPES_FALLBACK = {
	"2 cartas de referencias personales.",
	"certificados de estudios y/o actas de grado bachiller y posteriores.",
}


def _normalize_text(value):
	text = str(value or "").strip().lower()
	if not text:
		return ""
	return "".join(ch for ch in unicodedata.normalize("NFKD", text) if not unicodedata.combining(ch))


def _normalize_identity_value(value):
	text = str(value or "").strip().upper()
	if not text:
		return ""
	text = "".join(ch for ch in unicodedata.normalize("NFKD", text) if not unicodedata.combining(ch))
	return re.sub(r"[^A-Z0-9]", "", text)


def _resolve_document_type_name(document_type):
	requested = canonicalize_selection_document_name((document_type or "").strip())
	if not requested:
		frappe.throw(_("Tipo de documento requerido."))

	if frappe.db.exists("Document Type", requested):
		return requested

	requested_norm = _normalize_text(requested)
	rows = frappe.get_all(
		"Document Type",
		fields=["name", "document_name"],
		filters={"is_active": 1},
		ignore_permissions=True,
	)
	for row in rows:
		if _normalize_text(row.name) == requested_norm or _normalize_text(row.document_name) == requested_norm:
			return row.name

	frappe.throw(_(f"Tipo de documento no encontrado: {requested}"))


def _is_excluded_from_candidate_hiring_progress(doc_type_row):
	"""Regla transicional: Contrato no bloquea el envío a RL."""
	name = str((doc_type_row.get("document_name") if isinstance(doc_type_row, dict) else getattr(doc_type_row, "document_name", None)) or (doc_type_row.get("name") if isinstance(doc_type_row, dict) else getattr(doc_type_row, "name", None)) or "").strip().lower()
	return name == "contrato"


def _is_bank_certification_document(doc_type_row):
	name = _normalize_text((doc_type_row.get("document_name") if isinstance(doc_type_row, dict) else getattr(doc_type_row, "document_name", None)) or (doc_type_row.get("name") if isinstance(doc_type_row, dict) else getattr(doc_type_row, "name", None)) or "")
	return name == _normalize_text("Certificación bancaria (No mayor a 30 días).")


def _candidate_has_bank_account(candidate):
	row = frappe.db.get_value(
		"Candidato",
		candidate,
		["tiene_cuenta_bancaria", "banco_siesa", "tipo_cuenta_bancaria", "numero_cuenta_bancaria"],
		as_dict=True,
	)
	value = str((row or {}).get("tiene_cuenta_bancaria") or "").strip().lower()
	if value in {"si", "sí", "1", "true", "yes"}:
		return True
	return any((row or {}).get(fieldname) not in (None, "") for fieldname in ("banco_siesa", "tipo_cuenta_bancaria", "numero_cuenta_bancaria"))


def _filter_candidate_document_types_for_profile(candidate, doc_types):
	if _candidate_has_bank_account(candidate):
		return list(doc_types or [])
	return [row for row in (doc_types or []) if not _is_bank_certification_document(row)]


def _get_document_type_rules(document_type):
	dt_name = _resolve_document_type_name(document_type)
	dt = frappe.get_doc("Document Type", dt_name)
	allowed_roles = []
	for row in dt.allowed_areas or []:
		allowed_roles.extend(get_effective_area_roles(row.area_role))

	override_roles = []
	if dt.allowed_roles_override:
		override_roles = [r.strip() for r in dt.allowed_roles_override.replace("\n", ",").split(",") if r.strip()]

	allows_multiple = int(dt.allows_multiple or 0)
	if not allows_multiple and _normalize_text(dt.document_name or dt.name) in _MULTI_UPLOAD_DOCUMENT_TYPES_FALLBACK:
		allows_multiple = 1

	return {
		"requires_approval": int(dt.requires_approval or 0),
		"allows_multiple": allows_multiple,
		"allowed_roles": sorted(set(allowed_roles + override_roles)),
		"document_type": dt_name,
	}


def _safe_document_type_slug(document_type):
	slug = re.sub(r"\s+", "_", (document_type or "documento").strip())
	slug = re.sub(r"[^\w\-]", "", slug, flags=re.UNICODE)
	return slug or "documento"


def _person_doctype_for(person_type):
	return "Candidato" if person_type == "Candidato" else "Ficha Empleado"


def _match_person_name_by_identity(doctype, fieldname, value, extra_fields=None):
	normalized_value = _normalize_identity_value(value)
	if not normalized_value:
		return ""

	fields = ["name", fieldname]
	for extra_field in extra_fields or []:
		if extra_field and extra_field not in fields:
			fields.append(extra_field)

	rows = frappe.get_all(doctype, fields=fields, ignore_permissions=True)
	for row in rows:
		for candidate_value in [row.get("name"), row.get(fieldname)] + [row.get(extra_field) for extra_field in extra_fields or []]:
			if _normalize_identity_value(candidate_value) == normalized_value:
				return str(row.get("name") or "").strip()
	return ""


def _resolve_employee_name(person):
	person_name = str(person or "").strip()
	if not person_name:
		return ""

	if frappe.db.exists("Ficha Empleado", person_name):
		return person_name

	by_document = frappe.db.get_value("Ficha Empleado", {"cedula": person_name}, "name")
	if by_document:
		return by_document

	matched = _match_person_name_by_identity("Ficha Empleado", "cedula", person_name)
	if matched:
		return matched

	if frappe.db.exists("Candidato", person_name):
		candidate_employee = str(frappe.db.get_value("Candidato", person_name, "persona") or "").strip()
		if candidate_employee and frappe.db.exists("Ficha Empleado", candidate_employee):
			return candidate_employee

	matched_candidate = _match_person_name_by_identity("Candidato", "numero_documento", person_name, extra_fields=["persona"])
	if matched_candidate:
		candidate_employee = str(frappe.db.get_value("Candidato", matched_candidate, "persona") or "").strip()
		if candidate_employee and frappe.db.exists("Ficha Empleado", candidate_employee):
			return candidate_employee

	return ""


def _resolve_candidate_name(person):
	person_name = str(person or "").strip()
	if not person_name:
		return ""

	if frappe.db.exists("Candidato", person_name):
		return person_name

	by_document = frappe.db.get_value("Candidato", {"numero_documento": person_name}, "name")
	if by_document:
		return by_document

	by_employee = frappe.db.get_value("Candidato", {"persona": person_name}, "name")
	if by_employee:
		return by_employee

	matched = _match_person_name_by_identity("Candidato", "numero_documento", person_name, extra_fields=["persona"])
	if matched:
		return matched

	employee_name = _resolve_employee_name(person_name)
	if employee_name:
		by_employee = frappe.db.get_value("Candidato", {"persona": employee_name}, "name")
		if by_employee:
			return by_employee

	return ""


def _resolve_person_name(person_type, person):
	person_name = str(person or "").strip()
	if not person_name:
		return ""

	if person_type == "Candidato":
		return _resolve_candidate_name(person_name) or person_name

	return _resolve_employee_name(person_name) or person_name


def _person_identity_aliases(person_type, person):
	aliases = []
	requested = str(person or "").strip()
	resolved = _resolve_person_name(person_type, requested)

	for value in (resolved, requested):
		if value and value not in aliases:
			aliases.append(value)

	if person_type == "Candidato" and resolved:
		numero_documento = str(frappe.db.get_value("Candidato", resolved, "numero_documento") or "").strip()
		if numero_documento and numero_documento not in aliases:
			aliases.append(numero_documento)
		employee = str(frappe.db.get_value("Candidato", resolved, "persona") or "").strip()
		if employee and employee not in aliases:
			aliases.append(employee)
		if employee:
			employee_document = str(frappe.db.get_value("Ficha Empleado", employee, "cedula") or "").strip()
			if employee_document and employee_document not in aliases:
				aliases.append(employee_document)
	elif person_type == "Empleado" and resolved:
		cedula = str(frappe.db.get_value("Ficha Empleado", resolved, "cedula") or "").strip()
		if cedula and cedula not in aliases:
			aliases.append(cedula)
		candidate = str(frappe.db.get_value("Candidato", {"persona": resolved}, "name") or "").strip()
		if candidate and candidate not in aliases:
			aliases.append(candidate)
		if candidate:
			candidate_document = str(frappe.db.get_value("Candidato", candidate, "numero_documento") or "").strip()
			if candidate_document and candidate_document not in aliases:
				aliases.append(candidate_document)

	return aliases


def get_person_document_rows(person_type, person, *, fields=None, extra_filters=None, order_by="modified desc", limit_page_length=None):
	requested_fields = list(fields or ["name"])
	for fieldname in ("name", "person", "candidate", "employee"):
		if fieldname not in requested_fields:
			requested_fields.append(fieldname)

	rows = frappe.get_all(
		"Person Document",
		filters={"person_type": person_type, **(extra_filters or {})},
		fields=requested_fields,
		order_by=order_by,
		limit_page_length=limit_page_length,
	)
	aliases = _person_identity_aliases(person_type, person)
	return [row for row in rows if _matches_person_alias(row, aliases)]


def _get_file_doc_from_url(file_url):
	if not file_url:
		return None

	by_url = frappe.db.get_value("File", {"file_url": file_url}, "name")
	if by_url:
		return by_url

	file_name = (str(file_url).rstrip("/").split("/")[-1] or "").strip()
	if not file_name:
		return None

	return frappe.db.get_value("File", {"file_name": file_name}, "name")


def rename_uploaded_candidate_file(file_url, document_type, candidate=None, numero_documento=None):
	"""Renombra archivo de candidato a cedula-tipo_documento.ext de forma segura.

	No toca archivos históricos; solo se invoca en nuevos uploads.
	Si no puede resolver el archivo o no existe en disco, retorna la URL original.
	"""
	if not file_url:
		return file_url

	cedula = (numero_documento or "").strip()
	if not cedula and candidate:
		cedula = (frappe.db.get_value("Candidato", candidate, "numero_documento") or "").strip()
	if not cedula:
		return file_url

	file_doc_name = _get_file_doc_from_url(file_url)
	if not file_doc_name:
		return file_url

	file_doc = frappe.get_doc("File", file_doc_name)
	old_url = (file_doc.file_url or file_url or "").strip()
	if not old_url:
		return file_url

	old_abs_path = frappe.get_site_path(old_url.lstrip("/"))
	if not os.path.exists(old_abs_path):
		return file_url

	ext = os.path.splitext(old_abs_path)[1] or os.path.splitext(old_url)[1] or ""
	doc_slug = _safe_document_type_slug(document_type)
	base_name = f"{cedula}-{doc_slug}"
	new_file_name = f"{base_name}{ext}"

	dir_path = os.path.dirname(old_abs_path)
	new_abs_path = os.path.join(dir_path, new_file_name)
	idx = 2
	while os.path.exists(new_abs_path) and os.path.normpath(new_abs_path) != os.path.normpath(old_abs_path):
		new_file_name = f"{base_name}-{idx}{ext}"
		new_abs_path = os.path.join(dir_path, new_file_name)
		idx += 1

	if os.path.normpath(new_abs_path) != os.path.normpath(old_abs_path):
		os.rename(old_abs_path, new_abs_path)

	base_url = old_url.rsplit("/", 1)[0] if "/" in old_url else ""
	new_url = f"{base_url}/{new_file_name}" if base_url else f"/{new_file_name}"

	file_doc.file_name = new_file_name
	file_doc.file_url = new_url
	file_doc.save(ignore_permissions=True)
	return new_url


def move_file_to_employee_subfolder(file_url, employee, subfolder, filename_prefix=None):
	"""Move an uploaded file into a deterministic employee subfolder.

	This is reusable for any future module that needs employee-scoped storage,
	e.g. incapacidades, recomendaciones, incapacidades prorrogadas, etc.
	"""
	if not file_url or not employee or not subfolder:
		return file_url

	safe_employee = re.sub(r"[^\w\-]", "_", str(employee).strip(), flags=re.UNICODE) or "empleado"
	safe_subfolder = re.sub(r"[^\w\-]", "_", str(subfolder).strip().lower(), flags=re.UNICODE) or "documentos"

	target_marker = f"/empleados/{safe_employee}/{safe_subfolder}/"
	if target_marker in str(file_url):
		return file_url

	file_doc_name = _get_file_doc_from_url(file_url)
	if not file_doc_name:
		return file_url

	file_doc = frappe.get_doc("File", file_doc_name)
	old_url = (file_doc.file_url or file_url or "").strip()
	if not old_url:
		return file_url

	old_abs_path = frappe.get_site_path(old_url.lstrip("/"))
	if not os.path.exists(old_abs_path):
		return file_url

	is_private = str(old_url).startswith("/private/files/")
	root_abs = frappe.get_site_path("private", "files") if is_private else frappe.get_site_path("public", "files")
	rel_dir = os.path.join("empleados", safe_employee, safe_subfolder)
	target_dir = os.path.join(root_abs, rel_dir)
	os.makedirs(target_dir, exist_ok=True)

	ext = os.path.splitext(old_abs_path)[1] or os.path.splitext(old_url)[1] or ""
	base_name = (filename_prefix or os.path.splitext(file_doc.file_name or os.path.basename(old_abs_path))[0] or "documento").strip()
	base_name = re.sub(r"[^\w\-]", "_", base_name, flags=re.UNICODE) or "documento"

	new_file_name = f"{base_name}{ext}"
	new_abs_path = os.path.join(target_dir, new_file_name)
	while os.path.exists(new_abs_path) and os.path.normpath(new_abs_path) != os.path.normpath(old_abs_path):
		new_file_name = f"{base_name}-{frappe.generate_hash(length=6)}{ext}"
		new_abs_path = os.path.join(target_dir, new_file_name)

	if os.path.normpath(new_abs_path) != os.path.normpath(old_abs_path):
		os.rename(old_abs_path, new_abs_path)

	rel_url = "/".join(["private/files" if is_private else "files", rel_dir.replace(os.sep, "/"), new_file_name])
	new_url = f"/{rel_url}"

	file_doc.file_name = new_file_name
	file_doc.file_url = new_url
	file_doc.save(ignore_permissions=True)
	return new_url


def _candidate_apellidos_fallback(row):
	if not row:
		return ""
	apellidos = (row.get("apellidos") if isinstance(row, dict) else getattr(row, "apellidos", None)) or ""
	if str(apellidos).strip():
		return str(apellidos).strip()
	primer = (row.get("primer_apellido") if isinstance(row, dict) else getattr(row, "primer_apellido", None)) or ""
	segundo = (row.get("segundo_apellido") if isinstance(row, dict) else getattr(row, "segundo_apellido", None)) or ""
	return " ".join([p.strip() for p in [primer, segundo] if p and str(p).strip()]).strip()


def _sync_employee_from_candidate(employee_doc, candidate_doc):
	updates = {}
	for fieldname in (
		"email",
		"banco_siesa",
		"tipo_cuenta_bancaria",
		"numero_cuenta_bancaria",
		"eps_siesa",
		"afp_siesa",
		"cesantias_siesa",
		"ccf_siesa",
	):
		current_value = employee_doc.get(fieldname) if hasattr(employee_doc, "get") else getattr(employee_doc, fieldname, None)
		candidate_value = candidate_doc.get(fieldname) if hasattr(candidate_doc, "get") else getattr(candidate_doc, fieldname, None)
		if current_value in (None, "") and candidate_value not in (None, ""):
			updates[fieldname] = candidate_value

	current_origin = employee_doc.get("candidato_origen") if hasattr(employee_doc, "get") else getattr(employee_doc, "candidato_origen", None)
	if current_origin in (None, "") and getattr(candidate_doc, "name", None):
		updates["candidato_origen"] = candidate_doc.name

	for fieldname, value in updates.items():
		setattr(employee_doc, fieldname, value)

	return updates


def can_user_read_person_document(doc, user=None):
	user = user or frappe.session.user
	if user == "Administrator":
		return True

	if _has_full_employee_documental_access(user, doc):
		return True
	if _has_candidate_rrll_access(user, doc):
		return True

	# Access list explícito por usuario o rol
	roles = set(frappe.get_roles(user))
	for row in doc.document_access or []:
		if row.user and row.user == user and row.can_view:
			return True
		if row.role and row.role in roles and row.can_view:
			return True

	rules = _get_document_type_rules(doc.document_type)
	dimension = resolve_document_dimension(doc.document_type)
	policy = evaluate_dimension_access(
		dimension,
		user=user,
		surface="person_document",
		context={"document_type": doc.document_type, "action": "read"},
	)
	if not policy.get("effective_allowed"):
		return False
	if dimension == "clinical" and user_has_any_role(user, "HR SST", "HR Labor Relations", "Relaciones Laborales Jefe", "System Manager"):
		return True

	if roles_have_any(roles, set(rules["allowed_roles"])):
		return True

	# Candidato dueño del registro
	if doc.person_type == "Candidato":
		candidate_user = frappe.db.get_value("Candidato", doc.person, "user")
		if candidate_user and candidate_user == user:
			return True

	return False


def _candidate_has_uploaded_document(candidate, document_type):
	rows = get_person_document_rows(
		"Candidato",
		candidate,
		fields=["name"],
		extra_filters={
			"document_type": document_type,
			"status": ["in", ["Subido", "Aprobado"]],
			"file": ["is", "set"],
		},
		limit_page_length=50,
	)
	return bool(rows)


def _matches_person_alias(row, aliases):
	alias_set = {str(value or "").strip() for value in aliases if str(value or "").strip()}
	if not alias_set:
		return False
	for fieldname in ("person", "candidate", "employee"):
		value = str(_row_get(row, fieldname) or "").strip()
		if value and value in alias_set:
			return True
	return False


def _has_full_employee_documental_access(user, doc):
	if not user_has_any_role(user, "System Manager", "Relaciones Laborales Jefe"):
		return False
	return _is_employee_document_record(doc) or _is_admitted_candidate_document_record(doc)


def _has_candidate_rrll_access(user, doc):
	return _is_candidate_document_record(doc) and user_has_any_role(user, "HR Labor Relations", "Relaciones Laborales Jefe")


def _is_employee_document_record(doc):
	person_type = str(getattr(doc, "person_type", "") or (doc.get("person_type") if hasattr(doc, "get") else "")).strip()
	return person_type == "Empleado"


def _is_candidate_document_record(doc):
	person_type = str(getattr(doc, "person_type", "") or (doc.get("person_type") if hasattr(doc, "get") else "")).strip()
	return person_type == "Candidato"


def _is_admitted_candidate_document_record(doc):
	if not _is_candidate_document_record(doc):
		return False
	candidate = getattr(doc, "person", None) or (doc.get("person") if hasattr(doc, "get") else None)
	if not candidate:
		return False
	status = frappe.db.get_value("Candidato", candidate, "estado_proceso")
	return str(status or "").strip() in {
		"En afiliación",
		"En Afiliación",
		"Afiliacion",
		"En Proceso de Contratación",
		"Listo para contratar",
		"Listo para Contratar",
		"Contratado",
	}


def _find_existing_person_document(person_type, person, document_type, *, pending_only=False):
	aliases = _person_identity_aliases(person_type, person)
	rows = frappe.get_all(
		"Person Document",
		filters={
			"person_type": person_type,
			"document_type": document_type,
		},
		fields=["name", "person", "candidate", "employee", "file"],
		order_by="modified desc",
	)
	for row in rows:
		if pending_only and _row_get(row, "file"):
			continue
		if _matches_person_alias(row, aliases):
			return _row_get(row, "name")
	return None


def _find_pending_document_row(person_type, person, document_type):
	return _find_existing_person_document(person_type, person, document_type, pending_only=True)


def _row_get(row, key, default=None):
	if isinstance(row, dict):
		return row.get(key, default)
	return getattr(row, key, default)


def _doc_sort_key(row):
	return str(
		_row_get(row, "uploaded_on")
		or _row_get(row, "approved_on")
		or _row_get(row, "modified")
		or _row_get(row, "creation")
		or ""
	)


def _build_person_dossier(person_type, person):
	"""Canonical dossier source for a person with vigente/historico/versioned views (S5.1)."""
	rows = get_person_document_rows(
		person_type,
		person,
		fields=["name", "document_type", "status", "file", "uploaded_on", "approved_on", "modified", "creation"],
		order_by="modified desc",
	)

	by_type = {}
	for row in rows:
		doc_type = _row_get(row, "document_type")
		if not doc_type:
			continue
		by_type.setdefault(doc_type, []).append(row)

	vigentes = []
	historico = []
	for doc_type, group in by_type.items():
		sorted_group = sorted(group, key=_doc_sort_key, reverse=True)
		rules = _get_document_type_rules(doc_type)
		allows_multiple = int(rules.get("allows_multiple") or 0)

		if allows_multiple:
			for idx, row in enumerate(sorted_group, start=1):
				payload = {
					"name": _row_get(row, "name"),
					"document_type": doc_type,
					"status": _row_get(row, "status"),
					"file": _row_get(row, "file"),
					"version": idx,
					"is_vigente": True,
					"allows_multiple": 1,
				}
				vigentes.append(payload)
			continue

		for idx, row in enumerate(sorted_group, start=1):
			payload = {
				"name": _row_get(row, "name"),
				"document_type": doc_type,
				"status": _row_get(row, "status"),
				"file": _row_get(row, "file"),
				"version": idx,
				"is_vigente": idx == 1,
				"allows_multiple": 0,
			}
			if idx == 1:
				vigentes.append(payload)
			else:
				historico.append(payload)

	vigentes = sorted(vigentes, key=lambda r: (str(r.get("document_type") or ""), int(r.get("version") or 0)))
	historico = sorted(historico, key=lambda r: (str(r.get("document_type") or ""), int(r.get("version") or 0)))

	return {
		"person_type": person_type,
		"person": person,
		"source": "Person Document",
		"vigentes": vigentes,
		"historico": historico,
	}


def _new_person_document(person_type, person, document_type):
	person_name = _resolve_person_name(person_type, person)
	doc = frappe.get_doc({
		"doctype": "Person Document",
		"person_type": person_type,
		"person_doctype": _person_doctype_for(person_type),
		"person": person_name,
		"candidate": person_name if person_type == "Candidato" else None,
		"employee": person_name if person_type == "Empleado" else None,
		"document_type": document_type,
		"status": "Pendiente",
	})
	doc.insert(ignore_permissions=True)
	return doc


def _sync_person_document_identity(doc, person_type, person):
	person_name = _resolve_person_name(person_type, person)
	doc.person_type = person_type
	if person_type == "Candidato":
		doc.person_doctype = _person_doctype_for(person_type)
		doc.person = person_name
		doc.candidate = person_name
		if hasattr(doc, "employee"):
			doc.employee = None
		return doc

	doc.person_doctype = _person_doctype_for(person_type)
	doc.person = person_name
	doc.employee = person_name
	if hasattr(doc, "candidate"):
		doc.candidate = None
	return doc


def repair_person_document_links(person_type=None, person=None):
	if not frappe.db.exists("DocType", "Person Document"):
		return 0

	filters = {}
	if person_type:
		filters["person_type"] = person_type

	updated = 0
	requested_person = str(person or "").strip()
	resolved_requested_person = _resolve_person_name(person_type or "Candidato", person) if person else ""
	rows = frappe.get_all(
		"Person Document",
		filters=filters or None,
		fields=["name", "person_type", "person", "person_doctype", "candidate", "employee"],
		ignore_permissions=True,
	)
	for row in rows:
		row_person_type = str(row.get("person_type") or "").strip()
		if row_person_type not in {"Candidato", "Empleado"}:
			continue
		if requested_person:
			row_reference = str(
				row.get("candidate") if row_person_type == "Candidato" else row.get("employee") or row.get("person") or ""
			).strip()
			if row_reference not in {requested_person, resolved_requested_person} and str(row.get("person") or "").strip() not in {
				requested_person,
				resolved_requested_person,
			}:
				continue

		reference_name = row.get("candidate") if row_person_type == "Candidato" else row.get("employee")
		reference_name = reference_name or row.get("person")
		resolved_person = _resolve_person_name(row_person_type, reference_name)
		target_doctype = _person_doctype_for(row_person_type)
		if not resolved_person or not frappe.db.exists(target_doctype, resolved_person):
			continue

		updates = {}
		if str(row.get("person") or "").strip() != resolved_person:
			updates["person"] = resolved_person
		if str(row.get("person_doctype") or "").strip() != target_doctype:
			updates["person_doctype"] = target_doctype
		if row_person_type == "Candidato" and str(row.get("candidate") or "").strip() != resolved_person:
			updates["candidate"] = resolved_person
		if row_person_type == "Candidato" and str(row.get("employee") or "").strip():
			updates["employee"] = None
		if row_person_type == "Empleado" and str(row.get("employee") or "").strip() != resolved_person:
			updates["employee"] = resolved_person
		if row_person_type == "Empleado" and str(row.get("candidate") or "").strip():
			updates["candidate"] = None

		if updates:
			frappe.db.set_value("Person Document", row.get("name"), updates, update_modified=False)
			updated += 1

	return updated


def ensure_person_document(person_type, person, document_type):
	person = _resolve_person_name(person_type, person)
	rules = _get_document_type_rules(document_type)
	resolved_document_type = rules["document_type"]
	if not rules["allows_multiple"]:
		existing = _find_existing_person_document(person_type, person, resolved_document_type)
		if existing:
			return frappe.get_doc("Person Document", existing)
		return _new_person_document(person_type, person, resolved_document_type)

	pending_name = _find_pending_document_row(person_type, person, resolved_document_type)
	if pending_name:
		return frappe.get_doc("Person Document", pending_name)

	return _new_person_document(person_type, person, resolved_document_type)


def ensure_candidate_required_documents(candidate):
	doc_types = frappe.get_all(
		"Document Type",
		filters={"is_active": 1, "applies_to": ["in", ["Candidato", "Ambos"]]},
		fields=["name", "allows_multiple"],
	)
	doc_types = _filter_candidate_document_types_for_profile(candidate, doc_types)
	for d in doc_types:
		if int(d.allows_multiple or 0):
			exists = frappe.db.exists(
				"Person Document",
				{"person_type": "Candidato", "person": candidate, "document_type": d.name},
			)
			if not exists:
				ensure_person_document("Candidato", candidate, d.name)
			continue
		ensure_person_document("Candidato", candidate, d.name)


def get_candidate_progress(candidate):
	required = frappe.get_all(
		"Document Type",
		filters={
			"is_active": 1,
			"is_required_for_hiring": 1,
			"applies_to": ["in", ["Candidato", "Ambos"]],
		},
		fields=["name", "requires_approval", "document_name", "allows_multiple"],
	)
	required = [row for row in required if not _is_excluded_from_candidate_hiring_progress(row)]
	required = _filter_candidate_document_types_for_profile(candidate, required)

	if not required:
		return {
			"required_total": 0,
			"required_ok": 0,
			"missing": [],
			"percent": 100,
			"is_complete": True,
		}

	dossier = _build_person_dossier("Candidato", candidate)
	documents = list(dossier.get("vigentes") or [])
	doc_map = {}
	for d in documents:
		doc_map.setdefault(_row_get(d, "document_type"), []).append(d)

	ok = 0
	missing = []
	for req in required:
		related_docs = doc_map.get(req.name) or []
		valid_related_docs = [d for d in related_docs if _row_get(d, "file")]
		statuses = [_row_get(d, "status") for d in valid_related_docs]
		if req.requires_approval:
			is_ok = any(status == "Aprobado" for status in statuses)
		else:
			is_ok = any(status in {"Subido", "Aprobado"} for status in statuses)

		if is_ok:
			ok += 1
		else:
			missing.append(req.name)

	percent = int(round((ok / len(required)) * 100)) if required else 100
	return {
		"required_total": len(required),
		"required_ok": ok,
		"missing": missing,
		"percent": percent,
		"is_complete": ok == len(required),
	}


def set_candidate_status_from_progress(candidate):
	current_status = frappe.db.get_value("Candidato", candidate, "estado_proceso")
	if is_candidate_status(current_status, STATE_EXAMEN_MEDICO):
		return current_status

	get_candidate_progress(candidate)
	status = resolve_candidate_status_for_storage(
		STATE_DOCUMENTACION,
		options=get_candidate_status_options(),
		default=STATE_DOCUMENTACION,
	)
	frappe.db.set_value("Candidato", candidate, "estado_proceso", status, update_modified=False)
	return status


def upload_person_document(person_type, person, document_type, file_url, notes=None, numero_documento=None):
	repair_person_document_links(person_type=person_type, person=person)
	person = _resolve_person_name(person_type, person)
	rules = _get_document_type_rules(document_type)
	resolved_document_type = rules["document_type"]
	if rules["allows_multiple"]:
		pending_name = _find_pending_document_row(person_type, person, resolved_document_type)
		doc = frappe.get_doc("Person Document", pending_name) if pending_name else _new_person_document(person_type, person, resolved_document_type)
	else:
		doc = ensure_person_document(person_type, person, resolved_document_type)

	_sync_person_document_identity(doc, person_type, person)

	renamed_file_url = file_url
	if person_type == "Candidato":
		renamed_file_url = rename_uploaded_candidate_file(
			file_url=file_url,
			document_type=resolved_document_type,
			candidate=person,
			numero_documento=numero_documento,
		)

	doc.notes = notes
	doc.uploaded_by = frappe.session.user
	doc.uploaded_on = now()

	doc.file = renamed_file_url
	doc.status = "Subido"
	if rules["requires_approval"] and user_has_any_role(frappe.session.user, "HR Labor Relations", "Relaciones Laborales Jefe"):
		doc.status = "Aprobado"
		doc.approved_by = frappe.session.user
		doc.approved_on = now()

	doc.save(ignore_permissions=True)

	if person_type == "Candidato":
		set_candidate_status_from_progress(person)

	return doc


def send_candidate_to_labor_relations(candidate, pdv_destino=None, fecha_tentativa_ingreso=None):
	if not user_has_any_role(frappe.session.user, "HR Selection") and frappe.session.user != "Administrator":
		frappe.throw(_("No autorizado para enviar candidatos a Relaciones Laborales."))

	progress = get_candidate_progress(candidate)
	if not progress["is_complete"]:
		frappe.throw(_("No se puede enviar: documentación requerida incompleta."))

	candidate_doc = frappe.get_doc("Candidato", candidate)
	handoff_gate = validate_selection_to_rrll_gate(
		{
			"candidate": candidate,
			"medical_concept": candidate_doc.get("concepto_medico"),
			"required_documents": {
				"SAGRILAFT": _candidate_has_uploaded_document(candidate, "SAGRILAFT"),
			},
			"target_data": {
				"pdv_destino": pdv_destino or candidate_doc.get("pdv_destino"),
				"fecha_tentativa_ingreso": fecha_tentativa_ingreso or candidate_doc.get("fecha_tentativa_ingreso"),
			},
		}
	)
	if handoff_gate.get("status") != "ready":
		frappe.throw(
			_(
				"No se puede enviar a RRLL: gate mínimo incompleto"
				+ (f" ({', '.join(handoff_gate.get('errors') or [])})" if handoff_gate.get("errors") else "")
			)
		)

	updates = {"estado_proceso": STATE_AFILIACION}
	if pdv_destino:
		updates["pdv_destino"] = pdv_destino
	if fecha_tentativa_ingreso:
		updates["fecha_tentativa_ingreso"] = fecha_tentativa_ingreso
	frappe.db.set_value("Candidato", candidate, updates)

	persona = frappe.db.get_value("Candidato", candidate, "persona")
	if persona and frappe.db.exists("Ficha Empleado", persona):
		persona_updates = {}
		if pdv_destino:
			persona_updates["pdv"] = pdv_destino
		if fecha_tentativa_ingreso:
			persona_updates["fecha_ingreso"] = fecha_tentativa_ingreso
		if persona_updates:
			frappe.db.set_value("Ficha Empleado", persona, persona_updates)

	if not frappe.db.exists("Datos Contratacion", {"candidato": candidate}):
		frappe.get_doc({
			"doctype": "Datos Contratacion",
			"candidato": candidate,
		}).insert(ignore_permissions=True)

	return {"ok": True, "status": STATE_AFILIACION, "handoff_gate": handoff_gate}


def hire_candidate(candidate):
	if not user_has_any_role(frappe.session.user, "HR Labor Relations", "Relaciones Laborales Jefe") and frappe.session.user != "Administrator":
		frappe.throw(_("No autorizado para contratar."))

	cand = frappe.get_doc("Candidato", candidate)
	if not is_candidate_status(cand.estado_proceso, STATE_LISTO_CONTRATAR):
		frappe.throw(_("El candidato debe estar en estado Listo para contratar."))

	if cand.persona and frappe.db.exists("Ficha Empleado", cand.persona):
		emp = frappe.get_doc("Ficha Empleado", cand.persona)
		employee = emp.name
	else:
		emp = frappe.get_doc({
			"doctype": "Ficha Empleado",
			"nombres": cand.nombres,
			"apellidos": _candidate_apellidos_fallback(cand),
			"cedula": cand.numero_documento,
			"pdv": cand.pdv_destino,
			"cargo": cand.cargo_postulado,
			"fecha_ingreso": cand.fecha_tentativa_ingreso,
			"email": cand.email,
		}).insert(ignore_permissions=True, ignore_mandatory=True)
		employee = emp.name

	emp_updates = _sync_employee_from_candidate(emp, cand)
	if emp_updates:
		emp.save(ignore_permissions=True)

	frappe.db.set_value("Candidato", candidate, "persona", employee)

	datos_name = frappe.db.get_value("Datos Contratacion", {"candidato": candidate})
	if datos_name:
		datos = frappe.get_doc("Datos Contratacion", datos_name)
	else:
		datos = frappe.get_doc({
			"doctype": "Datos Contratacion",
			"candidato": candidate,
		})
	if not datos.ficha_empleado:
		datos.ficha_empleado = employee
	if not getattr(datos, "contrato", None):
		ultimo_contrato = frappe.db.get_value("Contrato", {"candidato": candidate}, "name", order_by="creation desc")
		if ultimo_contrato:
			datos.contrato = ultimo_contrato
	if getattr(datos, "name", None):
		datos.save(ignore_permissions=True)
	else:
		datos.insert(ignore_permissions=True)

	pdocs = frappe.get_all(
		"Person Document",
		filters={"person_type": "Candidato", "person": candidate},
		fields=["name"],
	)
	for row in pdocs:
		doc = frappe.get_doc("Person Document", row.name)
		doc.employee = employee
		doc.save(ignore_permissions=True)

	frappe.db.set_value("Candidato", candidate, "estado_proceso", STATE_CONTRATADO)
	return {"ok": True, "employee": employee}


def build_candidate_documents_zip(candidate):
	dossier = _build_person_dossier("Candidato", candidate)
	docs = list(dossier.get("vigentes") or []) + list(dossier.get("historico") or [])

	buf = io.BytesIO()
	with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
		for row in docs:
			file_url = _row_get(row, "file")
			if not file_url:
				continue
			abs_path = frappe.get_site_path(str(file_url).lstrip("/"))
			if not os.path.exists(abs_path):
				continue
			ext = os.path.splitext(abs_path)[1] or ""
			safe_name = (str(_row_get(row, "document_type") or "documento")).replace("/", "-")
			version = int(_row_get(row, "version", 1) or 1)
			suffix = "_vigente" if _row_get(row, "is_vigente", True) else "_historico"
			zf.write(abs_path, arcname=f"{safe_name}_v{version}{suffix}{ext}")

	zip_name = f"candidato_{candidate}_documentos.zip"
	file_doc = save_file(zip_name, buf.getvalue(), "Candidato", candidate, is_private=1)
	return file_doc.file_url


def build_employee_documents_zip(employee):
	emp = frappe.get_doc("Ficha Empleado", employee)

	docs = []
	employee_rows = frappe.get_all(
		"Person Document",
		filters={
			"file": ["is", "set"],
			"employee": employee,
		},
		fields=["name", "document_type", "status", "file", "uploaded_on", "approved_on", "modified", "creation"],
	)
	for row in employee_rows:
		docs.append({
			"document_type": _row_get(row, "document_type"),
			"file": _row_get(row, "file"),
			"version": 1,
			"is_vigente": True,
		})

	candidate_origin = getattr(emp, "candidato_origen", None) or frappe.db.get_value("Candidato", {"persona": employee}, "name")
	if candidate_origin:
		cand_dossier = _build_person_dossier("Candidato", candidate_origin)
		docs.extend(cand_dossier.get("vigentes") or [])
		docs.extend(cand_dossier.get("historico") or [])

	for c in frappe.get_all(
		"Contrato",
		filters={"empleado": employee, "contrato_firmado": ["is", "set"]},
		fields=["name", "contrato_firmado"],
	):
		docs.append({"document_type": f"Contrato {c.name}", "file": c.contrato_firmado})

	buf = io.BytesIO()
	with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
		for row in docs:
			file_url = _row_get(row, "file")
			if not file_url:
				continue
			abs_path = frappe.get_site_path(str(file_url).lstrip("/"))
			if not os.path.exists(abs_path):
				continue
			ext = os.path.splitext(abs_path)[1] or ""
			safe_name = (str(_row_get(row, "document_type") or "documento")).replace("/", "-")
			version = int(_row_get(row, "version", 1) or 1)
			suffix = "_vigente" if _row_get(row, "is_vigente", True) else "_historico"
			zf.write(abs_path, arcname=f"{safe_name}_v{version}{suffix}{ext}")

	zip_name = f"empleado_{employee}_documentos.zip"
	file_doc = save_file(zip_name, buf.getvalue(), "Ficha Empleado", employee, is_private=1)
	return file_doc.file_url
