import frappe
from frappe import _
from frappe.utils import now_datetime

from hubgh.hubgh.payroll_permissions import enforce_payroll_access


@frappe.whitelist()
def get_pending_lines(filters=None):
	"""Get pending lines for TC review."""
	enforce_payroll_access("tc_tray")
	from hubgh.hubgh.payroll_tc_tray import PayrollTCTrayService

	service = PayrollTCTrayService()

	filter_dict = {}
	if filters:
		if isinstance(filters, str):
			import json
			filter_dict = json.loads(filters)
		else:
			filter_dict = filters

	return service.query_pending_lines(
		employee_filter=filter_dict.get("employee"),
		batch_filter=filter_dict.get("batch"),
		period_filter=filter_dict.get("period"),
		status_filter=filter_dict.get("status"),
		limit=filter_dict.get("limit", 500),
	)


@frappe.whitelist()
def get_consolidated_view(filters=None, batch=None, period=None, status=None, employee=None, limit=500):
	"""Get consolidated view by employee."""
	enforce_payroll_access("tc_tray")
	from hubgh.hubgh.payroll_tc_tray import PayrollTCTrayService

	filter_dict = {}
	if filters:
		if isinstance(filters, str):
			filter_dict = frappe.parse_json(filters) or {}
		else:
			filter_dict = filters

	batch = filter_dict.get("batch") or batch
	period = filter_dict.get("period") or period
	status = filter_dict.get("status") or status
	employee = filter_dict.get("employee") or employee
	limit = filter_dict.get("limit") or limit

	service = PayrollTCTrayService()
	result = service.query_pending_lines(
		employee_filter=employee,
		batch_filter=batch,
		period_filter=period,
		status_filter=status,
		limit=limit,
	)
	employees = result.get("consolidated") or []
	lines = result.get("lines") or []
	return {
		"status": result.get("status", "success"),
		"contract_version": "nomina-operativa-v2",
		"total_employees": len(employees),
		"total_lines": len(lines),
		"pending_count": sum(1 for line in lines if (line.get("tc_status") or "Pendiente") == "Pendiente"),
		"ready_count": sum(1 for employee_data in employees if employee_data.get("overall_tc_status") == "Aprobado"),
		"employees": employees,
		"batch_summary": result.get("batch_summary") or [],
		"empty_state": _build_empty_state(batch=batch, period=period, status=status, employee=employee),
		"traceability": {
			"stage": "tc_review",
			"source": "Payroll Import Line",
			"generated_at": now_datetime().isoformat(),
			"filters": {
				"batch": batch,
				"period": period,
				"status": status,
				"employee": employee,
			},
		},
	}


def _build_empty_state(batch=None, period=None, status=None, employee=None):
	if batch or period or status or employee:
		return {
			"title": _("No hay novedades de la etapa TC con los filtros actuales"),
			"message": _("Probá limpiando filtros o revisá otro lote/período procesado."),
			"next_step": _("Si todavía no cargaste novedades, empezá por Cargar archivo."),
		}

	return {
		"title": _("Todavía no hay novedades para la etapa TC (revisión inicial)"),
		"message": _("La bandeja se llena cuando existe al menos un lote procesado con líneas válidas o revisadas."),
		"next_step": _("Próximo paso: cargá un archivo de novedades y luego revisá el historial de cargas."),
	}


@frappe.whitelist()
def approve_lines(line_names, comment=None):
	"""Bulk approve lines."""
	enforce_payroll_access("tc_tray")
	from hubgh.hubgh.payroll_tc_tray import PayrollTCTrayService

	if isinstance(line_names, str):
		import json
		line_names = json.loads(line_names)

	service = PayrollTCTrayService()
	return service.bulk_approve(line_names, comment)


@frappe.whitelist()
def reject_lines(line_names, comment=None):
	"""Bulk reject lines."""
	enforce_payroll_access("tc_tray")
	from hubgh.hubgh.payroll_tc_tray import PayrollTCTrayService

	if isinstance(line_names, str):
		import json
		line_names = json.loads(line_names)

	service = PayrollTCTrayService()
	return service.bulk_reject(line_names, comment)


@frappe.whitelist()
def get_batches_for_review():
	"""Get all batches with pending TC review."""
	enforce_payroll_access("tc_tray")
	batches = frappe.get_all(
		"Payroll Import Batch",
		filters={"status": ["in", ["Completado", "Completado con errores"]]},
		fields=["name", "source_type", "period", "uploaded_on", "total_rows", "valid_rows"],
		order_by="uploaded_on desc",
	)
	return batches


@frappe.whitelist()
def get_batch_lines(batch_name):
	"""Get all lines for a specific batch."""
	enforce_payroll_access("tc_tray")
	lines = frappe.get_all(
		"Payroll Import Line",
		filters={"batch": batch_name},
		fields=["name", "employee_id", "employee_name", "novedad_type", 
				"quantity", "status", "tc_status", "rule_applied", "rule_notes"],
		order_by="employee_name, row_number",
	)
	return lines
