import json
import unicodedata
from datetime import date
from pathlib import Path

import frappe
from frappe.utils import getdate, now_datetime

from hubgh.hubgh.candidate_states import (
	STATE_AFILIACION,
	STATE_LISTO_CONTRATAR,
	candidate_status_filter_values,
)
from hubgh.hubgh.people_ops_handoffs import validate_handoff_contract
from hubgh.hubgh.payroll_employee_compat import normalize_tipo_jornada
from hubgh.hubgh.role_matrix import user_has_any_role
from hubgh.hubgh.siesa_reference_matrix import ensure_reference_catalog, normalize_code_for_doctype


AFFILIATION_TYPES = {
	"eps": {
		"label": "EPS",
		"afiliado": "eps_afiliado",
		"fecha": "eps_fecha_afiliacion",
		"numero": "eps_numero_afiliacion",
		"certificado": "eps_certificado",
	},
	"afp": {
		"label": "AFP",
		"afiliado": "afp_afiliado",
		"fecha": "afp_fecha_afiliacion",
		"numero": "afp_numero_afiliacion",
		"certificado": "afp_certificado",
	},
	"cesantias": {
		"label": "Cesantías",
		"afiliado": "cesantias_afiliado",
		"fecha": "cesantias_fecha_afiliacion",
		"numero": "cesantias_numero_afiliacion",
		"certificado": "cesantias_certificado",
	},
	"caja": {
		"label": "Caja",
		"afiliado": "caja_afiliado",
		"fecha": "caja_fecha_afiliacion",
		"numero": "caja_numero_afiliacion",
		"certificado": "caja_certificado",
	},
	"arl": {
		"label": "ARL",
		"afiliado": "arl_afiliado",
		"fecha": "arl_fecha_afiliacion",
		"numero": "arl_numero_afiliacion",
		"certificado": "arl_certificado",
	},
}

CANDIDATE_SIESA_ENTITY_FIELDS = {
	"eps": {"field": "eps_siesa", "doctype": "Entidad EPS Siesa"},
	"afp": {"field": "afp_siesa", "doctype": "Entidad AFP Siesa"},
	"cesantias": {"field": "cesantias_siesa", "doctype": "Entidad Cesantias Siesa"},
}

SIESA_REQUIRED_FIELDS = {
	"tipo_cotizante_siesa": {"label": "tipo cotizante", "doctype": "Tipo Cotizante Siesa"},
	"centro_costos_siesa": {"label": "centro de costos", "doctype": "Centro Costos Siesa"},
	"unidad_negocio_siesa": {"label": "unidad de negocio", "doctype": "Unidad Negocio Siesa"},
	"centro_trabajo_siesa": {"label": "centro de trabajo", "doctype": "Centro Trabajo Siesa"},
	"grupo_empleados_siesa": {"label": "grupo de empleados", "doctype": "Grupo Empleados Siesa"},
}

SIESA_JSON_KEY_BY_DOCTYPE = {
	"Tipo Cotizante Siesa": "tipos_cotizante",
	"Centro Costos Siesa": "centros_costo",
	"Unidad Negocio Siesa": "unidades_negocio",
}

_SIESA_CATALOG_CACHE = None


MANDATORY_INGRESO_FIELDS = [
	("numero_documento", "número de documento"),
	("nombres", "nombres"),
	("apellidos", "apellidos"),
	("pdv_destino", "PDV destino"),
	("cargo", "cargo"),
	("fecha_ingreso", "fecha de ingreso"),
	("tipo_contrato", "tipo de contrato"),
]


def _user_is_hr():
	user = frappe.session.user
	return user == "Administrator" or user_has_any_role(user, "Gestión Humana", "HR Labor Relations", "System Manager")


def _user_is_rrll_authority():
	user = frappe.session.user
	return user == "Administrator" or user_has_any_role(user, "HR Labor Relations", "System Manager")


def validate_hr_access():
	if not _user_is_hr():
		frappe.throw("No autorizado")


def validate_rrll_authority():
	if not _user_is_rrll_authority():
		frappe.throw("No autorizado: la formalización de ingreso requiere autoridad RRLL")


def _candidate_full_name(row):
	apellidos = (row.get("apellidos") if isinstance(row, dict) else getattr(row, "apellidos", None)) or ""
	if not str(apellidos).strip():
		primer = (row.get("primer_apellido") if isinstance(row, dict) else getattr(row, "primer_apellido", None)) or ""
		segundo = (row.get("segundo_apellido") if isinstance(row, dict) else getattr(row, "segundo_apellido", None)) or ""
		apellidos = " ".join([p.strip() for p in [primer, segundo] if p and str(p).strip()]).strip()

	parts = [
		(row.get("nombres") if isinstance(row, dict) else getattr(row, "nombres", None)) or "",
		apellidos,
	]
	name = " ".join([p.strip() for p in parts if p and str(p).strip()]).strip()
	if name:
		return name

	numero_documento = (row.get("numero_documento") if isinstance(row, dict) else getattr(row, "numero_documento", None)) or ""
	if numero_documento:
		return f"Candidato {numero_documento}"

	return (row.get("name") if isinstance(row, dict) else getattr(row, "name", None)) or "Sin nombre"


def _compute_days_to_entry(fecha_tentativa_ingreso):
	if not fecha_tentativa_ingreso:
		return None
	entry_date = getdate(fecha_tentativa_ingreso)
	if not entry_date:
		return None
	return (entry_date - date.today()).days


def _affiliation_type_snapshot(doc, type_key):
	meta = AFFILIATION_TYPES[type_key]
	afiliado = int(doc.get(meta["afiliado"]) or 0)
	return {
		"key": type_key,
		"label": meta["label"],
		"afiliado": afiliado,
		"estado": "completo" if afiliado else "pendiente",
		"pendiente": not bool(afiliado),
		"completo": bool(afiliado),
		"fecha_afiliacion": doc.get(meta["fecha"]),
		"numero_afiliacion": doc.get(meta["numero"]),
		"certificado": doc.get(meta["certificado"]),
	}


