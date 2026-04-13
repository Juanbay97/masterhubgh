import json

import frappe

from hubgh.hubgh.payroll_import_engine import process_import_run
from hubgh.hubgh.payroll_permissions import enforce_payroll_access


MONTH_NAMES_ES = {
	1: "Enero",
	2: "Febrero",
	3: "Marzo",
	4: "Abril",
	5: "Mayo",
	6: "Junio",
	7: "Julio",
	8: "Agosto",
	9: "Septiembre",
	10: "Octubre",
	11: "Noviembre",
	12: "Diciembre",
}


def _catalog_route(doctype):
	return f"/app/{frappe.scrub(doctype)}"


def _active_status_values():
	return ["Active", "Activo", "Activa"]


def _build_period_label(period):
	nombre_periodo = (period.get("nombre_periodo") or getattr(period, "nombre_periodo", "") or "").strip()
	if nombre_periodo:
		return nombre_periodo
	month_name = MONTH_NAMES_ES.get(frappe.utils.cint(period.get("mes") if isinstance(period, dict) else getattr(period, "mes", None)))
	year = period.get("ano") if isinstance(period, dict) else getattr(period, "ano", None)
	if month_name and year:
		return f"{month_name} {year}"
	if year:
		return str(year)
	return period.get("name") if isinstance(period, dict) else getattr(period, "name", "Periodo sin nombre")


def _serialize_source(source):
	return {
		"value": source.get("name"),
		"label": source.get("nombre_fuente") or source.get("name"),
		"tipo_fuente": source.get("tipo_fuente"),
		"periodicidad": source.get("periodicidad"),
	}


def _serialize_period(period):
	return {
		"value": period.get("name"),
		"label": _build_period_label(period),
		"nombre_periodo": period.get("nombre_periodo"),
		"ano": period.get("ano"),
		"mes": period.get("mes"),
		"fecha_corte_inicio": period.get("fecha_corte_inicio"),
		"fecha_corte_fin": period.get("fecha_corte_fin"),
	}


def _ensure_list(value):
	if isinstance(value, str):
		parsed = frappe.parse_json(value)
		if isinstance(parsed, list):
			return parsed
		return [parsed]
	return value or []


def _get_batch(batch_name):
	if not batch_name:
		frappe.throw("Debe indicar el lote de importacion.")
	return frappe.get_doc("Payroll Import Batch", batch_name)


def _get_run_batches(run_id):
	if not run_id:
		frappe.throw("Debe indicar el run de importación.")
	batches = frappe.get_all(
		"Payroll Import Batch",
		filters={"run_id": run_id},
		fields=["name", "status", "nomina_period", "run_label", "run_source_count", "source_file", "source_type", "period"],
		order_by="creation asc",
	)
	if not batches:
		frappe.throw("No se encontraron lotes para el run indicado.")
	return batches


def _validate_source_and_period(source_type, period):
	source_status = frappe.db.get_value("Payroll Source Catalog", source_type, "status")
	if not source_status:
		frappe.throw("La fuente seleccionada no existe.")
	if source_status not in _active_status_values():
		frappe.throw("La fuente seleccionada no esta activa. Revise el catalogo de fuentes.")

	period_doc = frappe.get_cached_doc("Payroll Period Config", period)
	if getattr(period_doc, "status", None) not in _active_status_values():
		frappe.throw("El periodo seleccionado no esta activo. Revise el catalogo de periodos.")
	return period_doc


def _make_run_id(period_doc):
	base = f"{period_doc.name}-{frappe.generate_hash(length=8)}"
	return f"RUN-{base.upper()}"


def _serialize_run_batches(batches):
	return [
		{
			"name": batch.get("name"),
			"status": batch.get("status"),
			"source_file": batch.get("source_file"),
			"source_type": batch.get("source_type"),
			"period": batch.get("period"),
		}
		for batch in batches
	]


@frappe.whitelist()
def get_upload_form_options():
	enforce_payroll_access("import_batches")
	sources = frappe.get_all(
		"Payroll Source Catalog",
		filters={"status": ["in", _active_status_values()]},
		fields=["name", "nombre_fuente", "tipo_fuente", "periodicidad"],
		order_by="nombre_fuente asc",
	)
	periods = frappe.get_all(
		"Payroll Period Config",
		filters={"status": ["in", _active_status_values()]},
		fields=["name", "nombre_periodo", "ano", "mes", "fecha_corte_inicio", "fecha_corte_fin"],
		order_by="ano desc, mes desc, fecha_corte_inicio desc",
	)
	return {
		"sources": [_serialize_source(source) for source in sources],
		"periods": [_serialize_period(period) for period in periods],
		"catalog_links": {"sources": _catalog_route("Payroll Source Catalog"), "periods": _catalog_route("Payroll Period Config")},
		"empty_states": {"sources": not bool(sources), "periods": not bool(periods)},
	}


