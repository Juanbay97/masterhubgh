import frappe

from hubgh.hubgh.contratacion_service import get_or_create_affiliation, get_or_create_datos_contratacion


ADVANCED_HIRING_STATES = ("En Afiliación", "Listo para Contratar", "Contratado")


def _split_last_names(apellidos):
	parts = [p.strip() for p in (apellidos or "").split() if p and p.strip()]
	if not parts:
		return "", ""
	primer = parts[0]
	segundo = " ".join(parts[1:]).strip() if len(parts) > 1 else ""
	return primer, segundo


def _is_missing(value):
	if value is None:
		return True
	if isinstance(value, str):
		return not value.strip()
	return False


def _backfill_candidate_fields():
	if not frappe.db.exists("DocType", "Candidato"):
		return

	rows = frappe.get_all(
		"Candidato",
		fields=[
			"name",
			"apellidos",
			"primer_apellido",
			"segundo_apellido",
			"estado_proceso",
			"es_extranjero",
			"tiene_alergias",
		],
	)

	for row in rows:
		updates = {}

		if _is_missing(row.get("estado_proceso")):
			updates["estado_proceso"] = "En Proceso"

		if row.get("es_extranjero") in (None, ""):
			updates["es_extranjero"] = 0

		if row.get("tiene_alergias") in (None, ""):
			updates["tiene_alergias"] = 0

		apellidos = (row.get("apellidos") or "").strip()
		primer_apellido = (row.get("primer_apellido") or "").strip()
		segundo_apellido = (row.get("segundo_apellido") or "").strip()

		if apellidos and (not primer_apellido or not segundo_apellido):
			primer_legacy, segundo_legacy = _split_last_names(apellidos)
			if not primer_apellido and primer_legacy:
				updates["primer_apellido"] = primer_legacy
			if not segundo_apellido and segundo_legacy:
				updates["segundo_apellido"] = segundo_legacy

		if updates:
			frappe.db.set_value("Candidato", row.name, updates, update_modified=False)


def _ensure_hiring_documents_exist():
	if not frappe.db.exists("DocType", "Candidato"):
		return

	rows = frappe.get_all(
		"Candidato",
		filters={"estado_proceso": ["in", list(ADVANCED_HIRING_STATES)]},
		fields=["name"],
	)

	for row in rows:
		candidate = row.name

		# Inserta solo si no existe; si existe, lo reutiliza sin sobreescribir datos.
		get_or_create_datos_contratacion(candidate)

		affiliation = get_or_create_affiliation(candidate)
		if affiliation.is_new():
			affiliation.insert(ignore_permissions=True)


def execute():
	_backfill_candidate_fields()
	_ensure_hiring_documents_exist()