def _iter_affiliation_fields(type_key):
	meta = AFFILIATION_TYPES[type_key]
	return [meta["afiliado"], meta["fecha"], meta["numero"], meta["certificado"]]


def _resolve_pdv_names(candidates):
	pdv_ids = sorted({c.get("pdv_destino") for c in candidates if c.get("pdv_destino")})
	if not pdv_ids:
		return {}

	pdvs = frappe.get_all(
		"Punto de Venta",
		filters={"name": ["in", pdv_ids]},
		fields=["name", "nombre_pdv", "codigo"],
	)
	return {pdv.name: (pdv.nombre_pdv or pdv.codigo or pdv.name) for pdv in pdvs}


def _get_candidate_siesa_update(data, type_key):
	meta = CANDIDATE_SIESA_ENTITY_FIELDS.get(type_key)
	if not meta:
		return {}

	fieldname = meta["field"]
	raw_value = None
	if isinstance(data, dict):
		raw_value = data.get(fieldname)
		if raw_value is None:
			raw_value = data.get("siesa_entity")

	if raw_value is None:
		return {}

	value = (str(raw_value or "")).strip() or None
	if value and not frappe.db.exists(meta["doctype"], value):
		frappe.throw(f"Entidad SIESA inválida para {AFFILIATION_TYPES[type_key]['label']}: {value}")

	return {fieldname: value}


def _first_value(*values):
	for value in values:
		if value not in (None, ""):
			return value
	return None


def _is_missing_value(value):
	return value is None or (isinstance(value, str) and not value.strip())


def _ingreso_field_value(contract_doc, datos_doc, candidate_doc, fieldname):
	if contract_doc is not None:
		value = contract_doc.get(fieldname)
		if value not in (None, ""):
			return value

	if datos_doc is not None:
		value = datos_doc.get(fieldname)
		if value not in (None, ""):
			return value

	if candidate_doc is not None:
		if fieldname == "cargo":
			return candidate_doc.get("cargo_postulado")
		if fieldname == "fecha_ingreso":
			return candidate_doc.get("fecha_tentativa_ingreso")
		value = candidate_doc.get(fieldname)
		if value not in (None, ""):
			return value

	return None


def _validate_mandatory_ingreso_gate(contract_doc):
	"""Mandatory data/document gate before formal contract submit (S2.1)."""
	candidate_doc = frappe.get_doc("Candidato", contract_doc.candidato) if contract_doc.candidato else None
	datos_doc = get_or_create_datos_contratacion(contract_doc.candidato, contract=contract_doc.name) if contract_doc.candidato else None

	missing_data = []
	for fieldname, label in MANDATORY_INGRESO_FIELDS:
		value = _ingreso_field_value(contract_doc, datos_doc, candidate_doc, fieldname)
		if _is_missing_value(value):
			missing_data.append(label)

	salary_value = _ingreso_field_value(contract_doc, datos_doc, candidate_doc, "salario")
	try:
		salary = float(salary_value or 0)
	except (TypeError, ValueError):
		salary = 0
	if salary <= 0:
		missing_data.append("salario válido (> 0)")

	if missing_data:
		frappe.throw("No se puede formalizar ingreso: faltan datos mínimos - " + ", ".join(sorted(set(missing_data))))

	if contract_doc.candidato:
		from hubgh.hubgh.document_service import get_candidate_progress

		progress = get_candidate_progress(contract_doc.candidato)
		if not progress.get("is_complete"):
			missing_docs = progress.get("missing") or []
			detail = f": {', '.join(missing_docs)}" if missing_docs else ""
			frappe.throw(f"No se puede formalizar ingreso: documentación requerida incompleta{detail}")


def _normalize_match_text(value):
	if value is None:
		return ""
	raw = str(value).strip().lower().replace("-", " ")
	raw = "".join(ch for ch in unicodedata.normalize("NFKD", raw) if not unicodedata.combining(ch))
	return " ".join(raw.split())


def _expand_lookup_values(values):
	out = []
	for value in values:
		if value in (None, ""):
			continue
		raw = str(value).strip()
		if not raw:
			continue
		out.append(raw)
		if " - " in raw:
			left, right = [p.strip() for p in raw.split(" - ", 1)]
			if left:
				out.append(left)
			if right:
				out.append(right)
	return out


def _catalog_rows(doctype):
	rows = frappe.get_all(
		doctype,
		fields=["name", "code", "description", "enabled"],
	)
	filtered = []
	for row in rows:
		enabled = row.get("enabled")
		if enabled in (None, "", 1, "1", True):
			filtered.append(row)
	return filtered


def _catalog_json_path():
	rel_path = Path("Archivos siesa") / "Arquitectura refactorizacion siesa modulo contratación" / "codigos_siesa_completo.json"
	for parent in Path(__file__).resolve().parents:
		candidate = parent / rel_path
		if candidate.exists():
			return candidate
	return None


def _load_siesa_catalog_json():
	global _SIESA_CATALOG_CACHE
	if _SIESA_CATALOG_CACHE is not None:
		return _SIESA_CATALOG_CACHE

	json_path = _catalog_json_path()
	if not json_path:
		_SIESA_CATALOG_CACHE = {}
		return _SIESA_CATALOG_CACHE

	try:
		with json_path.open("r", encoding="utf-8") as f:
			payload = json.load(f)
			_SIESA_CATALOG_CACHE = payload if isinstance(payload, dict) else {}
	except Exception:
		_SIESA_CATALOG_CACHE = {}
	return _SIESA_CATALOG_CACHE


def _upsert_catalog_row(doctype, code, description):
	code = normalize_code_for_doctype(doctype, code)
	description = str(description).strip()
	if not code or not description:
		return None

	existing = frappe.db.get_value(doctype, {"code": code}, "name")
	if existing:
		doc = frappe.get_doc(doctype, existing)
		if doc.get("description") != description or int(doc.get("enabled") or 0) != 1:
			doc.description = description
			doc.enabled = 1
			doc.save(ignore_permissions=True)
		return existing

	doc = frappe.get_doc({
		"doctype": doctype,
		"code": code,
		"description": description,
		"enabled": 1,
	})
	doc.insert(ignore_permissions=True)
	return doc.name


