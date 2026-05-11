"""Deduplica Banco Siesa: deshabilita / mergea registros legacy.

Origen del problema: `hubgh/hubgh/www/candidato.py` tenía un seeder
hardcoded `_DEFAULT_BANCOS_SIESA` con códigos ACH mal asignados
(ej. "BBVA" en code=1006 cuando 1006 es ITAU; "BANCO DAVIVIENDA" en
code=1013 cuando 1013 es BBVA; "BANCOLOMBIA" en code=0002 que no es
código ACH oficial). Ese seeder corría en cada apertura de /candidato
y creaba duplicados/registros mal etiquetados que conviven con los
oficiales creados por `ensure_banco_reference_catalog`.

Este patch:
  1. Asegura que el catálogo oficial esté en BD.
  2. Para cada banco con `code` no oficial: busca su equivalente
     canonical por description (con aliases) y hace `rename_doc` con
     merge=True para repuntar Link fields. Si no hay equivalente,
     solo lo deshabilita.
"""

import frappe

from hubgh.hubgh.siesa_reference_matrix import (
	BANCO_NAME_ALIASES,
	OFFICIAL_BANCO_CATALOG,
	ensure_banco_reference_catalog,
)


def _normalize(value):
	return " ".join(str(value or "").strip().upper().split())


def execute():
	if not frappe.db.exists("DocType", "Banco Siesa"):
		return

	ensure_banco_reference_catalog()

	# Build sets de canonical codes y un map description-normalized → canonical_code.
	canonical_codes = set()
	desc_to_canonical = {}

	for canonical_name, codigo_ach, codigo_bancolombia in OFFICIAL_BANCO_CATALOG:
		ach = str(codigo_ach or "").strip()
		bancolombia = str(codigo_bancolombia or "").strip()
		target = ach or bancolombia
		if not target:
			continue
		canonical_codes.add(target)
		desc_to_canonical[_normalize(canonical_name)] = target

	for alias, official_name in BANCO_NAME_ALIASES.items():
		official_key = _normalize(official_name)
		canonical_target = desc_to_canonical.get(official_key)
		if canonical_target:
			desc_to_canonical[_normalize(alias)] = canonical_target

	# Recorrer todos los bancos en BD; los que no estén en canonical_codes
	# son legacy y hay que mergearlos al oficial o deshabilitarlos.
	for row in frappe.get_all(
		"Banco Siesa",
		fields=["name", "code", "description", "enabled"],
	):
		current_name = str(row.get("name") or "").strip()
		current_code = str(row.get("code") or "").strip()
		if not current_name or current_name in canonical_codes or current_code in canonical_codes:
			continue

		target_code = desc_to_canonical.get(_normalize(row.get("description")))
		if target_code and target_code != current_name:
			# Repuntar Link fields al canonical y borrar el legacy.
			try:
				frappe.rename_doc(
					"Banco Siesa", current_name, target_code, force=True, merge=True
				)
				continue
			except Exception as exc:
				frappe.logger("hubgh.dedupe_banco").warning(
					"No se pudo mergear Banco Siesa legacy",
					extra={"from": current_name, "to": target_code, "error": str(exc)},
				)

		# Sin equivalente o falló el merge: solo deshabilitar.
		if int(row.get("enabled") or 0) == 1:
			frappe.db.set_value(
				"Banco Siesa", current_name, "enabled", 0, update_modified=False
			)

	frappe.db.commit()
