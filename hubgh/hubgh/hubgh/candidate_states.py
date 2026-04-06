import unicodedata


STATE_DOCUMENTACION = "En documentación"
STATE_EXAMEN_MEDICO = "En examen médico"
STATE_AFILIACION = "En afiliación"
STATE_LISTO_CONTRATAR = "Listo para contratar"
STATE_CONTRATADO = "Contratado"
STATE_RECHAZADO = "Rechazado"


_STATE_ALIASES = {
	STATE_DOCUMENTACION: {
		STATE_DOCUMENTACION,
		"En documentación",
		"En Proceso",
		"Documentacion",
		"Documentación Incompleta",
		"Documentación Completa",
	},
	STATE_EXAMEN_MEDICO: {
		STATE_EXAMEN_MEDICO,
		"En examen médico",
		"En Examen Médico",
		"Examen Medico",
	},
	STATE_AFILIACION: {
		STATE_AFILIACION,
		"En afiliación",
		"En Afiliación",
		"Afiliacion",
		"En Proceso de Contratación",
	},
	STATE_LISTO_CONTRATAR: {
		STATE_LISTO_CONTRATAR,
		"Listo para contratar",
		"Listo para Contratar",
	},
	STATE_CONTRATADO: {
		STATE_CONTRATADO,
	},
	STATE_RECHAZADO: {
		STATE_RECHAZADO,
	},
}


_STATE_STORAGE_PRIORITY = {
	STATE_DOCUMENTACION: (
		"En Proceso",
		"Documentación Incompleta",
		"Documentacion",
	),
	STATE_EXAMEN_MEDICO: (
		"En Examen Médico",
		"Examen Medico",
	),
	STATE_AFILIACION: (
		"En Afiliación",
		"Afiliacion",
		"En Proceso de Contratación",
	),
	STATE_LISTO_CONTRATAR: (
		"Listo para Contratar",
	),
}


_STATE_STORAGE_EXCLUSIONS = {
	STATE_DOCUMENTACION: {
		"Documentación Completa",
	},
}


def _normalize(value):
	text = str(value or "").strip().lower()
	if not text:
		return ""
	return "".join(ch for ch in unicodedata.normalize("NFKD", text) if not unicodedata.combining(ch))


_ALIAS_LOOKUP = {}
for canonical, aliases in _STATE_ALIASES.items():
	for alias in aliases:
		_ALIAS_LOOKUP[_normalize(alias)] = canonical


def normalize_candidate_status(value, default=STATE_DOCUMENTACION):
	return _ALIAS_LOOKUP.get(_normalize(value), default)


def parse_candidate_status_options(options):
	if not options:
		return []
	return [line.strip() for line in str(options).splitlines() if line.strip()]


def get_candidate_status_options(meta=None, doctype="Candidato", fieldname="estado_proceso"):
	field = None
	if meta and hasattr(meta, "get_field"):
		field = meta.get_field(fieldname)
	if not field:
		try:
			import frappe

			field = frappe.get_meta(doctype).get_field(fieldname)
		except Exception:
			field = None
	return parse_candidate_status_options(getattr(field, "options", ""))


def resolve_candidate_status_for_storage(value, *, options=None, default=STATE_DOCUMENTACION):
	raw_value = str(value or "").strip()
	desired = normalize_candidate_status(raw_value, default=default)
	allowed_options = list(options or [])
	if not allowed_options:
		return desired
	if raw_value and raw_value in allowed_options:
		return raw_value
	if desired in allowed_options:
		return desired
	for fallback in _STATE_STORAGE_PRIORITY.get(desired, ()):
		if fallback in allowed_options:
			return fallback
	excluded = {_normalize(option) for option in _STATE_STORAGE_EXCLUSIONS.get(desired, set())}
	for option in allowed_options:
		if _normalize(option) in excluded:
			continue
		if normalize_candidate_status(option, default="") == desired:
			return option
	return desired


def candidate_status_filter_values(*statuses):
	values = []
	for status in statuses:
		canonical = normalize_candidate_status(status, default=str(status or ""))
		aliases = _STATE_ALIASES.get(canonical, {status})
		for alias in aliases:
			if alias not in values:
				values.append(alias)
	return values


def is_candidate_status(value, *statuses):
	current = normalize_candidate_status(value, default="")
	if not current:
		return False
	for status in statuses:
		if current == normalize_candidate_status(status, default=""):
			return True
	return False