def _ensure_catalog_seed_from_archivos(doctype):
	if _catalog_rows(doctype):
		return

	json_key = SIESA_JSON_KEY_BY_DOCTYPE.get(doctype)
	if not json_key:
		return

	payload = _load_siesa_catalog_json()
	for row in payload.get(json_key) or []:
		if not isinstance(row, dict):
			continue
		code = row.get("code")
		description = row.get("description")
		if code in (None, "") or description in (None, ""):
			continue
		_upsert_catalog_row(doctype, code, description)


def _ensure_catalog_fallback_test_row(doctype):
	name = frappe.db.get_value(doctype, {"code": "1"}, "name")
	if name:
		doc = frappe.get_doc(doctype, name)
		if int(doc.get("enabled") or 0) != 1 or (doc.get("description") or "").strip().lower() != "test":
			doc.enabled = 1
			doc.description = "test"
			doc.save(ignore_permissions=True)
		return name
	return _upsert_catalog_row(doctype, "1", "test")


def _ensure_catalog_ready(doctype):
	ensure_reference_catalog(doctype)
	_ensure_catalog_seed_from_archivos(doctype)
	if not _catalog_rows(doctype):
		_ensure_catalog_fallback_test_row(doctype)


def _resolve_siesa_catalog_name(doctype, values):
	lookup_values = _expand_lookup_values(values)
	if not lookup_values:
		_ensure_catalog_ready(doctype)
		return frappe.db.get_value(doctype, {"code": "1"}, "name")

	rows = _catalog_rows(doctype)
	if not rows:
		_ensure_catalog_ready(doctype)
		rows = _catalog_rows(doctype)
		if not rows:
			return None

	by_name = {str(r.get("name") or ""): r.get("name") for r in rows}
	by_code = {
		_normalize_match_text(normalize_code_for_doctype(doctype, r.get("code"))): r.get("name")
		for r in rows
		if r.get("code")
	}
	by_desc = {_normalize_match_text(r.get("description")): r.get("name") for r in rows if r.get("description")}

	for value in lookup_values:
		if value in by_name:
			return by_name[value]
		norm = _normalize_match_text(normalize_code_for_doctype(doctype, value) or value)
		if norm in by_code:
			return by_code[norm]
		if norm in by_desc:
			return by_desc[norm]

	_ensure_catalog_ready(doctype)
	return frappe.db.get_value(doctype, {"code": "1"}, "name")


def _guess_tipo_cotizante_from_tipo_contrato(tipo_contrato):
	if not tipo_contrato:
		return None
	norm = _normalize_match_text(tipo_contrato)
	rows = _catalog_rows("Tipo Cotizante Siesa")
	if not rows:
		return None

	if "aprendiz" in norm:
		for row in rows:
			desc = _normalize_match_text(row.get("description"))
			if "aprendiz" in desc:
				return row.get("name")

	for row in rows:
		desc = _normalize_match_text(row.get("description"))
		if any(token in desc for token in ["dependiente", "empleado", "trabajador"]):
			return row.get("name")

	return None


def _collect_contract_context_values(candidate_doc, datos_doc, data):
	pdv = _first_value(
		data.get("pdv_destino") if isinstance(data, dict) else None,
		datos_doc.get("pdv_destino") if datos_doc else None,
		getattr(candidate_doc, "pdv_destino", None),
	)
	cargo = _first_value(
		data.get("cargo") if isinstance(data, dict) else None,
		data.get("cargo_postulado") if isinstance(data, dict) else None,
		datos_doc.get("cargo_postulado") if datos_doc else None,
		getattr(candidate_doc, "cargo_postulado", None),
	)
	tipo_contrato = _first_value(
		data.get("tipo_contrato") if isinstance(data, dict) else None,
		datos_doc.get("tipo_contrato") if datos_doc else None,
	)

	values = {
		"tipo_cotizante_siesa": [
			(data.get("tipo_cotizante_siesa") if isinstance(data, dict) else None),
			(datos_doc.get("tipo_cotizante_siesa") if datos_doc else None),
			(getattr(candidate_doc, "tipo_cotizante_siesa", None)),
		],
		"centro_costos_siesa": [
			(data.get("centro_costos_siesa") if isinstance(data, dict) else None),
			(datos_doc.get("centro_costos_siesa") if datos_doc else None),
			(getattr(candidate_doc, "centro_costos_siesa", None)),
			pdv,
			cargo,
		],
		"unidad_negocio_siesa": [
			(data.get("unidad_negocio_siesa") if isinstance(data, dict) else None),
			(datos_doc.get("unidad_negocio_siesa") if datos_doc else None),
			(getattr(candidate_doc, "unidad_negocio_siesa", None)),
			pdv,
			cargo,
		],
		"centro_trabajo_siesa": [
			(data.get("centro_trabajo_siesa") if isinstance(data, dict) else None),
			(datos_doc.get("centro_trabajo_siesa") if datos_doc else None),
			(getattr(candidate_doc, "centro_trabajo_siesa", None)),
			pdv,
			cargo,
		],
		"grupo_empleados_siesa": [
			(data.get("grupo_empleados_siesa") if isinstance(data, dict) else None),
			(datos_doc.get("grupo_empleados_siesa") if datos_doc else None),
			(getattr(candidate_doc, "grupo_empleados_siesa", None)),
			cargo,
			tipo_contrato,
		],
	}

	if tipo_contrato:
		values["tipo_cotizante_siesa"].append(tipo_contrato)

	infer_group = _infer_grupo_from_selection(cargo, tipo_contrato)
	if infer_group:
		values["grupo_empleados_siesa"].append(infer_group)

	infer_ccosto = _infer_ccosto_from_selection(cargo)
	if infer_ccosto:
		values["centro_costos_siesa"].append(infer_ccosto)

	return values, tipo_contrato


