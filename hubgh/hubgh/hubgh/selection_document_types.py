import json
import unicodedata

import frappe


LEGACY_REQUIRED_CANDIDATE_DOCS = [
	{
		"legacy_documento_requerido": "DOC_HV",
		"document_name": "Hoja de vida actualizada.",
		"description": "Hoja de vida actualizada.",
	},
	{
		"legacy_documento_requerido": "DOC_ID",
		"document_name": "Fotocopia del documento de identidad al 150%.",
		"description": "Fotocopia del documento de identidad al 150%.",
	},
	{
		"legacy_documento_requerido": "DOC_BANCO",
		"document_name": "Certificación bancaria (No mayor a 30 días).",
		"description": "En caso de no tener cuenta bancaria, favor escribir por medio de WhatsApp para poder remitir la Carta de apertura de cuenta bancaria con Bancolombia.",
	},
	{
		"legacy_documento_requerido": "DOC_MANIP",
		"document_name": "Carnet manipulación de alimentos.",
		"description": "En caso de no tener el curso favor realizarlo en el menor tiempo posible y adjuntar certificado.",
	},
	{
		"legacy_documento_requerido": "DOC_EPS",
		"document_name": "Certificado de EPS (Salud).",
		"description": "No mayor a 30 días. https://www.adres.gov.co/consulte-su-eps",
	},
	{
		"legacy_documento_requerido": "DOC_PENSION",
		"document_name": "Certificado de fondo de pensiones.",
		"description": "No mayor a 30 días.",
	},
	{
		"legacy_documento_requerido": "DOC_CESANTIAS",
		"document_name": "Certificado de fondo de cesantías.",
		"description": "No mayor a 30 días.",
	},
	{
		"legacy_documento_requerido": "DOC_ESTUDIOS",
		"document_name": "Certificados de estudios y/o actas de grado Bachiller y posteriores.",
		"description": "Certificados de estudios y/o actas de grado Bachiller y posteriores.",
	},
	{
		"legacy_documento_requerido": "DOC_REFERENCIAS",
		"document_name": "2 cartas de referencias personales.",
		"description": "Deben estar firmadas en físico o digital.",
	},
]


SELECTION_OPERATIONAL_DOCS = [
	{
		"document_name": "Carta Oferta",
		"is_required_for_hiring": 0,
		"is_optional": 1,
		"aliases": ["Carta oferta"],
	},
	{
		"document_name": "SAGRILAFT",
		"is_required_for_hiring": 1,
		"is_optional": 0,
		"aliases": [],
	},
	{
		"document_name": "Autorización de Descuento",
		"is_required_for_hiring": 0,
		"is_optional": 1,
		"aliases": ["Autorización de descuento"],
	},
	{
		"document_name": "Autorización de Ingreso",
		"is_required_for_hiring": 0,
		"is_optional": 1,
		"aliases": ["Documento autorización de ingreso"],
	},
	{
		"document_name": "Examen Médico",
		"is_required_for_hiring": 0,
		"is_optional": 1,
		"aliases": ["Examen medico", "Concepto Médico", "Concepto medico", "Aptitud Médica", "Aptitud medica"],
	},
]


SELECTION_WORKSPACE_SHORTCUT_LABEL = "Tipos de documento"
SELECTION_WORKSPACE_SHORTCUT_LINK = "Document Type"
SELECTION_WORKSPACE_LEGACY_LABEL = "Documentos requeridos"
SELECTION_WORKSPACE_NAME = "Selección"


def _normalize_text(value):
	text = str(value or "").strip().lower()
	if not text:
		return ""
	return "".join(ch for ch in unicodedata.normalize("NFKD", text) if not unicodedata.combining(ch))


def _selection_alias_map():
	alias_map = {}
	for row in SELECTION_OPERATIONAL_DOCS:
		canonical = row["document_name"]
		for name in [canonical, *(row.get("aliases") or [])]:
			alias_map[_normalize_text(name)] = canonical
	return alias_map


def canonicalize_selection_document_name(document_name):
	requested = str(document_name or "").strip()
	if not requested:
		return requested
	return _selection_alias_map().get(_normalize_text(requested), requested)


def get_selection_operational_document_names():
	return [row["document_name"] for row in SELECTION_OPERATIONAL_DOCS]


def get_selection_document_lookup_names(document_name):
	canonical = canonicalize_selection_document_name(document_name)
	lookup = {canonical}
	for row in SELECTION_OPERATIONAL_DOCS:
		if row["document_name"] != canonical:
			continue
		lookup.update(row.get("aliases") or [])
		break
	return sorted(name for name in lookup if name)


