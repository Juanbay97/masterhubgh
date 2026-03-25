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
		"En Proceso",
		"Documentación Incompleta",
		"Documentación Completa",
	},
	STATE_EXAMEN_MEDICO: {
		STATE_EXAMEN_MEDICO,
		"En Examen Médico",
	},
	STATE_AFILIACION: {
		STATE_AFILIACION,
		"En Afiliación",
		"En Proceso de Contratación",
	},
	STATE_LISTO_CONTRATAR: {
		STATE_LISTO_CONTRATAR,
		"Listo para Contratar",
	},
	STATE_CONTRATADO: {
		STATE_CONTRATADO,
	},
	STATE_RECHAZADO: {
		STATE_RECHAZADO,
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