def _infer_grupo_from_selection(cargo, tipo_contrato):
	norm = _normalize_match_text(cargo)
	tipo = _normalize_match_text(tipo_contrato)
	if "aprendiz" in norm or "aprendiz" in tipo or "practicante" in norm or "judicante" in norm:
		return "004"
	admin_tokens = [
		"gerente", "director", "administr", "contab", "nomina", "gestion humana", "mercadeo", "sistemas", "costos",
		"servicio al cliente", "reclutamiento", "bienestar", "audiovisual", "estrategia",
	]
	if any(token in norm for token in admin_tokens):
		return "001"
	return "002"


def _infer_ccosto_from_selection(cargo):
	norm = _normalize_match_text(cargo)
	mapping = [
		("110102", ["gestion humana", "recursos humanos", "nomina", "seleccion", "bienestar"]),
		("110104", ["sistemas", "analista de sistemas", "auxiliar de sistemas"]),
		("110105", ["contab", "costos"]),
		("110106", ["mercadeo", "servicio al cliente", "audiovisual", "estrategia"]),
		("220104", ["mantenimiento", "tecnico mantenimiento", "ingeniero de mantenimiento"]),
		("220103", ["calidad", "sst"]),
		("220101", ["produccion", "despostador", "cocina", "chef", "planta"]),
		("220102", ["operacion", "punto de venta", "cajera", "steward"]),
	]
	for code, tokens in mapping:
		if any(token in norm for token in tokens):
			return code
	return "220102"


def _resolve_required_siesa_fields(candidate_doc, datos_doc, data):
	resolved = {}
	context_values, tipo_contrato = _collect_contract_context_values(candidate_doc, datos_doc, data)

	for fieldname, meta in SIESA_REQUIRED_FIELDS.items():
		resolved[fieldname] = _resolve_siesa_catalog_name(meta["doctype"], context_values.get(fieldname) or [])

	if not resolved.get("tipo_cotizante_siesa"):
		resolved["tipo_cotizante_siesa"] = _guess_tipo_cotizante_from_tipo_contrato(tipo_contrato)
	if not resolved.get("tipo_cotizante_siesa"):
		_ensure_catalog_ready("Tipo Cotizante Siesa")
		resolved["tipo_cotizante_siesa"] = frappe.db.get_value("Tipo Cotizante Siesa", {"code": "1"}, "name")

	return resolved


def _missing_required_siesa_fields(values):
	missing = []
	for fieldname, meta in SIESA_REQUIRED_FIELDS.items():
		if not values.get(fieldname):
			missing.append(meta["label"])
	return missing


def _manual_capture_message(missing_labels):
	if not missing_labels:
		return ""
	return "Falta captura manual de campos SIESA: " + ", ".join(missing_labels)


def get_or_create_affiliation(candidate):
	name = frappe.db.get_value("Afiliacion Seguridad Social", {"candidato": candidate})
	if name:
		return frappe.get_doc("Afiliacion Seguridad Social", name)
	return frappe.get_doc({
		"doctype": "Afiliacion Seguridad Social",
		"candidato": candidate,
	})


def get_or_create_datos_contratacion(candidate, contract=None):
	name = frappe.db.get_value("Datos Contratacion", {"candidato": candidate})
	if name:
		doc = frappe.get_doc("Datos Contratacion", name)
		if contract and not doc.contrato:
			doc.contrato = contract
			doc.save(ignore_permissions=True)
		return doc

	doc = frappe.get_doc({
		"doctype": "Datos Contratacion",
		"candidato": candidate,
		"contrato": contract,
	})
	doc.insert(ignore_permissions=True)
	return doc


