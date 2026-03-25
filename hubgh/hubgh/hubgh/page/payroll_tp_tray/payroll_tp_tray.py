"""
Payroll TP Tray Page - Backend handlers for the TP operational-stage interface.

Provides data endpoints and processing logic for the TP approval interface,
including executive summaries and batch operations.
"""

import frappe
from frappe import _
from frappe.utils import now_datetime

from hubgh.hubgh.payroll_permissions import enforce_payroll_access
from hubgh.hubgh.payroll_tp_tray import get_tp_tray_service


def _get_available_period_labels():
	periods = frappe.db.sql("""
		SELECT DISTINCT pb.nomina_period
		FROM `tabPayroll Import Batch` pb
		INNER JOIN `tabPayroll Import Line` pl ON pl.batch = pb.name
		WHERE pl.tc_status = 'Aprobado'
		AND pb.nomina_period IS NOT NULL
		ORDER BY pb.nomina_period DESC
	""", as_dict=True)
	return [p.nomina_period for p in periods if p.nomina_period]


@frappe.whitelist()
def get_page_data():
	"""
	Get initial data for TP Tray page load.
	
	Returns periods, summary statistics, and initial employee consolidation.
	"""
	
	try:
		enforce_payroll_access("tp_tray")
		service = get_tp_tray_service()
		
		# Get available periods
		available_periods = _get_available_period_labels()
		
		# Get data for most recent period if available
		consolidation_data = {"employee_consolidation": [], "period_summary": {}, "executive_summary": {}}
		if available_periods:
			recent_period = available_periods[0]  # Already sorted DESC
			consolidation_result = service.consolidate_by_period(
				period_filter=recent_period,
				limit=100,
				jornada_filter="Todas",
			)
			if consolidation_result.get("status") == "success":
				consolidation_data = consolidation_result
		
		return {
			"status": "success",
			"contract_version": "nomina-operativa-v2",
			"available_periods": available_periods,
			"current_period": available_periods[0] if available_periods else None,
			"consolidation": consolidation_data,
			"page_loaded": now_datetime().strftime("%Y-%m-%d %H:%M:%S"),
			"traceability": {
				"stage": "tp_page_load",
				"source": "Payroll Import Batch/Line",
				"generated_at": now_datetime().isoformat(),
			},
		}
		
	except Exception as e:
		frappe.log_error(f"Error loading TP Tray page data: {str(e)}")
		return {
			"status": "error",
			"message": str(e),
			"available_periods": [],
			"consolidation": {"employee_consolidation": [], "period_summary": {}, "executive_summary": {}}
		}


@frappe.whitelist()
def refresh_period_data(period=None, batch=None, jornada_type=None):
	"""
	Refresh consolidation data for a specific period or batch.
	
	Args:
		period: Period filter (YYYY-MM format)
		batch: Specific batch filter
	"""
	
	try:
		enforce_payroll_access("tp_tray")
		service = get_tp_tray_service()
		result = service.consolidate_by_period(
			period_filter=period,
			batch_filter=batch,
			limit=500,
			jornada_filter=jornada_type,
		)
		if isinstance(result, dict):
			result.setdefault("contract_version", "nomina-operativa-v2")
			result["traceability"] = {
				"stage": "tp_refresh",
				"source": "Payroll Import Line",
				"generated_at": now_datetime().isoformat(),
				"filters": {"period": period, "batch": batch, "jornada_type": jornada_type},
			}
		return result
		
	except Exception as e:
		frappe.log_error(f"Error refreshing period data: {str(e)}")
		return {"status": "error", "message": str(e)}


@frappe.whitelist()
def approve_period(period=None, batch=None, comments=None, jornada_type=None):
	"""
	Approve entire period or batch for TP and generate prenominas.
	
	Args:
		period: Period to approve (YYYY-MM format)
		batch: Specific batch to approve
		comments: Approval comments
	"""
	
	try:
		enforce_payroll_access("tp_tray")
		service = get_tp_tray_service()
		
		if batch:
			# Approve specific batch
			result = service.bulk_approve_tp(
				batch_filter=batch,
				comments=comments,
				jornada_filter=jornada_type,
			)
		elif period:
			# Get all batches for the period and approve
			batch_filters = {"nomina_period": ["like", f"%{period}%"]}
			batches = frappe.get_all("Payroll Import Batch", 
								   filters=batch_filters, 
								   fields=["name"])
			
			if not batches:
				return {"status": "error", "message": f"No se encontraron lotes para el período {period}"}
			
			# Approve each batch
			total_success = 0
			total_errors = 0
			all_prenomina_results = []
			
			for batch_info in batches:
				batch_result = service.bulk_approve_tp(
					batch_filter=batch_info.name,
					comments=comments,
					jornada_filter=jornada_type,
				)
				if batch_result.get("status") in ["success", "partial"]:
					total_success += batch_result.get("success_count", 0)
					total_errors += batch_result.get("error_count", 0)
					all_prenomina_results.extend(batch_result.get("prenomina_results", []))
			
			result = {
				"status": "success" if total_errors == 0 else "partial",
				"message": f"Período {period}: {total_success} líneas aprobadas, {total_errors} errores",
				"success_count": total_success,
				"error_count": total_errors,
				"affected_batches": [b.name for b in batches],
				"prenomina_results": all_prenomina_results
			}
		else:
			return {"status": "error", "message": "Debe especificar período o lote"}
		
		return result
		
	except Exception as e:
		frappe.log_error(f"Error approving period/batch: {str(e)}")
		return {"status": "error", "message": str(e)}


