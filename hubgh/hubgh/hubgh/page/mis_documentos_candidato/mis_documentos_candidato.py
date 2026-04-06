import frappe

from hubgh.hubgh.document_service import ensure_person_document, upload_person_document
from hubgh.hubgh.siesa_reference_matrix import ensure_social_security_reference_catalogs


META_FIELDS_BY_DOC = {
	"Certificado de EPS (Salud).": {"eps_siesa"},
	"Certificado de fondo de pensiones.": {"afp_siesa"},
	"Certificado de fondo de cesantías.": {"cesantias_siesa"},
	"Certificación bancaria (No mayor a 30 días).": {"banco_siesa", "tipo_cuenta_bancaria", "numero_cuenta_bancaria"},
	"Certificados de estudios y/o actas de grado Bachiller y posteriores.": {"nivel_educativo_siesa"},
}


CATALOG_SOURCES = {
	"eps": ("Entidad EPS Siesa", "eps_siesa"),
	"afp": ("Entidad AFP Siesa", "afp_siesa"),
	"cesantias": ("Entidad Cesantias Siesa", "cesantias_siesa"),
	"bancos": ("Banco Siesa", "banco_siesa"),
}


CANDIDATE_UPLOAD_DOCS = [
	"Hoja de vida actualizada.",
	"Fotocopia del documento de identidad al 150%.",
	"Certificación bancaria (No mayor a 30 días).",
	"Carnet manipulación de alimentos.",
	"Certificado de EPS (Salud).",
	"Certificado de fondo de pensiones.",
	"Certificado de fondo de cesantías.",
	"Certificados de estudios y/o actas de grado Bachiller y posteriores.",
	"2 cartas de referencias personales.",
]


SECTION_LABELS = {
	"documental": "Documental",
	"bancaria": "Bancaria",
	"seguridad_social": "Seguridad Social",
}


FIELD_TO_CATALOG_DOCTYPE = {
	"eps_siesa": "Entidad EPS Siesa",
	"afp_siesa": "Entidad AFP Siesa",
	"cesantias_siesa": "Entidad Cesantias Siesa",
	"banco_siesa": "Banco Siesa",
}


def _get_my_candidate_name():
	user = frappe.session.user
	if not user or user == "Guest":
		frappe.throw("Debes iniciar sesión para continuar.")

	candidate = frappe.db.get_value("Candidato", {"user": user}, "name")
	if not candidate:
		frappe.throw("No encontramos tu candidato asociado al usuario actual.")
	return candidate


def _section_for_document(document_type: str, label: str | None = None) -> str:
	text = f"{document_type or ''} {label or ''}".lower()
	if "banc" in text:
		return "bancaria"
	if any(token in text for token in ("eps", "pens", "cesant", "seguridad social")):
		return "seguridad_social"
	return "documental"


def _is_uploaded_ok(status: str | None, file_url: str | None) -> bool:
	return bool(file_url) and (status or "") in {"Subido", "Aprobado"}


def _cleanup_duplicate_pending_documents(candidate, document_types):
	for document_type in document_types or []:
		pending_rows = frappe.get_all(
			"Person Document",
			filters={
				"person_type": "Candidato",
				"person": candidate,
				"document_type": document_type,
				"file": ["is", "not set"],
			},
			fields=["name"],
			order_by="modified desc",
		)
		if len(pending_rows) <= 1:
			continue

		for row in pending_rows[1:]:
			frappe.delete_doc("Person Document", row.name, ignore_permissions=True, force=1)


