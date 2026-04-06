import frappe

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


def _build_period_label(period):
	nombre_periodo = (period.get("nombre_periodo") or "").strip()
	if nombre_periodo:
		return nombre_periodo

	month_name = MONTH_NAMES_ES.get(frappe.utils.cint(period.get("mes")))
	year = period.get("ano")
	if month_name and year:
		return f"{month_name} {year}"
	if year:
		return str(year)
	return period.get("name") or "Periodo sin nombre"


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


def _get_batch(batch_name):
	if not batch_name:
		frappe.throw("Debe indicar el lote de importacion.")
	return frappe.get_doc("Payroll Import Batch", batch_name)


@frappe.whitelist()
def get_upload_form_options():
	enforce_payroll_access("import_batches")

	sources = frappe.get_all(
		"Payroll Source Catalog",
		filters={"status": "Active"},
		fields=["name", "nombre_fuente", "tipo_fuente", "periodicidad"],
		order_by="nombre_fuente asc",
	)
	periods = frappe.get_all(
		"Payroll Period Config",
		filters={"status": "Active"},
		fields=["name", "nombre_periodo", "ano", "mes", "fecha_corte_inicio", "fecha_corte_fin"],
		order_by="ano desc, mes desc, fecha_corte_inicio desc",
	)

	return {
		"sources": [_serialize_source(source) for source in sources],
		"periods": [_serialize_period(period) for period in periods],
		"catalog_links": {
			"sources": _catalog_route("Payroll Source Catalog"),
			"periods": _catalog_route("Payroll Period Config"),
		},
		"empty_states": {
			"sources": not bool(sources),
			"periods": not bool(periods),
		},
	}


@frappe.whitelist()
def create_import_batch(file_url, source_type, period):
	enforce_payroll_access("import_batches")

	if not file_url:
		frappe.throw("Debe adjuntar un archivo fuente antes de crear el lote.")

	source_status = frappe.db.get_value("Payroll Source Catalog", source_type, "status")
	if not source_status:
		frappe.throw("La fuente seleccionada no existe.")
	if source_status != "Active":
		frappe.throw("La fuente seleccionada no esta activa. Revise el catalogo de fuentes.")

	period_doc = frappe.get_cached_doc("Payroll Period Config", period)
	if period_doc.status != "Active":
		frappe.throw("El periodo seleccionado no esta activo. Revise el catalogo de periodos.")

	batch = frappe.get_doc({
		"doctype": "Payroll Import Batch",
		"source_file": file_url,
		"source_type": source_type,
		"period": period,
		"nomina_period": (period_doc.nombre_periodo or period_doc.name),
		"status": "Pendiente",
	})
	batch.insert(ignore_permissions=True)

	return {
		"name": batch.name,
		"status": batch.status,
		"nomina_period": batch.nomina_period,
	}


@frappe.whitelist()
def get_import_preview_lines(batch_name, limit_page_length=200):
	enforce_payroll_access("import_batches")
	_get_batch(batch_name)

	return frappe.get_all(
		"Payroll Import Line",
		filters={"batch": batch_name},
		fields=[
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
		],
		order_by="row_number asc",
		limit_page_length=frappe.utils.cint(limit_page_length) or 200,
	)


@frappe.whitelist()
def confirm_import_batch(batch_name):
	enforce_payroll_access("import_batches")
	batch = _get_batch(batch_name)
	batch.db_set("status", "Confirmado", update_modified=True)
	return {"name": batch.name, "status": "Confirmado"}


@frappe.whitelist()
def delete_import_batch(batch_name):
	enforce_payroll_access("import_batches")
	batch = _get_batch(batch_name)

	if batch.status in ("Confirmado", "Aprobado TC"):
		frappe.throw("No se puede eliminar un lote ya confirmado o aprobado.")

	frappe.delete_doc("Payroll Import Batch", batch.name, ignore_permissions=True)
	return {"name": batch.name, "deleted": True}
