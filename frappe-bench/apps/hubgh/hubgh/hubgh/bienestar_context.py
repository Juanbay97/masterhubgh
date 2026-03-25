import frappe


BIENESTAR_ALERT_SOURCE_FIELDS = [
	"seguimiento_ingreso",
	"evaluacion_periodo_prueba",
	"levantamiento_punto",
	"gh_novedad",
]

BIENESTAR_COMPROMISO_SOURCE_FIELDS = [
	"alerta",
	"seguimiento_ingreso",
	"evaluacion_periodo_prueba",
	"levantamiento_punto",
	"gh_novedad",
]

ORIGIN_CONTEXT_FIELD = "origen_contexto"
COMPROMISO_ORIGIN_TYPE_FIELD = "tipo_origen_compromiso"
COMPROMISO_ORIGIN_MANUAL = "Manual"

SOURCE_FIELD_LABELS = {
	"alerta": "Alerta",
	"seguimiento_ingreso": "Seguimiento ingreso",
	"evaluacion_periodo_prueba": "Evaluacion periodo prueba",
	"levantamiento_punto": "Levantamiento",
	"gh_novedad": "GH Novedad",
}

COMPROMISO_ORIGIN_TYPE_BY_FIELD = {
	"alerta": "Alerta",
	"seguimiento_ingreso": "Seguimiento ingreso",
	"evaluacion_periodo_prueba": "Evaluacion periodo prueba",
	"levantamiento_punto": "Levantamiento",
	"gh_novedad": "GH Novedad",
}

COMPROMISO_ORIGIN_FIELD_BY_TYPE = {
	COMPROMISO_ORIGIN_MANUAL: None,
	**{label: fieldname for fieldname, label in COMPROMISO_ORIGIN_TYPE_BY_FIELD.items()},
}

ALERTA_SOURCE_BY_TIPO = {
	"Ingreso": "seguimiento_ingreso",
	"Periodo de prueba": "evaluacion_periodo_prueba",
	"Levantamiento de punto": "levantamiento_punto",
}


def _get_value(doc, fieldname):
	if isinstance(doc, dict):
		return doc.get(fieldname)
	return getattr(doc, fieldname, None)


def _set_value(doc, fieldname, value):
	if isinstance(doc, dict):
		doc[fieldname] = value
		return
	setattr(doc, fieldname, value)


def _is_existing_doc(doc):
	is_new = getattr(doc, "is_new", None)
	if callable(is_new):
		return not bool(is_new())
	return bool(getattr(doc, "name", None)) and not bool(getattr(doc, "__islocal", False))


def get_populated_source_refs(doc, allowed_fields):
	return [
		(fieldname, _get_value(doc, fieldname))
		for fieldname in (allowed_fields or [])
		if _get_value(doc, fieldname)
	]


def expected_alert_source_field(tipo_alerta):
	return ALERTA_SOURCE_BY_TIPO.get(str(tipo_alerta or "").strip())



def _normalize_origin_context(fieldname, allowed_fields):
	value = str(fieldname or "").strip()
	if not value:
		return None
	return value if value in (allowed_fields or []) else None


def _normalize_compromiso_origin_type(value):
	label = str(value or "").strip()
	if not label:
		return None
	return label if label in COMPROMISO_ORIGIN_FIELD_BY_TYPE else None


def get_active_source_reference(doc, allowed_fields, *, expected_field=None, strict=False, doctype_label=None):
	selected = get_populated_source_refs(doc, allowed_fields)
	origin_field = _normalize_origin_context(_get_value(doc, ORIGIN_CONTEXT_FIELD), allowed_fields)

	if expected_field:
		if origin_field and origin_field != expected_field:
			expected_label = SOURCE_FIELD_LABELS.get(expected_field, expected_field)
			frappe.throw(
				f"{doctype_label}: para este contexto debes usar solo la referencia {expected_label}."
			)
		origin_field = expected_field

	if not origin_field:
		if len(selected) == 1:
			origin_field = selected[0][0]
		elif selected and not strict:
			origin_field = selected[0][0]

	if strict and len(selected) > 1 and not origin_field:
		frappe.throw(
			f"{doctype_label}: define el contexto de origen activo antes de guardar."
		)

	if origin_field and not _get_value(doc, origin_field) and strict:
		expected_label = SOURCE_FIELD_LABELS.get(origin_field, origin_field)
		frappe.throw(
			f"{doctype_label}: completa la referencia {expected_label} para el contexto activo."
		)

	return origin_field, _get_value(doc, origin_field) if origin_field else None