def validar_candidato_para_siesa(candidate):
	errors = []
	datos_name = frappe.db.get_value("Datos Contratacion", {"candidato": candidate})
	if not datos_name:
		errors.append("Falta registro de Datos Contratación")
		return {"ok": False, "errors": errors, "datos": None}

	datos = frappe.get_doc("Datos Contratacion", datos_name)
	candidato = frappe.get_doc("Candidato", candidate)

	def _value(*fieldnames):
		for fieldname in fieldnames:
			value = datos.get(fieldname)
			if value not in (None, ""):
				return value
			value = candidato.get(fieldname)
			if value not in (None, ""):
				return value
		return None

	def _missing(value):
		return value is None or (isinstance(value, str) and not value.strip())

	apellidos_raw = (_value("apellidos") or "").strip()
	primer_apellido = (_value("primer_apellido") or "").strip()
	segundo_apellido = (_value("segundo_apellido") or "").strip()

	if not primer_apellido or not segundo_apellido:
		partes_apellidos = [p.strip() for p in apellidos_raw.split() if p and p.strip()]
		if not primer_apellido and len(partes_apellidos) >= 1:
			primer_apellido = partes_apellidos[0]
		if not segundo_apellido and len(partes_apellidos) >= 2:
			segundo_apellido = " ".join(partes_apellidos[1:]).strip()

	if _missing(_value("tipo_documento")):
		errors.append("Falta tipo de documento")
	if _missing(_value("numero_documento")):
		errors.append("Falta número de documento")
	if _missing(_value("nombres")):
		errors.append("Faltan nombres")
	if _missing(primer_apellido):
		errors.append("Falta primer apellido")
	if _missing(_value("fecha_nacimiento")):
		errors.append("Falta fecha de nacimiento")
	if _missing(_value("fecha_expedicion")):
		errors.append("Falta fecha de expedición")
	if _missing(_value("genero")):
		errors.append("Falta género")
	if _missing(_value("estado_civil")):
		errors.append("Falta estado civil")
	if _missing(_value("direccion")):
		errors.append("Falta dirección de residencia")
	if _missing(_value("ciudad_residencia_siesa", "ciudad")):
		errors.append("Falta ciudad de residencia")
	if _missing(_value("email")) and _missing(_value("celular")):
		errors.append("Falta email o celular (al menos uno)")
	if _missing(_value("banco_siesa")):
		errors.append("Falta banco")
	if _missing(_value("tipo_cuenta_bancaria")):
		errors.append("Falta tipo de cuenta bancaria")
	if _missing(_value("numero_cuenta_bancaria")):
		errors.append("Falta número de cuenta bancaria")
	resolved_siesa = _resolve_required_siesa_fields(candidato, datos, {
		"tipo_cotizante_siesa": _value("tipo_cotizante_siesa"),
		"centro_costos_siesa": _value("centro_costos_siesa"),
		"unidad_negocio_siesa": _value("unidad_negocio_siesa"),
		"centro_trabajo_siesa": _value("centro_trabajo_siesa"),
		"grupo_empleados_siesa": _value("grupo_empleados_siesa"),
		"pdv_destino": _value("pdv_destino"),
		"cargo": _value("cargo", "cargo_postulado"),
		"cargo_postulado": _value("cargo_postulado", "cargo"),
		"tipo_contrato": _value("tipo_contrato"),
	})
	missing_siesa = _missing_required_siesa_fields(resolved_siesa)
	if missing_siesa:
		errors.append(_manual_capture_message(missing_siesa))

	salario = _value("salario")
	try:
		salario_valor = float(salario) if salario not in (None, "") else 0
	except (TypeError, ValueError):
		salario_valor = 0
	if salario_valor <= 0:
		errors.append("Falta salario válido (> 0)")

	if _missing(_value("fecha_ingreso")):
		errors.append("Falta fecha de ingreso")

	if datos.estado_datos not in ("Completo", "Enviado a SIESA"):
		# Recalcula estado para evitar bloqueos por estado_datos obsoleto
		datos.save(ignore_permissions=True)
		datos.reload()
	if datos.estado_datos not in ("Completo", "Enviado a SIESA"):
		errors.append("Datos Contratación incompleto")

	# Check for contrato - first try linked, then search by candidate
	contrato_name = datos.contrato
	if not contrato_name:
		# Try to find contrato by candidate
		contrato_name = frappe.db.get_value(
			"Contrato", 
			{"candidato": candidate, "docstatus": 1}, 
			"name",
			order_by="creation desc"
		)
		if contrato_name:
			# Auto-link for future validations
			frappe.db.set_value("Datos Contratacion", datos_name, "contrato", contrato_name, update_modified=False)
	
	if not contrato_name:
		errors.append("No hay contrato asociado")
	else:
		contrato = frappe.get_doc("Contrato", contrato_name)
		if contrato.docstatus != 1:
			errors.append("Contrato no está confirmado")

	a = get_or_create_affiliation(candidate)
	if not int(a.arl_afiliado or 0):
		errors.append("Falta afiliación ARL")
	if not int(a.eps_afiliado or 0):
		errors.append("Falta afiliación EPS")
	if not int(a.afp_afiliado or 0):
		errors.append("Falta afiliación AFP")
	if not int(a.cesantias_afiliado or 0):
		errors.append("Falta afiliación Cesantías")
	if not int(a.caja_afiliado or 0):
		errors.append("Falta afiliación Caja")

	return {"ok": len(errors) == 0, "errors": errors, "datos": datos_name}


@frappe.whitelist()
def affiliation_candidates(search=None, include_completed=0):
	validate_hr_access()
	estados = candidate_status_filter_values(STATE_AFILIACION)
	if int(include_completed or 0):
		estados.extend(candidate_status_filter_values(STATE_LISTO_CONTRATAR))
		estados = list(dict.fromkeys(estados))
	filters = {"estado_proceso": ["in", estados]}
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
			"estado_proceso",
			"fecha_tentativa_ingreso",
			"pdv_destino",
			"cargo_postulado",
		],
		order_by="modified desc",
	)
	pdv_names = _resolve_pdv_names(rows)

	out = []
	for r in rows:
		a = get_or_create_affiliation(r.name)
		datos = frappe.db.get_value("Datos Contratacion", {"candidato": r.name}, ["name", "estado_datos"], as_dict=True)
		dias_restantes_ingreso = _compute_days_to_entry(r.fecha_tentativa_ingreso)
		type_flags = {k: _affiliation_type_snapshot(a, k) for k in AFFILIATION_TYPES}
		prioridad_alta = dias_restantes_ingreso is not None and dias_restantes_ingreso <= 1 and bool(type_flags["arl"]["pendiente"])
		out.append({
			"name": r.name,
			"full_name": _candidate_full_name(r),
			"numero_documento": r.numero_documento,
			"estado_proceso": r.estado_proceso,
			"fecha_tentativa_ingreso": r.fecha_tentativa_ingreso,
			"dias_restantes_ingreso": dias_restantes_ingreso,
			"pdv_destino": r.pdv_destino,
			"pdv_destino_nombre": pdv_names.get(r.pdv_destino) or r.pdv_destino,
			"cargo_postulado": r.cargo_postulado,
			"afiliacion": {
				"name": a.name,
				"estado_general": a.estado_general,
			},
			"afiliaciones_estado": type_flags,
			"prioridad": "alta" if prioridad_alta else "normal",
			"prioridad_alta": prioridad_alta,
			"datos_contratacion": datos,
		})
	return out


@frappe.whitelist()
def affiliation_detail(candidate):
	validate_hr_access()
	a = get_or_create_affiliation(candidate)
	c = frappe.get_doc("Candidato", candidate)
	docs = frappe.get_all(
		"Person Document",
		filters={"person_type": "Candidato", "person": candidate},
		fields=["name", "document_type", "status", "file", "uploaded_on", "uploaded_by"],
		order_by="modified desc",
	)
	return {
		"candidate": {
			"name": c.name,
			"full_name": _candidate_full_name(c),
			"numero_documento": c.numero_documento,
			"estado_proceso": c.estado_proceso,
			"fecha_tentativa_ingreso": c.fecha_tentativa_ingreso,
			"dias_restantes_ingreso": _compute_days_to_entry(c.fecha_tentativa_ingreso),
			"pdv_destino": c.pdv_destino,
			"pdv_destino_nombre": frappe.db.get_value("Punto de Venta", c.pdv_destino, "nombre_pdv") if c.pdv_destino else None,
			"cargo_postulado": c.cargo_postulado,
			"eps_siesa": c.eps_siesa,
			"afp_siesa": c.afp_siesa,
			"cesantias_siesa": c.cesantias_siesa,
		},
		"affiliation": a.as_dict(),
		"affiliations": {k: _affiliation_type_snapshot(a, k) for k in AFFILIATION_TYPES},
		"documents": docs,
	}