def sync_selection_document_types():
	if not frappe.db.exists("DocType", "Document Type"):
		return {"created": [], "updated": [], "renamed": [], "deactivated": []}

	result = {"created": [], "updated": [], "renamed": [], "deactivated": []}

	for row in LEGACY_REQUIRED_CANDIDATE_DOCS:
		legacy_name = row["legacy_documento_requerido"] if _legacy_required_document_exists(row["legacy_documento_requerido"]) else None
		_upsert_document_type(
			{
				"document_name": row["document_name"],
				"is_active": 1,
				"candidate_uploads": 1,
				"allows_multiple": 1 if row["document_name"] == "2 cartas de referencias personales." else 0,
				"is_required_for_hiring": 1,
				"is_optional": 0,
				"applies_to": "Candidato",
				"requires_approval": 0,
				"requires_for_employee_folder": 0,
				"legacy_documento_requerido": legacy_name,
				"allowed_roles_override": "",
			},
			aliases=[],
			result=result,
		)

	for row in SELECTION_OPERATIONAL_DOCS:
		_upsert_document_type(
			{
				"document_name": row["document_name"],
				"is_active": 1,
				"candidate_uploads": 0,
				"allows_multiple": 0,
				"is_required_for_hiring": int(row["is_required_for_hiring"] or 0),
				"is_optional": int(row["is_optional"] or 0),
				"applies_to": "Candidato",
				"requires_approval": 0,
				"requires_for_employee_folder": 0,
				"allowed_roles_override": "HR Selection",
			},
			aliases=row.get("aliases") or [],
			result=result,
		)

	return result


def sync_selection_workspace_shortcut():
	if not frappe.db.exists("Workspace", SELECTION_WORKSPACE_NAME):
		return False

	workspace = frappe.get_doc("Workspace", SELECTION_WORKSPACE_NAME)
	changed = False

	for row in workspace.shortcuts or []:
		label = str(getattr(row, "label", "") or "").strip()
		link_to = str(getattr(row, "link_to", "") or "").strip()
		if link_to not in {"Documento Requerido", SELECTION_WORKSPACE_SHORTCUT_LINK} and label not in {
			SELECTION_WORKSPACE_LEGACY_LABEL,
			SELECTION_WORKSPACE_SHORTCUT_LABEL,
		}:
			continue
		if label != SELECTION_WORKSPACE_SHORTCUT_LABEL:
			row.label = SELECTION_WORKSPACE_SHORTCUT_LABEL
			changed = True
		if link_to != SELECTION_WORKSPACE_SHORTCUT_LINK:
			row.link_to = SELECTION_WORKSPACE_SHORTCUT_LINK
			changed = True
		if getattr(row, "type", None) != "DocType":
			row.type = "DocType"
			changed = True
		if getattr(row, "doc_view", None) != "List":
			row.doc_view = "List"
			changed = True

	content = str(getattr(workspace, "content", "") or "").strip()
	if content:
		try:
			blocks = json.loads(content)
		except Exception:
			blocks = None
		if isinstance(blocks, list):
			for block in blocks:
				if block.get("type") != "shortcut":
					continue
				data = block.get("data") or {}
				shortcut_name = str(data.get("shortcut_name") or "").strip()
				if shortcut_name not in {SELECTION_WORKSPACE_LEGACY_LABEL, SELECTION_WORKSPACE_SHORTCUT_LABEL}:
					continue
				if data.get("shortcut_name") != SELECTION_WORKSPACE_SHORTCUT_LABEL:
					data["shortcut_name"] = SELECTION_WORKSPACE_SHORTCUT_LABEL
					changed = True
			new_content = json.dumps(blocks, ensure_ascii=False, separators=(",", ":"))
			if new_content != workspace.content:
				workspace.content = new_content
				changed = True

	if changed:
		workspace.save(ignore_permissions=True)

	return changed


def _upsert_document_type(payload, aliases, result):
	canonical_name = payload["document_name"]
	canonical_doc = _get_existing_document_type(canonical_name)
	alias_docs = [doc for doc in (_get_existing_document_type(alias) for alias in aliases) if doc]

	if not canonical_doc and alias_docs:
		primary_alias = alias_docs[0]
		if primary_alias.name != canonical_name:
			frappe.rename_doc("Document Type", primary_alias.name, canonical_name, force=True, merge=False)
			result["renamed"].append(f"{primary_alias.name}->{canonical_name}")
		canonical_doc = _get_existing_document_type(canonical_name)
		alias_docs = [doc for doc in (_get_existing_document_type(alias) for alias in aliases) if doc]

	if canonical_doc:
		doc = frappe.get_doc("Document Type", canonical_doc.name)
		action = "updated"
	else:
		doc = frappe.get_doc({"doctype": "Document Type", "document_name": canonical_name})
		action = "created"

	for fieldname, value in payload.items():
		setattr(doc, fieldname, value)

	if doc.is_new():
		doc.insert(ignore_permissions=True)
	else:
		doc.save(ignore_permissions=True)

	result[action].append(canonical_name)

	for alias_doc in alias_docs:
		if alias_doc.name == canonical_name:
			continue
		_repoint_person_documents(alias_doc.name, canonical_name)
		alias_record = frappe.get_doc("Document Type", alias_doc.name)
		alias_record.is_active = 0
		alias_record.candidate_uploads = 0
		alias_record.is_required_for_hiring = 0
		alias_record.is_optional = 1
		alias_record.applies_to = alias_record.applies_to or "Candidato"
		alias_record.save(ignore_permissions=True)
		result["deactivated"].append(alias_doc.name)


def _get_existing_document_type(name):
	if not name:
		return None
	rows = frappe.get_all(
		"Document Type",
		filters={"name": name},
		fields=["name", "document_name"],
		limit_page_length=1,
	)
	return rows[0] if rows else None


def _legacy_required_document_exists(name):
	if not name:
		return False
	return bool(frappe.db.exists("Documento Requerido", name))


def _repoint_person_documents(from_name, to_name):
	if from_name == to_name:
		return
	frappe.db.sql(
		"update `tabPerson Document` set document_type=%s where document_type=%s",
		(to_name, from_name),
	)