def validate_single_source_reference(doc, allowed_fields, *, doctype_label, expected_field=None):
	fieldname, ref_name = get_active_source_reference(
		doc,
		allowed_fields,
		expected_field=expected_field,
		strict=True,
		doctype_label=doctype_label,
	)

	if hasattr(doc, ORIGIN_CONTEXT_FIELD):
		setattr(doc, ORIGIN_CONTEXT_FIELD, fieldname or "")

	return fieldname, ref_name


def get_compromiso_origin_type(doc):
	origin_type = _normalize_compromiso_origin_type(_get_value(doc, COMPROMISO_ORIGIN_TYPE_FIELD))
	if origin_type:
		return origin_type

	origin_field = _normalize_origin_context(_get_value(doc, ORIGIN_CONTEXT_FIELD), BIENESTAR_COMPROMISO_SOURCE_FIELDS)
	if origin_field:
		return COMPROMISO_ORIGIN_TYPE_BY_FIELD.get(origin_field)

	selected = get_populated_source_refs(doc, BIENESTAR_COMPROMISO_SOURCE_FIELDS)
	if len(selected) == 1:
		return COMPROMISO_ORIGIN_TYPE_BY_FIELD.get(selected[0][0])
	if not selected:
		return COMPROMISO_ORIGIN_MANUAL
	return None


def validate_compromiso_source_reference(doc, *, doctype_label):
	selected = get_populated_source_refs(doc, BIENESTAR_COMPROMISO_SOURCE_FIELDS)
	selected_map = dict(selected)
	origin_type = get_compromiso_origin_type(doc) or COMPROMISO_ORIGIN_MANUAL
	expected_field = COMPROMISO_ORIGIN_FIELD_BY_TYPE.get(origin_type)
	is_legacy_trace = _is_existing_doc(doc) and len(selected) > 1

	if origin_type == COMPROMISO_ORIGIN_MANUAL:
		if selected:
			frappe.throw(f"{doctype_label}: el modo Manual no permite referencias de origen.")
		_set_value(doc, ORIGIN_CONTEXT_FIELD, "")
		_set_value(doc, COMPROMISO_ORIGIN_TYPE_FIELD, COMPROMISO_ORIGIN_MANUAL)
		return None, None

	if not expected_field:
		frappe.throw(f"{doctype_label}: selecciona un tipo de origen valido o usa Manual.")

	if expected_field not in selected_map:
		expected_label = SOURCE_FIELD_LABELS.get(expected_field, expected_field)
		frappe.throw(
			f"{doctype_label}: completa la referencia {expected_label} para el origen seleccionado."
		)

	if len(selected) != 1 and not is_legacy_trace:
		frappe.throw(f"{doctype_label}: el modo Con origen admite exactamente una referencia activa.")

	_set_value(doc, ORIGIN_CONTEXT_FIELD, expected_field)
	_set_value(doc, COMPROMISO_ORIGIN_TYPE_FIELD, origin_type)
	return expected_field, selected_map.get(expected_field)


def build_origin_context_payload(doc, allowed_fields):
	fieldname, ref_name = get_active_source_reference(
		doc,
		allowed_fields,
		strict=False,
		doctype_label="Contexto Bienestar",
	)
	label = SOURCE_FIELD_LABELS.get(fieldname, "Sin origen contextual") if fieldname else "Sin origen contextual"
	return {
		"origen_contexto_field": fieldname,
		"origen_contexto_label": label,
		"origen_contexto_ref": ref_name,
		"origen_contexto_display": f"{label}: {ref_name}" if fieldname and ref_name else label,
	}