@frappe.whitelist()
def save_affiliation(candidate, payload, affiliation_type=None):
	validate_hr_access()
	data = json.loads(payload) if isinstance(payload, str) else (payload or {})
	a = get_or_create_affiliation(candidate)
	valid_columns = set(a.meta.get_valid_columns())

	type_key = (affiliation_type or data.get("affiliation_type") or data.get("type") or "").strip().lower()
	if not type_key or type_key not in AFFILIATION_TYPES:
		frappe.throw("Tipo de afiliación inválido o faltante")

	type_payload = data.get("data") if isinstance(data.get("data"), dict) else data
	if not isinstance(type_payload, dict):
		type_payload = {}

	for fieldname in _iter_affiliation_fields(type_key):
		if fieldname in type_payload and fieldname in valid_columns:
			a.set(fieldname, type_payload.get(fieldname))

	candidate_updates = _get_candidate_siesa_update(data, type_key)
	candidate_updates.update(_get_candidate_siesa_update(type_payload, type_key))
	if candidate_updates:
		candidate_valid_columns = set(frappe.get_meta("Candidato").get_valid_columns())
		frappe.db.set_value(
			"Candidato",
			candidate,
			{k: v for k, v in candidate_updates.items() if k in candidate_valid_columns},
		)

	if a.estado_general != "Completado":
		any_progress = any(int(a.get(AFFILIATION_TYPES[k]["afiliado"]) or 0) for k in AFFILIATION_TYPES)
		a.estado_general = "En Proceso" if any_progress else "Pendiente"
		a.revisado_por = frappe.session.user
		a.fecha_revision = now_datetime()
	a.save(ignore_permissions=True)
	return {"ok": True, "name": a.name, "estado_general": a.estado_general}


@frappe.whitelist()
def mark_affiliation_complete(candidate):
	validate_hr_access()
	a = get_or_create_affiliation(candidate)
	required_flags = ["eps_afiliado", "afp_afiliado", "cesantias_afiliado", "caja_afiliado", "arl_afiliado"]
	missing = [f for f in required_flags if not int(a.get(f) or 0)]
	if int(a.requiere_migracion or 0) and not int(a.migracion_completado or 0):
		missing.append("migracion_completado")
	if missing:
		frappe.throw(f"Afiliaciones incompletas: {', '.join(missing)}")
	a.estado_general = "Completado"
	a.save(ignore_permissions=True)
	frappe.db.set_value("Candidato", candidate, "estado_proceso", STATE_LISTO_CONTRATAR)
	get_or_create_datos_contratacion(candidate)
	return {"ok": True}


@frappe.whitelist()
def affiliation_contract_snapshot(candidate):
	validate_hr_access()
	if not candidate or not frappe.db.exists("Candidato", candidate):
		frappe.throw("Candidato inválido")

	candidato = frappe.get_doc("Candidato", candidate)
	datos_name = frappe.db.get_value("Datos Contratacion", {"candidato": candidate})
	datos = frappe.get_doc("Datos Contratacion", datos_name) if datos_name else None
	afiliacion_name = frappe.db.get_value("Afiliacion Seguridad Social", {"candidato": candidate})
	afiliacion = frappe.get_doc("Afiliacion Seguridad Social", afiliacion_name) if afiliacion_name else None

	primer_apellido = _first_value(
		(datos.get("primer_apellido") if datos else None),
		getattr(candidato, "primer_apellido", None),
	)
	segundo_apellido = _first_value(
		(datos.get("segundo_apellido") if datos else None),
		getattr(candidato, "segundo_apellido", None),
	)

	if (not primer_apellido or not segundo_apellido) and (getattr(candidato, "apellidos", None) or "").strip():
		partes_apellidos = [p.strip() for p in (candidato.apellidos or "").split() if p and p.strip()]
		if not primer_apellido and len(partes_apellidos) >= 1:
			primer_apellido = partes_apellidos[0]
		if not segundo_apellido and len(partes_apellidos) >= 2:
			segundo_apellido = " ".join(partes_apellidos[1:]).strip()

	return {
		"candidate": {
			"name": candidato.name,
			"full_name": _candidate_full_name(candidato),
			"numero_documento": candidato.numero_documento,
		},
		"datos_contratacion": datos.name if datos else None,
		"blocks": {
			"personales": {
				"tipo_documento": _first_value(datos.get("tipo_documento") if datos else None, candidato.tipo_documento),
				"numero_documento": _first_value(datos.get("numero_documento") if datos else None, candidato.numero_documento),
				"nombres": _first_value(datos.get("nombres") if datos else None, candidato.nombres),
				"primer_apellido": primer_apellido,
				"segundo_apellido": segundo_apellido,
				"fecha_nacimiento": _first_value(datos.get("fecha_nacimiento") if datos else None, candidato.fecha_nacimiento),
				"fecha_expedicion": _first_value(datos.get("fecha_expedicion") if datos else None, candidato.fecha_expedicion),
			},
			"contacto": {
				"direccion": _first_value(datos.get("direccion") if datos else None, candidato.direccion),
				"barrio": datos.get("barrio") if datos else None,
				"ciudad": _first_value(datos.get("ciudad_residencia_siesa") if datos else None, datos.get("ciudad") if datos else None, candidato.ciudad),
				"departamento_residencia_siesa": datos.get("departamento_residencia_siesa") if datos else None,
				"pais_residencia_siesa": datos.get("pais_residencia_siesa") if datos else None,
				"celular": _first_value(datos.get("celular") if datos else None, candidato.celular),
				"email": _first_value(datos.get("email") if datos else None, candidato.email),
			},
			"bancarios": {
				"banco_siesa": datos.get("banco_siesa") if datos else None,
				"tipo_cuenta_bancaria": datos.get("tipo_cuenta_bancaria") if datos else None,
				"numero_cuenta_bancaria": datos.get("numero_cuenta_bancaria") if datos else None,
			},
			"laborales": {
				"pdv_destino": _first_value(datos.get("pdv_destino") if datos else None, candidato.pdv_destino),
				"cargo_postulado": _first_value(datos.get("cargo_postulado") if datos else None, candidato.cargo_postulado),
				"salario": datos.get("salario") if datos else None,
				"tipo_contrato": datos.get("tipo_contrato") if datos else None,
				"fecha_tentativa_ingreso": _first_value(datos.get("fecha_tentativa_ingreso") if datos else None, candidato.fecha_tentativa_ingreso),
				"fecha_ingreso": datos.get("fecha_ingreso") if datos else None,
				"fecha_fin_contrato": datos.get("fecha_fin_contrato") if datos else None,
				"horas_trabajadas_mes": datos.get("horas_trabajadas_mes") if datos else None,
			},
			"seguridad_social": {
				"eps_siesa": _first_value(datos.get("eps_siesa") if datos else None, candidato.eps_siesa),
				"afp_siesa": _first_value(datos.get("afp_siesa") if datos else None, candidato.afp_siesa),
				"cesantias_siesa": _first_value(datos.get("cesantias_siesa") if datos else None, candidato.cesantias_siesa),
				"ccf_siesa": _first_value(datos.get("ccf_siesa") if datos else None, candidato.ccf_siesa),
				"arl_codigo_siesa": _first_value(
					datos.get("arl_codigo_siesa") if datos else None,
					afiliacion.get("arl_numero_afiliacion") if afiliacion else None,
				),
			},
		},
	}


