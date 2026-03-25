"""
TC Tray Service - Business logic for TC (Contador) review workflow.

Provides consolidation and approval logic for imported payroll lines
that require TC review before proceeding to TP tray.

Sprint 3: Core TC workflow with bulk approve/reject and employee consolidation.
"""

import frappe
from frappe import _
from frappe.utils import now_datetime, getdate, flt
from typing import List, Dict, Any, Optional
import json

from hubgh.hubgh.payroll_employee_compat import (
	build_employee_parametrization_message,
	get_payroll_employee_context,
)
from hubgh.hubgh.payroll_publishers import publish_tc_review_event, publish_bulk_tc_events


class PayrollTCTrayService:
	"""Service for managing TC review workflow."""
	
	def __init__(self):
		self.supported_statuses = ["Pendiente", "Revisado", "Aprobado", "Rechazado"]
	
	def query_pending_lines(
		self,
		employee_filter: str = None,
		batch_filter: str = None,
		period_filter: str = None,
		status_filter: str = None,
		limit: int = 100,
	) -> Dict[str, Any]:
		"""
		Query all pending lines for TC review.
		
		Args:
			employee_filter: Optional employee name/id filter
			batch_filter: Optional batch filter  
			limit: Maximum lines to return
			
		Returns:
			Dict with consolidated data ready for tray UI
		"""
		
		try:
			# Build filters for query
			filters = {
				"status": ["in", ["Válido", "Procesado"]],
			}

			if status_filter:
				filters["tc_status"] = status_filter
			else:
				filters["tc_status"] = ["in", ["Pendiente", "Revisado"]]
			
			if employee_filter:
				filters["employee_name"] = ["like", f"%{employee_filter}%"]
			if batch_filter:
				filters["batch"] = batch_filter
			elif period_filter:
				batches = frappe.get_all(
					"Payroll Import Batch",
					filters={"period": period_filter},
					pluck="name",
				)
				if not batches:
					return {
						"status": "success",
						"total_lines": 0,
						"total_employees": 0,
						"lines": [],
						"consolidated": [],
						"batch_summary": [],
						"filters_applied": filters,
					}
				filters["batch"] = ["in", batches]
			
			# Query lines with all required fields
			lines = frappe.get_all("Payroll Import Line",
				filters=filters,
				fields=[
					"name", "batch", "employee_id", "employee_name", "matched_employee", "matched_employee_doctype",
					"novedad_type", "novedad_date", "quantity", "amount", 
					"rule_applied", "rule_notes", "tc_status", "validation_errors",
					"source_sheet", "source_row_data"
				],
				order_by="batch desc, employee_name asc, novedad_date desc",
				limit=int(limit or 100)
			)
			
			# Get consolidated view by employee
			consolidated = self.consolidate_by_employee(lines)
			
			# Get batch summary
			batch_summary = self.get_batch_summary(lines)
			
			return {
				"status": "success",
				"total_lines": len(lines),
				"total_employees": len(consolidated),
				"lines": lines,
				"consolidated": consolidated,
				"batch_summary": batch_summary,
				"filters_applied": filters
			}
			
		except Exception as e:
			frappe.log_error(f"Error querying TC pending lines: {str(e)}")
			return {
				"status": "error",
				"message": str(e),
				"lines": [],
				"consolidated": [],
				"batch_summary": []
			}
	
	def consolidate_by_employee(self, lines: List[Dict]) -> List[Dict[str, Any]]:
		"""
		Consolidate import lines by employee for easier TC review.
		
		Args:
			lines: List of PayrollImportLine records
			
		Returns:
			List of employee summaries with aggregated data
		"""
		
		employee_map = {}
		
		for line in lines:
			emp_key = line.get("matched_employee") or line.get("employee_id") or "UNKNOWN"
			emp_name = line.get("employee_name") or "Sin Nombre"
			
			if emp_key not in employee_map:
				employee_map[emp_key] = {
					"employee_id": emp_key,
					"employee_name": emp_name,
					"matched_employee": line.get("matched_employee"),
					"matched_employee_doctype": line.get("matched_employee_doctype") or "Ficha Empleado",
					"line_count": 0,
					"total_amount": 0,
					"batches": set(),
					"novelty_types": set(), 
					"has_errors": False,
					"has_rules": False,
					"tc_status_summary": {},
					"lines": []
				}
			
			emp_summary = employee_map[emp_key]
			emp_summary["lines"].append(line)
			emp_summary["line_count"] += 1
			emp_summary["total_amount"] += flt(line.get("amount", 0))
			emp_summary["batches"].add(line.get("batch"))
			emp_summary["novelty_types"].add(line.get("novedad_type"))
			
			# Track status indicators
			if line.get("validation_errors"):
				emp_summary["has_errors"] = True
			if line.get("rule_applied"):
				emp_summary["has_rules"] = True
				
			# Count TC statuses
			tc_status = line.get("tc_status", "Pendiente")
			emp_summary["tc_status_summary"][tc_status] = emp_summary["tc_status_summary"].get(tc_status, 0) + 1
		
		# Convert sets to lists for JSON serialization
		result = []
		for emp_data in employee_map.values():
			emp_data["batches"] = list(emp_data["batches"])
			emp_data["novelty_types"] = list(emp_data["novelty_types"])
			
			# Determine overall TC status
			status_counts = emp_data["tc_status_summary"]
			if status_counts.get("Rechazado", 0) > 0:
				emp_data["overall_tc_status"] = "Rechazado"
			elif status_counts.get("Aprobado", 0) == emp_data["line_count"]:
				emp_data["overall_tc_status"] = "Aprobado"
			elif status_counts.get("Revisado", 0) > 0:
				emp_data["overall_tc_status"] = "Revisado"
			else:
				emp_data["overall_tc_status"] = "Pendiente"
			
			result.append(emp_data)
		
		# Sort by employee name
		result.sort(key=lambda x: x["employee_name"])
		return result
	
	def get_batch_summary(self, lines: List[Dict]) -> List[Dict[str, Any]]:
		"""Get summary statistics by batch."""
		
		batch_map = {}
		
		for line in lines:
			batch = line.get("batch")
			if not batch:
				continue
				
			if batch not in batch_map:
				batch_map[batch] = {
					"batch": batch,
					"line_count": 0,
					"employee_count": set(),
					"total_amount": 0,
					"status_breakdown": {}
				}
			
			summary = batch_map[batch]
			summary["line_count"] += 1
			summary["employee_count"].add(line.get("matched_employee") or line.get("employee_id"))
			summary["total_amount"] += flt(line.get("amount", 0))
			
			tc_status = line.get("tc_status", "Pendiente")
			summary["status_breakdown"][tc_status] = summary["status_breakdown"].get(tc_status, 0) + 1
		
		# Convert sets to counts
		result = []
		for batch_data in batch_map.values():
			batch_data["employee_count"] = len(batch_data["employee_count"])
			result.append(batch_data)
			
		result.sort(key=lambda x: x["batch"], reverse=True)
		return result
	
	def get_employee_summary(self, employee_id: str, batch: str = None) -> Dict[str, Any]:
		"""
		Get detailed summary for a specific employee.
		
		Args:
			employee_id: Employee ID (matched or source)
			batch: Optional batch filter
			
		Returns:
			Detailed employee data with line breakdown
		"""
		
		try:
			filters = {
				"status": ["in", ["Válido", "Procesado"]], 
				"tc_status": ["in", ["Pendiente", "Revisado"]]
			}
			
			# Handle both matched employee and source employee_id
			filters["$or"] = [
				{"matched_employee": employee_id},
				{"employee_id": employee_id}
			]
			
			if batch:
				filters["batch"] = batch
			
			lines = frappe.get_all("Payroll Import Line",
				filters=filters,
				fields=["*"],
				order_by="novedad_date desc, novedad_type"
			)
			
			if not lines:
				return {
					"status": "error",
					"message": "No se encontraron novedades para la Ficha Empleado o identificador indicado.",
					"lines": [],
				}

			context = get_payroll_employee_context(employee_id)
			param_warning = build_employee_parametrization_message(
				context,
				required_fields=["contrato", "salary", "pdv"],
			)

			# Calculate totals and analysis
			total_amount = sum(flt(line.get("amount", 0)) for line in lines)
			novelty_types = list(set(line.get("novedad_type") for line in lines if line.get("novedad_type")))
			
			# Group by date for timeline view
			timeline = {}
			for line in lines:
				date_key = str(line.get("novedad_date", "Sin Fecha"))
				if date_key not in timeline:
					timeline[date_key] = []
				timeline[date_key].append(line)
			
			return {
				"status": "success",
				"employee_id": employee_id,
				"employee_name": lines[0].get("employee_name"),
				"matched_employee": lines[0].get("matched_employee"),
				"matched_employee_doctype": lines[0].get("matched_employee_doctype") or context.get("employee_doctype"),
				"employee_parametrization_warning": param_warning,
				"total_lines": len(lines),
				"total_amount": total_amount,
				"novelty_types": novelty_types,
				"lines": lines,
				"timeline": timeline
			}
			
		except Exception as e:
			frappe.log_error(f"Error getting employee summary for {employee_id}: {str(e)}")
			return {"status": "error", "message": str(e), "lines": []}
	
	def bulk_approve(self, line_ids: List[str], comments: str = None, approver: str = None) -> Dict[str, Any]:
		"""
		Bulk approve TC status for multiple lines.
		
		Args:
			line_ids: List of PayrollImportLine names to approve
			comments: Optional approval comments
			approver: User performing approval (defaults to current user)
			
		Returns:
			Result summary with success/failure counts
		"""
		
		return self._bulk_update_tc_status(line_ids, "Aprobado", comments, approver)
	
	def bulk_reject(self, line_ids: List[str], comments: str = None, rejector: str = None) -> Dict[str, Any]:
		"""
		Bulk reject TC status for multiple lines.
		
		Args:
			line_ids: List of PayrollImportLine names to reject
			comments: Optional rejection comments
			rejector: User performing rejection (defaults to current user)
			
		Returns:
			Result summary with success/failure counts
		"""
		
		return self._bulk_update_tc_status(line_ids, "Rechazado", comments, rejector)
	
	def _bulk_update_tc_status(self, line_ids: List[str], new_status: str, 
							  comments: str = None, user: str = None) -> Dict[str, Any]:
		"""
		Internal method for bulk TC status updates.
		"""
		
		if new_status not in self.supported_statuses:
			return {"status": "error", "message": f"Estado de etapa TC no válido: {new_status}"}
		
		user = user or frappe.session.user
		success_count = 0
		error_count = 0
		errors = []
		
		for line_id in line_ids:
			try:
				line_doc = frappe.get_doc("Payroll Import Line", line_id)
				
				# Validate current status allows transition
				if line_doc.tc_status == "Aprobado" and new_status != "Aprobado":
					errors.append(f"{line_id}: Ya está aprobado")
					error_count += 1
					continue
				
				# Update status and metadata
				line_doc.tc_status = new_status
				
				# Update rule notes with TC action
				existing_notes = line_doc.rule_notes or ""
				tc_action = f"TC {new_status} por {user} en {now_datetime()}"
				if comments:
					tc_action += f" - {comments}"
				
				if existing_notes:
					line_doc.rule_notes = f"{existing_notes}\n{tc_action}"
				else:
					line_doc.rule_notes = tc_action
				
				line_doc.save(ignore_permissions=True)
				success_count += 1
				
				# Publish People Ops Event for TC action
				try:
					publish_tc_review_event(line_doc, new_status, comments, user)
				except Exception as e:
					frappe.log_error(f"Error publishing TC event for {line_id}: {str(e)}")
				
			except Exception as e:
				errors.append(f"{line_id}: {str(e)}")
				error_count += 1
		
		# Commit transaction
		frappe.db.commit()
		
		# Publish bulk event summary if successful
		if success_count > 0:
			try:
				publish_bulk_tc_events(line_ids, new_status, comments, user)
			except Exception as e:
				frappe.log_error(f"Error publishing bulk TC event: {str(e)}")
		
		return {
			"status": "success" if error_count == 0 else "partial",
			"message": f"{success_count} líneas actualizadas, {error_count} errores",
			"success_count": success_count,
			"error_count": error_count,
			"errors": errors,
			"new_status": new_status
		}


