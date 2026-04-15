from __future__ import annotations

import frappe

from hubgh.www.candidato import get_procedencia_siesa_catalog


def _row_value(row, key, default=None):
	if isinstance(row, dict):
		return row.get(key, default)
	return getattr(row, key, default)


def get_punto_name_map(point_ids):
	ids = sorted({str(point_id or "").strip() for point_id in (point_ids or []) if str(point_id or "").strip()})
	if not ids:
		return {}

	try:
		rows = frappe.get_all(
			"Punto de Venta",
			filters={"name": ["in", ids]},
			fields=["name", "nombre_pdv"],
			ignore_permissions=True,
		)
	except Exception:
		return {point_id: point_id for point_id in ids}

	name_map = {
		str(_row_value(row, "name") or "").strip(): str(_row_value(row, "nombre_pdv") or _row_value(row, "name") or "").strip()
		for row in rows
	}
	for point_id in ids:
		name_map.setdefault(point_id, point_id)
	return name_map


def get_punto_display_name(point_id):
	point_id = str(point_id or "").strip()
	if not point_id:
		return ""
	return get_punto_name_map([point_id]).get(point_id) or point_id


def resolve_catalog_display_name(doctype, value):
	value = str(value or "").strip()
	if not value:
		return ""

	try:
		rows = frappe.get_all(
			doctype,
			filters={"name": value},
			fields=["name", "description", "code"],
			ignore_permissions=True,
			limit_page_length=1,
		)
		if not rows:
			rows = frappe.get_all(
				doctype,
				filters={"code": value},
				fields=["name", "description", "code"],
				ignore_permissions=True,
				limit_page_length=1,
			)
	except Exception:
		return value

	if not rows:
		return value

	row = rows[0]
	return str(_row_value(row, "description") or _row_value(row, "name") or _row_value(row, "code") or value).strip() or value


def resolve_siesa_bank_name(bank_value):
	return resolve_catalog_display_name("Banco Siesa", bank_value)


def resolve_candidate_location_labels(*, pais=None, departamento=None, ciudad=None):
	try:
		catalog = get_procedencia_siesa_catalog() or {}
	except Exception:
		catalog = {}

	pais_code = str(pais or "").strip()
	departamento_code = str(departamento or "").strip()
	ciudad_code = str(ciudad or "").strip()

	paises = catalog.get("paises") or []
	departamentos = catalog.get("departamentos") or []
	ciudades = catalog.get("ciudades") or []

	pais_name = next((str(row.get("name") or "").strip() for row in paises if str(row.get("code") or "").strip() == pais_code), "")

	departamento_name = next(
		(
			str(row.get("name") or "").strip()
			for row in departamentos
			if str(row.get("code") or "").strip() == departamento_code
			and (not pais_code or str(row.get("pais_codigo") or "").strip() in {"", pais_code})
		),
		"",
	)
	if not departamento_name:
		departamento_name = next(
			(str(row.get("name") or "").strip() for row in departamentos if str(row.get("code") or "").strip() == departamento_code),
			"",
		)

	ciudad_name = next(
		(
			str(row.get("name") or "").strip()
			for row in ciudades
			if str(row.get("code") or "").strip() == ciudad_code
			and (not pais_code or str(row.get("pais_codigo") or "").strip() in {"", pais_code})
			and (not departamento_code or str(row.get("departamento_codigo") or "").strip() in {"", departamento_code})
		),
		"",
	)
	if not ciudad_name:
		ciudad_name = next((str(row.get("name") or "").strip() for row in ciudades if str(row.get("code") or "").strip() == ciudad_code), "")

	return {
		"pais": pais_name or pais_code,
		"departamento": departamento_name or departamento_code,
		"ciudad": ciudad_name or ciudad_code,
	}