@frappe.whitelist()
def approve_employees(employee_ids, comments=None, jornada_type=None):
	"""
	Approve specific employees for TP.
	
	Args:
		employee_ids: JSON string or list of employee IDs
		comments: Approval comments
	"""
	enforce_payroll_access("tp_tray")

	try:
		if isinstance(employee_ids, str):
			employee_ids = frappe.parse_json(employee_ids)
		
		service = get_tp_tray_service()
		return service.bulk_approve_tp(
			employee_ids=employee_ids,
			comments=comments,
			jornada_filter=jornada_type,
		)
		
	except Exception as e:
		frappe.log_error(f"Error approving employees: {str(e)}")
		return {"status": "error", "message": str(e)}


@frappe.whitelist()
def get_prenomina_preview(batch_name, limit=10, jornada_type=None):
	"""
	Get preview of Prenomina data for a batch.
	
	Args:
		batch_name: Name of the batch
		limit: Number of employees to preview
	"""
	enforce_payroll_access("tp_tray")

	try:
		return frappe.call("hubgh.hubgh.payroll_export_prenomina.get_prenomina_preview", 
					  batch_name=batch_name, limit=limit, jornada_filter=jornada_type)
		
	except Exception as e:
		frappe.log_error(f"Error getting prenomina preview: {str(e)}")
		return {"status": "error", "message": str(e)}


@frappe.whitelist()
def generate_prenomina(batch_name, jornada_type=None):
	"""
	Generate Prenomina export for a batch.
	
	Args:
		batch_name: Name of the batch
	"""
	enforce_payroll_access("tp_tray")

	try:
		return frappe.call("hubgh.hubgh.payroll_export_prenomina.generate_prenomina_export", 
					  batch_name=batch_name, jornada_filter=jornada_type)
		
	except Exception as e:
		frappe.log_error(f"Error generating prenomina: {str(e)}")
		return {"status": "error", "message": str(e)}


@frappe.whitelist() 
def get_batch_details(batch_name):
	"""
	Get detailed information about a specific batch.
	
	Args:
		batch_name: Name of the batch
	"""
	enforce_payroll_access("tp_tray")

	try:
		enforce_payroll_access("tp_tray")
		# Get batch document
		batch_doc = frappe.get_doc("Payroll Import Batch", batch_name)
		
		# Get line summary
		line_summary = frappe.db.sql("""
			SELECT 
				status,
				tc_status,
				tp_status,
				COUNT(*) as count,
				SUM(amount) as total_amount
			FROM `tabPayroll Import Line`
			WHERE batch = %s
			GROUP BY status, tc_status, tp_status
		""", [batch_name], as_dict=True)
		
		# Get employee count
		employee_count = frappe.db.sql("""
			SELECT COUNT(DISTINCT COALESCE(matched_employee, employee_id)) as count
			FROM `tabPayroll Import Line`
			WHERE batch = %s
		""", [batch_name], as_dict=True)[0].count
		
		return {
			"status": "success",
			"batch_info": {
				"name": batch_doc.name,
				"nomina_period": batch_doc.nomina_period,
				"source_type": batch_doc.source_type,
				"source_file": batch_doc.source_file,
				"aprobado_tc_por": batch_doc.aprobado_tc_por,
				"aprobado_tc_fecha": batch_doc.aprobado_tc_fecha,
				"creation": batch_doc.creation,
				"owner": batch_doc.owner
			},
			"line_summary": line_summary,
			"employee_count": employee_count
		}
		
	except Exception as e:
		frappe.log_error(f"Error getting batch details: {str(e)}")
		return {"status": "error", "message": str(e)}