@frappe.whitelist()
def contract_candidates(search=None):
	validate_hr_access()
	filters = {
		"estado_proceso": [
			"in",
			candidate_status_filter_values(STATE_LISTO_CONTRATAR, STATE_AFILIACION),
		],
	}
	if search:
		filters["numero_documento"] = ["like", f"%{search}%"]

	rows = frappe.get_all(
		"Candidato",
		filters=filters,
		fields=["name", "nombres", "apellidos", "numero_documento", "pdv_destino", "cargo_postulado", "fecha_tentativa_ingreso"],
		order_by="fecha_tentativa_ingreso asc, modified asc",
	)
	return [{
		"name": r.name,
		"full_name": f"{r.nombres or ''} {r.apellidos or ''}".strip(),
		"numero_documento": r.numero_documento,
		"pdv_destino": r.pdv_destino,
		"cargo_postulado": r.cargo_postulado,
		"fecha_tentativa_ingreso": r.fecha_tentativa_ingreso,
	} for r in rows]


@frappe.whitelist()
def create_contract(candidate, payload):
	validate_hr_access()
	data = json.loads(payload) if isinstance(payload, str) else (payload or {})
	cand = frappe.get_doc("Candidato", candidate)
	datos = get_or_create_datos_contratacion(candidate)

	resolved_siesa = _resolve_required_siesa_fields(cand, datos, data)
	missing_siesa = _missing_required_siesa_fields(resolved_siesa)
	if missing_siesa:
		frappe.throw(_manual_capture_message(missing_siesa))

	contract_pdv = data.get("pdv_destino") or cand.pdv_destino
	contract_cargo = data.get("cargo") or data.get("cargo_postulado") or cand.cargo_postulado
	banco_siesa = data.get("banco_siesa") or getattr(cand, "banco_siesa", None)
	tipo_cuenta_bancaria = data.get("tipo_cuenta_bancaria") or getattr(cand, "tipo_cuenta_bancaria", None)
	numero_cuenta_bancaria = data.get("numero_cuenta_bancaria") or getattr(cand, "numero_cuenta_bancaria", None)

	doc = frappe.get_doc({
		"doctype": "Contrato",
		"candidato": candidate,
		"pdv_destino": contract_pdv,
		"cargo": contract_cargo,
		"numero_contrato": data.get("numero_contrato") or None,
		"tipo_contrato": data.get("tipo_contrato") or "Indefinido",
		"tipo_jornada": data.get("tipo_jornada"),
		"fecha_ingreso": data.get("fecha_ingreso") or cand.fecha_tentativa_ingreso,
		"fecha_fin_contrato": data.get("fecha_fin_contrato"),
		"salario": data.get("salario") or 0,
		"horas_trabajadas_mes": data.get("horas_trabajadas_mes") or 220,
		"banco_siesa": banco_siesa,
		"tipo_cuenta_bancaria": tipo_cuenta_bancaria,
		"cuenta_bancaria": numero_cuenta_bancaria,
		"entidad_eps_siesa": data.get("eps_siesa") or getattr(cand, "eps_siesa", None),
		"entidad_afp_siesa": data.get("afp_siesa") or getattr(cand, "afp_siesa", None),
		"entidad_cesantias_siesa": data.get("cesantias_siesa") or getattr(cand, "cesantias_siesa", None),
		"entidad_ccf_siesa": data.get("ccf_siesa") or getattr(cand, "ccf_siesa", None),
		"centro_costos_siesa": resolved_siesa.get("centro_costos_siesa"),
		"unidad_negocio_siesa": resolved_siesa.get("unidad_negocio_siesa"),
		"grupo_empleados_siesa": resolved_siesa.get("grupo_empleados_siesa"),
		"centro_trabajo_siesa": resolved_siesa.get("centro_trabajo_siesa"),
		"tipo_cotizante_siesa": resolved_siesa.get("tipo_cotizante_siesa"),
	})
	doc.insert(ignore_permissions=True)
	_sync_employee_tipo_jornada_from_contract(doc, cand)
	datos = get_or_create_datos_contratacion(candidate, contract=doc.name)
	updated = False

	datos_direct_fields = [
		"tipo_documento",
		"numero_documento",
		"nombres",
		"primer_apellido",
		"segundo_apellido",
		"fecha_nacimiento",
		"fecha_expedicion",
		"genero",
		"estado_civil",
		"direccion",
		"barrio",
		"ciudad",
		"procedencia_pais",
		"procedencia_departamento",
		"procedencia_ciudad",
		"ciudad_residencia_siesa",
		"departamento_residencia_siesa",
		"pais_residencia_siesa",
		"celular",
		"email",
		"fecha_ingreso",
		"fecha_fin_contrato",
		"salario",
		"horas_trabajadas_mes",
		"banco_siesa",
		"tipo_cuenta_bancaria",
		"numero_cuenta_bancaria",
		"eps_siesa",
		"afp_siesa",
		"cesantias_siesa",
		"ccf_siesa",
	]
	for fieldname in datos_direct_fields:
		if fieldname in data and data.get(fieldname) not in (None, ""):
			datos.set(fieldname, data.get(fieldname))
			updated = True

	if contract_pdv and not datos.get("pdv_destino"):
		datos.pdv_destino = contract_pdv
		updated = True
	if contract_cargo and not datos.get("cargo_postulado"):
		datos.cargo_postulado = contract_cargo
		updated = True
	if doc.fecha_ingreso:
		datos.fecha_ingreso = doc.fecha_ingreso
		updated = True
	if doc.salario is not None:
		datos.salario = doc.salario
		updated = True
	if doc.horas_trabajadas_mes is not None:
		datos.horas_trabajadas_mes = doc.horas_trabajadas_mes
		updated = True
	if doc.tipo_contrato:
		datos.tipo_contrato = doc.tipo_contrato
		updated = True

	siesa_fields = [
		"tipo_cotizante_siesa",
		"centro_costos_siesa",
		"unidad_negocio_siesa",
		"centro_trabajo_siesa",
		"grupo_empleados_siesa",
	]
	for fieldname in siesa_fields:
		if doc.get(fieldname):
			datos.set(fieldname, doc.get(fieldname))
			updated = True

	# Siempre guardar para forzar recalculo de estado_datos y evitar bloqueos por estado obsoleto
	datos.save(ignore_permissions=True)
	return {"ok": True, "name": doc.name}