@frappe.whitelist()
def get_my_documents():
	candidate = _get_my_candidate_name()
	cand = frappe.get_doc("Candidato", candidate)
	has_candidate_uploads_field = frappe.db.has_column("Document Type", "candidate_uploads")
	doc_type_filters = {
		"is_active": 1,
		"applies_to": ["in", ["Candidato", "Ambos"]],
	}
	if has_candidate_uploads_field:
		doc_type_filters["candidate_uploads"] = 1
	else:
		doc_type_filters["name"] = ["in", CANDIDATE_UPLOAD_DOCS]

	doc_types = frappe.get_all(
		"Document Type",
		filters=doc_type_filters,
		fields=["name", "document_name", "is_required_for_hiring", "requires_approval", "allows_multiple"],
		order_by="is_required_for_hiring desc, document_name asc",
	)

	for dt in doc_types:
		ensure_person_document("Candidato", candidate, dt.name)

	_cleanup_duplicate_pending_documents(candidate, [d.name for d in doc_types])

	docs = frappe.get_all(
		"Person Document",
		filters={"person_type": "Candidato", "person": candidate},
		fields=["name", "document_type", "status", "file", "uploaded_on", "notes"],
		order_by="uploaded_on desc, modified desc",
	)
	docs_by_type = {}
	for row in docs:
		docs_by_type.setdefault(row.document_type, []).append(row)

	section_progress = {
		"documental": {"label": SECTION_LABELS["documental"], "required_total": 0, "uploaded_ok": 0},
		"bancaria": {"label": SECTION_LABELS["bancaria"], "required_total": 0, "uploaded_ok": 0},
		"seguridad_social": {"label": SECTION_LABELS["seguridad_social"], "required_total": 0, "uploaded_ok": 0},
	}

	items = []
	for dt in doc_types:
		rows = docs_by_type.get(dt.name) or []
		latest_row = rows[0] if rows else None
		files = [
			{
				"name": row.name,
				"file": row.file,
				"status": row.status,
				"uploaded_on": row.uploaded_on,
				"notes": row.notes,
			}
			for row in rows
			if row.file
		]
		section_key = _section_for_document(dt.name, dt.document_name)
		if int(dt.is_required_for_hiring or 0):
			section_progress[section_key]["required_total"] += 1
			if any(_is_uploaded_ok(f.get("status"), f.get("file")) for f in files):
				section_progress[section_key]["uploaded_ok"] += 1
		items.append(
			{
				"document_type": dt.name,
				"label": dt.document_name or dt.name,
				"section": section_key,
				"has_metadata": int(bool(META_FIELDS_BY_DOC.get(dt.name))),
				"required_for_hiring": int(dt.is_required_for_hiring or 0),
				"requires_approval": int(dt.requires_approval or 0),
				"allows_multiple": int(dt.allows_multiple or 0),
				"status": latest_row.status if latest_row else "Pendiente",
				"file": latest_row.file if latest_row else None,
				"uploaded_on": latest_row.uploaded_on if latest_row else None,
				"notes": latest_row.notes if latest_row else None,
				"files": files,
			}
		)

	for section in section_progress.values():
		required_total = int(section.get("required_total") or 0)
		uploaded_ok = int(section.get("uploaded_ok") or 0)
		section["percent"] = int(round((uploaded_ok / required_total) * 100)) if required_total else 100
		section["is_complete"] = required_total == 0 or uploaded_ok >= required_total

	return {
		"candidate": candidate,
		"candidate_data": {
			"eps_siesa": cand.eps_siesa,
			"afp_siesa": cand.afp_siesa,
			"cesantias_siesa": cand.cesantias_siesa,
			"banco_siesa": cand.banco_siesa,
			"nivel_educativo_siesa": cand.nivel_educativo_siesa,
			"tipo_cuenta_bancaria": cand.tipo_cuenta_bancaria,
			"numero_cuenta_bancaria": cand.numero_cuenta_bancaria,
		},
		"documents": items,
		"section_progress": section_progress,
	}


def _catalog_rows(doctype):
	has_enabled = frappe.db.has_column(doctype, "enabled")
	fields = ["name", "description"]
	if has_enabled:
		fields.append("enabled")

	rows = frappe.get_all(
		doctype,
		fields=fields,
		order_by="description asc, name asc",
		ignore_permissions=True,
	)
	return [
		{
			"value": row.name,
			"label": f"{row.description} - {row.name}" if row.description else row.name,
		}
		for row in rows
		if (not has_enabled) or int(getattr(row, "enabled", 0) or 0) == 1
	]


@frappe.whitelist()
def get_siesa_options():
	_get_my_candidate_name()
	ensure_social_security_reference_catalogs()
	return {
		"eps": _catalog_rows(CATALOG_SOURCES["eps"][0]),
		"afp": _catalog_rows(CATALOG_SOURCES["afp"][0]),
		"cesantias": _catalog_rows(CATALOG_SOURCES["cesantias"][0]),
		"bancos": _catalog_rows(CATALOG_SOURCES["bancos"][0]),
	}


def _normalize_link_catalog_value(fieldname, value):
	if not value:
		return value

	value = str(value).strip()
	if fieldname not in {"eps_siesa", "afp_siesa", "cesantias_siesa", "banco_siesa"}:
		return value

	doctype = FIELD_TO_CATALOG_DOCTYPE[fieldname]
	if frappe.db.exists(doctype, value):
		return value

	if " - " in value:
		left, right = [p.strip() for p in value.split(" - ", 1)]
		# Compatibilidad: soporta tanto "codigo - descripcion" como "descripcion - codigo"
		for candidate in (left, right):
			if candidate and frappe.db.exists(doctype, candidate):
				return candidate

	match_by_description = frappe.db.get_value(doctype, {"description": value}, "name")
	if match_by_description:
		return match_by_description

	frappe.throw(f"La opción seleccionada para {fieldname} no es válida.")


@frappe.whitelist()
def upload_my_document(document_type, file_url, notes=None):
	candidate = _get_my_candidate_name()
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
def save_my_document_meta(document_type, payload):
	candidate = _get_my_candidate_name()
	data = payload or {}
	if isinstance(payload, str):
		import json

		data = json.loads(payload or "{}")

	allowed_fields = META_FIELDS_BY_DOC.get(document_type, set())
	if not allowed_fields:
		return {"ok": True, "updated_fields": []}

	updates = {}
	for fieldname in allowed_fields:
		if fieldname in data:
			updates[fieldname] = _normalize_link_catalog_value(fieldname, data.get(fieldname))

	if updates:
		frappe.db.set_value("Candidato", candidate, updates)

	return {"ok": True, "updated_fields": sorted(list(updates.keys()))}
