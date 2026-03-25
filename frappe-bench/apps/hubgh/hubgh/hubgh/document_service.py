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
	is_candidate_status,
)
from hubgh.hubgh.doctype.document_type.document_type import get_effective_area_roles
from hubgh.hubgh.people_ops_handoffs import validate_selection_to_rrll_gate
from hubgh.hubgh.people_ops_policy import evaluate_dimension_access, resolve_document_dimension
from hubgh.hubgh.role_matrix import roles_have_any, user_has_any_role


_MULTI_UPLOAD_DOCUMENT_TYPES_FALLBACK = {
	"2 cartas de referencias personales.",
	"certificados de estudios y/o actas de grado bachiller y posteriores.",
}


def _normalize_text(value):
	text = str(value or "").strip().lower()
	if not text:
		return ""
	return "".join(ch for ch in unicodedata.normalize("NFKD", text) if not unicodedata.combining(ch))


def _resolve_document_type_name(document_type):
	requested = (document_type or "").strip()
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
	name = (doc_type_row.get("document_name") or doc_type_row.get("name") or "").strip().lower()
	return name == "contrato"


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


def can_user_read_person_document(doc, user=None):
	user = user or frappe.session.user
	if user == "Administrator":
		return True

	if user_has_any_role(user, "HR Labor Relations"):
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
	if dimension == "clinical" and user_has_any_role(user, "HR SST", "HR Labor Relations", "System Manager"):
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
	rows = frappe.get_all(
		"Person Document",
		filters={
			"person_type": "Candidato",
			"person": candidate,
			"document_type": document_type,
			"status": ["in", ["Subido", "Aprobado"]],
			"file": ["is", "set"],
		},
		fields=["name"],
		limit_page_length=1,
	)
	return bool(rows)


def _find_pending_document_row(person_type, person, document_type):
	rows = frappe.get_all(
		"Person Document",
		filters={
			"person_type": person_type,
			"person": person,
			"document_type": document_type,
			"file": ["is", "not set"],
		},
		fields=["name"],
		order_by="modified desc",
		limit_page_length=1,
	)
	return rows[0].name if rows else None


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
	rows = frappe.get_all(
		"Person Document",
		filters={"person_type": person_type, "person": person},
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
	doc = frappe.get_doc({
		"doctype": "Person Document",
		"person_type": person_type,
		"person_doctype": "Candidato" if person_type == "Candidato" else "Ficha Empleado",
		"person": person,
		"document_type": document_type,
		"status": "Pendiente",
	})
	doc.insert(ignore_permissions=True)
	return doc


def ensure_person_document(person_type, person, document_type):
	rules = _get_document_type_rules(document_type)
	resolved_document_type = rules["document_type"]
	if not rules["allows_multiple"]:
		existing = frappe.db.get_value(
			"Person Document",
			{"person_type": person_type, "person": person, "document_type": resolved_document_type},
		)
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

	progress = get_candidate_progress(candidate)
	status = STATE_DOCUMENTACION
	frappe.db.set_value("Candidato", candidate, "estado_proceso", status, update_modified=False)
	return status


def upload_person_document(person_type, person, document_type, file_url, notes=None, numero_documento=None):
	rules = _get_document_type_rules(document_type)
	resolved_document_type = rules["document_type"]
	if rules["allows_multiple"]:
		pending_name = _find_pending_document_row(person_type, person, resolved_document_type)
		doc = frappe.get_doc("Person Document", pending_name) if pending_name else _new_person_document(person_type, person, resolved_document_type)
	else:
		doc = ensure_person_document(person_type, person, resolved_document_type)

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
	if rules["requires_approval"] and user_has_any_role(frappe.session.user, "HR Labor Relations"):
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
	if not user_has_any_role(frappe.session.user, "HR Labor Relations") and frappe.session.user != "Administrator":
		frappe.throw(_("No autorizado para contratar."))

	cand = frappe.get_doc("Candidato", candidate)
	if not is_candidate_status(cand.estado_proceso, STATE_LISTO_CONTRATAR):
		frappe.throw(_("El candidato debe estar en estado Listo para contratar."))

	if cand.persona and frappe.db.exists("Ficha Empleado", cand.persona):
		employee = cand.persona
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

	frappe.db.set_value("Candidato", candidate, "persona", employee)

	datos_name = frappe.db.get_value("Datos Contratacion", {"candidato": candidate})
	if datos_name:
		datos = frappe.get_doc("Datos Contratacion", datos_name)
		if not datos.ficha_empleado:
			datos.ficha_empleado = employee
		datos.save(ignore_permissions=True)

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

	if emp.candidato_origen:
		cand_dossier = _build_person_dossier("Candidato", emp.candidato_origen)
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