def _sync_employee_tipo_jornada_from_contract(contract_doc, candidate_doc=None):
	"""Keep Ficha Empleado.tipo_jornada updated from contract payload before submit."""
	tipo_jornada = normalize_tipo_jornada(contract_doc.get("tipo_jornada"))
	if not tipo_jornada:
		return

	employee = contract_doc.get("empleado")
	if not employee and candidate_doc:
		employee = candidate_doc.get("persona")

	if not employee:
		document_number = contract_doc.get("numero_documento")
		if not document_number and candidate_doc:
			document_number = candidate_doc.get("numero_documento")
		if document_number:
			employee = frappe.db.get_value("Ficha Empleado", {"cedula": document_number}, "name")

	if not employee or not frappe.db.exists("Ficha Empleado", employee):
		return

	current_tipo_jornada = normalize_tipo_jornada(
		frappe.db.get_value("Ficha Empleado", employee, "tipo_jornada")
	)
	if current_tipo_jornada == tipo_jornada:
		return

	frappe.db.set_value(
		"Ficha Empleado",
		employee,
		"tipo_jornada",
		tipo_jornada,
		update_modified=False,
	)


@frappe.whitelist()
def submit_contract(contract, signed_file_url=None):
	validate_rrll_authority()
	doc = frappe.get_doc("Contrato", contract)
	_validate_mandatory_ingreso_gate(doc)
	if signed_file_url:
		doc.contrato_firmado = signed_file_url
		doc.save(ignore_permissions=True)
	if doc.docstatus == 0:
		doc.submit()
	get_or_create_datos_contratacion(doc.candidato, contract=doc.name)
	handoff_contract = _build_selection_to_rrll_handoff(doc)
	return {
		"ok": True,
		"name": doc.name,
		"empleado": doc.empleado,
		"handoff_contract": handoff_contract,
	}


def _build_selection_to_rrll_handoff(contract_doc):
	payload = {
		"persona": contract_doc.get("empleado"),
		"candidato": contract_doc.get("candidato"),
		"contrato": contract_doc.get("name"),
		"punto": contract_doc.get("pdv_destino"),
		"fecha_ingreso": contract_doc.get("fecha_ingreso"),
		"documents": [],
	}
	return validate_handoff_contract("selection_to_rrll", payload, lifecycle_state="completed")


@frappe.whitelist()
def siesa_candidates(fecha_desde=None, fecha_hasta=None, only_ready=0):
	validate_hr_access()
	filters = {}
	if fecha_desde and fecha_hasta:
		filters["fecha_tentativa_ingreso"] = ["between", [fecha_desde, fecha_hasta]]
	elif fecha_desde:
		filters["fecha_tentativa_ingreso"] = [">=", fecha_desde]
	elif fecha_hasta:
		filters["fecha_tentativa_ingreso"] = ["<=", fecha_hasta]

	rows = frappe.get_all(
		"Candidato",
		filters=filters,
		fields=["name", "nombres", "apellidos", "numero_documento", "fecha_tentativa_ingreso", "estado_proceso"],
		order_by="fecha_tentativa_ingreso asc, modified asc",
	)
	out = []
	for r in rows:
		validation = validar_candidato_para_siesa(r.name)
		if int(only_ready or 0) and not validation["ok"]:
			continue
		out.append({
			"name": r.name,
			"full_name": f"{r.nombres or ''} {r.apellidos or ''}".strip(),
			"numero_documento": r.numero_documento,
			"fecha_tentativa_ingreso": r.fecha_tentativa_ingreso,
			"estado_proceso": r.estado_proceso,
			"ready_siesa": validation["ok"],
			"errores": validation["errors"],
		})
	return out