# =============================================================================
# Public API Functions
# =============================================================================

@frappe.whitelist()
def get_tc_tray_data(employee_filter=None, batch_filter=None, limit=100):
	"""
	API endpoint to get TC tray data for UI.
	
	Returns JSON data with pending lines and consolidation.
	"""
	
	service = PayrollTCTrayService()
	return service.query_pending_lines(
		employee_filter=employee_filter,
		batch_filter=batch_filter, 
		limit=int(limit or 100)
	)


@frappe.whitelist()
def get_employee_detail(employee_id, batch=None):
	"""
	API endpoint to get detailed employee data for TC review.
	"""
	
	service = PayrollTCTrayService()
	return service.get_employee_summary(employee_id, batch)


@frappe.whitelist()
def bulk_approve_tc(line_ids, comments=None):
	"""
	API endpoint for bulk TC approval.
	
	Args:
		line_ids: JSON string or list of line IDs
		comments: Optional approval comments
	"""
	
	if isinstance(line_ids, str):
		line_ids = frappe.parse_json(line_ids)
	
	service = PayrollTCTrayService()
	return service.bulk_approve(line_ids, comments)


@frappe.whitelist()
def bulk_reject_tc(line_ids, comments=None):
	"""
	API endpoint for bulk TC rejection.
	
	Args:
		line_ids: JSON string or list of line IDs  
		comments: Optional rejection comments
	"""
	
	if isinstance(line_ids, str):
		line_ids = frappe.parse_json(line_ids)
	
	service = PayrollTCTrayService()
	return service.bulk_reject(line_ids, comments)


def get_tc_tray_service() -> PayrollTCTrayService:
	"""Get singleton instance of PayrollTCTrayService."""
	return PayrollTCTrayService()
