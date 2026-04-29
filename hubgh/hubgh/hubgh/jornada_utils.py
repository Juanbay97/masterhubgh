import unicodedata


TIPO_JORNADA_FULL_TIME = "Tiempo Completo"
TIPO_JORNADA_PART_TIME = "Tiempo Parcial"


def _normalize_match_text(value: str | None) -> str:
	text = unicodedata.normalize("NFKD", str(value or ""))
	text = "".join(char for char in text if not unicodedata.combining(char))
	return " ".join(text.replace("_", " ").replace("-", " ").lower().split())


def normalize_tipo_jornada(value: str | None) -> str:
	text = _normalize_match_text(value)
	if not text:
		return ""

	full_time_values = {
		"tc",
		"tiempo completo",
		"tiempo completa",
		"jornada completa",
		"jornada completo",
		"completo",
		"full time",
		"full-time",
		"fulltime",
	}
	part_time_values = {
		"tp",
		"tiempo parcial",
		"jornada parcial",
		"parcial",
		"part time",
		"part-time",
		"parttime",
	}

	if text in full_time_values:
		return TIPO_JORNADA_FULL_TIME
	if text in part_time_values:
		return TIPO_JORNADA_PART_TIME
	return ""