@frappe.whitelist()
def create_import_run(file_urls_json, source_type, period, run_label=None):
	enforce_payroll_access("import_batches")
	file_urls = [file_url for file_url in _ensure_list(file_urls_json) if file_url]
	if not file_urls:
		frappe.throw("Debe adjuntar al menos un archivo fuente antes de crear el run.")

	period_doc = _validate_source_and_period(source_type, period)
	run_id = _make_run_id(period_doc)
	resolved_run_label = (run_label or "").strip() or f"{_build_period_label(period_doc.as_dict())} · {len(file_urls)} archivo(s)"
	batches = []
	for file_url in file_urls:
		batch = frappe.get_doc(
			{
				"doctype": "Payroll Import Batch",
				"run_id": run_id,
				"run_label": resolved_run_label,
				"run_source_count": len(file_urls),
				"source_file": file_url,
				"source_type": source_type,
				"period": period,
				"nomina_period": (period_doc.nombre_periodo or period_doc.name),
				"status": "Pendiente",
			}
		)
		batch.insert(ignore_permissions=True)
		batches.append(batch)

	return {
		"run_id": run_id,
		"run_label": resolved_run_label,
		"source_count": len(file_urls),
		"batches": [{"name": batch.name, "status": batch.status, "source_file": batch.source_file} for batch in batches],
	}


@frappe.whitelist()
def create_import_batch(file_url, source_type, period):
	run = create_import_run(json.dumps([file_url]), source_type, period)
	batch = run["batches"][0]
	return {"name": batch["name"], "status": batch["status"], "nomina_period": run["run_label"], "run_id": run["run_id"]}


@frappe.whitelist()
def get_import_run_preview(run_id):
	enforce_payroll_access("import_batches")
	preview = process_import_run(run_id)
	preview["batches"] = _serialize_run_batches(_get_run_batches(run_id))
	return preview


@frappe.whitelist()
def get_import_preview_lines(batch_name=None, run_id=None, limit_page_length=200):
	enforce_payroll_access("import_batches")
	filters = {}
	if run_id:
		filters["run_id"] = run_id
	elif batch_name:
		filters["batch"] = _get_batch(batch_name).name
	else:
		frappe.throw("Debe indicar un lote o run para consultar la vista previa.")

	return frappe.get_all(
		"Payroll Import Line",
		filters=filters,
		fields=[
			"run_id",
			"batch",
			"row_number",
			"status",
			"employee_id",
			"employee_name",
			"matched_employee",
			"matched_employee_doctype",
			"novedad_type",
			"quantity",
			"novedad_date",
			"validation_errors",
			"source_file",
			"source_type_code",
			"source_row_number",
			"source_concept_code",
			"parser_version",
		],
		order_by="batch asc, row_number asc",
		limit_page_length=frappe.utils.cint(limit_page_length) or 200,
	)


@frappe.whitelist()
def confirm_import_run(run_id):
	enforce_payroll_access("import_batches")
	batches = _get_run_batches(run_id)
	blocked = [batch["name"] for batch in batches if batch.get("status") in ("Fallido", "Fuente no soportada")]
	if blocked:
		frappe.throw("No se puede confirmar un run con lotes fallidos o fuentes no soportadas.")
	for batch in batches:
		frappe.db.set_value("Payroll Import Batch", batch["name"], "status", "Confirmado", update_modified=True)
	return {"run_id": run_id, "status": "Confirmado", "batch_count": len(batches)}


@frappe.whitelist()
def confirm_import_batch(batch_name):
	enforce_payroll_access("import_batches")
	batch = _get_batch(batch_name)
	if batch.run_id:
		return confirm_import_run(batch.run_id)
	batch.db_set("status", "Confirmado", update_modified=True)
	return {"name": batch.name, "status": "Confirmado"}


@frappe.whitelist()
def delete_import_run(run_id):
	enforce_payroll_access("import_batches")
	batches = _get_run_batches(run_id)
	for batch in batches:
		if batch.get("status") in ("Confirmado", "Aprobado TC"):
			frappe.throw("No se puede eliminar un run con lotes ya confirmados o aprobados.")
	for batch in batches:
		frappe.delete_doc("Payroll Import Batch", batch["name"], ignore_permissions=True)
	return {"run_id": run_id, "deleted": True, "batch_count": len(batches)}


@frappe.whitelist()
def delete_import_batch(batch_name):
	enforce_payroll_access("import_batches")
	batch = _get_batch(batch_name)
	if batch.run_id:
		return delete_import_run(batch.run_id)
	if batch.status in ("Confirmado", "Aprobado TC"):
		frappe.throw("No se puede eliminar un lote ya confirmado o aprobado.")
	frappe.delete_doc("Payroll Import Batch", batch.name, ignore_permissions=True)
	return {"name": batch.name, "deleted": True}
