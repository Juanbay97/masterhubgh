"""
Payroll Publishers - People Ops Event integration for payroll novelties.

This module publishes payroll events to the People Ops backbone using
the nomina.* taxonomy for proper routing and sensitivity handling.

Sprint 3: Core payroll event publishing with full taxonomy support.
"""

import frappe
from frappe.utils import now_datetime, getdate
from typing import Dict, Any, Optional

from hubgh.hubgh.people_ops_event_publishers import publish_people_ops_event, _doc_value


# Payroll-specific taxonomies for People Ops Events
PAYROLL_TAXONOMIES = {
	"nomina.importada": "Línea importada de fuente externa",
	"nomina.regla_aplicada": "Regla de negocio aplicada",
	"nomina.regla_rechazada": "Regla no aplicó (validación)",
	"nomina.tc_revisada": "Revisada por TC (contador)",
	"nomina.tc_rechazada": "Rechazada por TC",
	"nomina.tp_aprobada": "Aprobada por TP (gerencia)",
	"nomina.prenomina_generada": "Prenomina generada para período",
	"nomina.error_validacion": "Error en validación de datos",
	"nomina.dedup_detectada": "Línea duplicada detectada",
	"nomina.manual_override": "Ajuste manual aplicado"
}

# Sensitivity mapping based on novelty type
NOVELTY_SENSITIVITY_MAP = {
	# Clinical data (health-related)
	"clinical": ["INC-EG", "INC-AT", "ENF-GENERAL", "MATERNIDAD", "LICENCIA-MEDICA"],

	# Additional clinical aliases historically emitted by SST/payroll sources
	"clinical_extra": ["ACC-TRABAJO", "ENF-LABORAL"],
	
	# Disciplinary matters
	"disciplinary": ["NNR", "DNR", "AUSENTISMO", "BONIF-PERD", "SANCION", "DESC-DISCIPLINARIO"],
	
	# Operational (normal business)
	"operational": [
		"HD", "HN", "HED", "HEN", "DESCANSO", "VACACIONES", 
		"HORA-EXTRA", "RECARGO", "AUX-TRANSPORTE", "AUX-ALIMENTACION",
		"BONIFICACION", "COMISION", "PRIMA"
	],
	
	# Financial (sensitive amounts)
	"financial": ["SALARIO-BASE", "PRESTAMOS", "EMBARGOS", "PAYFLOW", "LIBRANZAS"]
}


def canonical_payroll_taxonomy(taxonomy: str) -> str:
	tax = str(taxonomy or "").strip().lower()
	if tax.startswith("nomina."):
		return tax
	tail = tax.split(".", 1)[-1].strip() if tax else "importada"
	return f"nomina.{tail or 'importada'}"


def determine_novelty_sensitivity(novelty_type: str) -> str:
	"""
	Determine sensitivity level for a novelty type.
	
	Args:
		novelty_type: The novelty type code
		
	Returns:
		Sensitivity level: clinical, sst_clinical, disciplinary, financial, or operational
	"""
	
	if not novelty_type:
		return "operational"
	
	# Check each sensitivity category
	for sensitivity, types in NOVELTY_SENSITIVITY_MAP.items():
		if novelty_type in types:
			return "clinical" if sensitivity == "clinical_extra" else sensitivity
	
	# Check partial matches for codes with suffixes
	for sensitivity, types in NOVELTY_SENSITIVITY_MAP.items():
		for type_pattern in types:
			if novelty_type.startswith(type_pattern.split("-")[0]):
				return "clinical" if sensitivity == "clinical_extra" else sensitivity
	
	# Default to operational
	return "operational"


def publish_payroll_import_event(line_doc, taxonomy: str = "nomina.importada", **kwargs) -> Optional[str]:
	"""
	Publish People Ops Event for payroll import line.
	
	Args:
		line_doc: PayrollImportLine document or dict
		taxonomy: Event taxonomy (defaults to nomina.importada)
		**kwargs: Additional event parameters
		
	Returns:
		Event ID if published, None if skipped
	"""
	
	try:
		employee_id = _doc_value(line_doc, "matched_employee") or _doc_value(line_doc, "employee_id")
		novelty_type = _doc_value(line_doc, "novedad_type", "")
		
		# Determine sensitivity based on novelty type
		sensitivity = determine_novelty_sensitivity(novelty_type)
		
		# Build event payload
		payload = {
			"persona": employee_id,
			"area": "nomina",
			"taxonomy": canonical_payroll_taxonomy(taxonomy),
			"sensitivity": sensitivity,
			"state": _doc_value(line_doc, "status", "Pendiente"),
			"severity": novelty_type,
			"source_doctype": "Payroll Import Line",
			"source_name": _doc_value(line_doc, "name"),
			"refs": {
				"batch": _doc_value(line_doc, "batch"),
				"novelty_type": novelty_type,
				"novelty_date": _doc_value(line_doc, "novedad_date"),
				"quantity": _doc_value(line_doc, "quantity"),
				"amount": _doc_value(line_doc, "amount"),
				"employee_name": _doc_value(line_doc, "employee_name"),
				"source_sheet": _doc_value(line_doc, "source_sheet")
			},
			"occurred_on": _doc_value(line_doc, "novedad_date") or _doc_value(line_doc, "modified"),
			**kwargs  # Allow override of any field
		}
		
		return publish_people_ops_event(payload)
		
	except Exception as e:
		frappe.log_error(f"Error publishing payroll import event: {str(e)}")
		return None


def publish_business_rule_event(line_doc, rule_applied: str, rule_notes: str = None, **kwargs) -> Optional[str]:
	"""
	Publish People Ops Event for business rule application.
	
	Args:
		line_doc: PayrollImportLine document or dict
		rule_applied: The rule code that was applied
		rule_notes: Optional rule application notes
		**kwargs: Additional event parameters
		
	Returns:
		Event ID if published, None if skipped
	"""
	
	try:
		employee_id = _doc_value(line_doc, "matched_employee") or _doc_value(line_doc, "employee_id")
		novelty_type = _doc_value(line_doc, "novedad_type", "")
		
		# Determine if rule was successful or rejected
		taxonomy = "nomina.regla_aplicada"
		state = "Aplicada"
		
		if rule_applied in ["ERROR", "VALIDATION_FAILED"]:
			taxonomy = "nomina.regla_rechazada"
			state = "Rechazada"
		
		# Determine sensitivity based on novelty type
		sensitivity = determine_novelty_sensitivity(novelty_type)
		
		# Build event payload
		payload = {
			"persona": employee_id,
			"area": "nomina",
			"taxonomy": taxonomy,
			"sensitivity": sensitivity,
			"state": state,
			"severity": rule_applied,
			"source_doctype": "Payroll Import Line",
			"source_name": _doc_value(line_doc, "name"),
			"refs": {
				"batch": _doc_value(line_doc, "batch"),
				"novelty_type": novelty_type,
				"rule_applied": rule_applied,
				"rule_notes": rule_notes or "",
				"original_amount": _doc_value(line_doc, "amount"),
				"employee_name": _doc_value(line_doc, "employee_name")
			},
			"occurred_on": now_datetime(),
			**kwargs
		}
		
		return publish_people_ops_event(payload)
		
	except Exception as e:
		frappe.log_error(f"Error publishing business rule event: {str(e)}")
		return None


def publish_tc_review_event(line_doc, tc_status: str, tc_comments: str = None, reviewer: str = None, **kwargs) -> Optional[str]:
	"""
	Publish People Ops Event for TC review action.
	
	Args:
		line_doc: PayrollImportLine document or dict
		tc_status: TC status (Aprobado, Rechazado, etc.)
		tc_comments: Optional TC comments
		reviewer: User performing the review
		**kwargs: Additional event parameters
		
	Returns:
		Event ID if published, None if skipped
	"""
	
	try:
		employee_id = _doc_value(line_doc, "matched_employee") or _doc_value(line_doc, "employee_id")
		novelty_type = _doc_value(line_doc, "novedad_type", "")
		
		# Determine taxonomy based on TC action
		taxonomy = "nomina.tc_revisada"
		if tc_status == "Rechazado":
			taxonomy = "nomina.tc_rechazada"
		
		# Determine sensitivity based on novelty type
		sensitivity = determine_novelty_sensitivity(novelty_type)
		
		# Build event payload
		payload = {
			"persona": employee_id,
			"area": "nomina",
			"taxonomy": taxonomy,
			"sensitivity": sensitivity,
			"state": tc_status,
			"severity": novelty_type,
			"source_doctype": "Payroll Import Line",
			"source_name": _doc_value(line_doc, "name"),
			"refs": {
				"batch": _doc_value(line_doc, "batch"),
				"novelty_type": novelty_type,
				"tc_status": tc_status,
				"tc_comments": tc_comments or "",
				"reviewer": reviewer or frappe.session.user,
				"amount": _doc_value(line_doc, "amount"),
				"employee_name": _doc_value(line_doc, "employee_name")
			},
			"occurred_on": now_datetime(),
			**kwargs
		}
		
		return publish_people_ops_event(payload)
		
	except Exception as e:
		frappe.log_error(f"Error publishing TC review event: {str(e)}")
		return None


def publish_tp_approval_event(batch_doc, tp_status: str, approver: str = None, **kwargs) -> Optional[str]:
	"""
	Publish People Ops Event for TP batch approval.
	
	Args:
		batch_doc: PayrollImportBatch document or dict
		tp_status: TP status (Aprobado, Rechazado)
		approver: User performing the approval
		**kwargs: Additional event parameters
		
	Returns:
		Event ID if published, None if skipped
	"""
	
	try:
		batch_name = _doc_value(batch_doc, "name")
		period = _doc_value(batch_doc, "nomina_period", "")
		
		# Build event payload
		payload = {
			"persona": approver or frappe.session.user,  # TP approval is user-centric
			"area": "nomina",
			"taxonomy": "nomina.tp_aprobada",
			"sensitivity": "operational",
			"state": tp_status,
			"severity": "batch_approval",
			"source_doctype": "Payroll Import Batch",
			"source_name": batch_name,
			"refs": {
				"batch": batch_name,
				"period": period,
				"tp_status": tp_status,
				"approver": approver or frappe.session.user,
				"source_file": _doc_value(batch_doc, "source_file"),
				"source_type": _doc_value(batch_doc, "source_type")
			},
			"occurred_on": now_datetime(),
			**kwargs
		}
		
		return publish_people_ops_event(payload)
		
	except Exception as e:
		frappe.log_error(f"Error publishing TP approval event: {str(e)}")
		return None


def publish_prenomina_generation_event(batch_doc, file_path: str = None, **kwargs) -> Optional[str]:
	"""
	Publish People Ops Event for prenomina file generation.
	
	Args:
		batch_doc: PayrollImportBatch document or dict
		file_path: Path to generated prenomina file
		**kwargs: Additional event parameters
		
	Returns:
		Event ID if published, None if skipped
	"""
	
	try:
		batch_name = _doc_value(batch_doc, "name")
		period = _doc_value(batch_doc, "nomina_period", "")
		
		# Build event payload
		payload = {
			"persona": frappe.session.user,  # Generation is user-triggered
			"area": "nomina", 
			"taxonomy": "nomina.prenomina_generada",
			"sensitivity": "financial",  # Prenomina contains salary data
			"state": "Generada",
			"severity": "prenomina_export",
			"source_doctype": "Payroll Import Batch",
			"source_name": batch_name,
			"refs": {
				"batch": batch_name,
				"period": period,
				"file_path": file_path or "",
				"generated_by": frappe.session.user,
				"line_count": frappe.db.count("Payroll Import Line", {"batch": batch_name, "status": ["!=", "Duplicado"]}),
				"export_format": "prenomina_xlsx"
			},
			"occurred_on": now_datetime(),
			**kwargs
		}
		
		return publish_people_ops_event(payload)
		
	except Exception as e:
		frappe.log_error(f"Error publishing prenomina generation event: {str(e)}")
		return None


def publish_error_event(line_doc, error_type: str, error_message: str, **kwargs) -> Optional[str]:
	"""
	Publish People Ops Event for payroll processing errors.
	
	Args:
		line_doc: PayrollImportLine document or dict
		error_type: Type of error (validation, rule_engine, etc.)
		error_message: Error description
		**kwargs: Additional event parameters
		
	Returns:
		Event ID if published, None if skipped
	"""
	
	try:
		employee_id = _doc_value(line_doc, "matched_employee") or _doc_value(line_doc, "employee_id")
		novelty_type = _doc_value(line_doc, "novedad_type", "")
		
		# Build event payload
		payload = {
			"persona": employee_id,
			"area": "nomina",
			"taxonomy": "nomina.error_validacion",
			"sensitivity": determine_novelty_sensitivity(novelty_type),
			"state": "Error",
			"severity": error_type,
			"source_doctype": "Payroll Import Line",
			"source_name": _doc_value(line_doc, "name"),
			"refs": {
				"batch": _doc_value(line_doc, "batch"),
				"novelty_type": novelty_type,
				"error_type": error_type,
				"error_message": error_message,
				"employee_name": _doc_value(line_doc, "employee_name"),
				"source_row": _doc_value(line_doc, "row_number")
			},
			"occurred_on": now_datetime(),
			**kwargs
		}
		
		return publish_people_ops_event(payload)
		
	except Exception as e:
		frappe.log_error(f"Error publishing error event: {str(e)}")
		return None


# =============================================================================
# Bulk Publishing Functions
# =============================================================================

def publish_batch_import_events(batch_name: str) -> Dict[str, Any]:
	"""
	Publish People Ops Events for all lines in an imported batch.
	
	Args:
		batch_name: Name of the PayrollImportBatch
		
	Returns:
		Summary of events published
	"""
	
	try:
		# Get all valid lines from the batch
		lines = frappe.get_all("Payroll Import Line",
			filters={"batch": batch_name, "status": ["!=", "Duplicado"]},
			fields=["name", "matched_employee", "employee_id", "employee_name", 
				   "novedad_type", "novedad_date", "status", "validation_errors"]
		)
		
		published_count = 0
		error_count = 0
		
		for line in lines:
			# Publish import event
			event_id = publish_payroll_import_event(line)
			if event_id:
				published_count += 1
			else:
				error_count += 1
			
			# If line has errors, publish error event
			if line.get("validation_errors"):
				error_event_id = publish_error_event(line, "validation", line["validation_errors"])
				if error_event_id:
					published_count += 1
		
		return {
			"status": "success",
			"batch": batch_name,
			"lines_processed": len(lines),
			"events_published": published_count,
			"errors": error_count
		}
		
	except Exception as e:
		frappe.log_error(f"Error publishing batch import events for {batch_name}: {str(e)}")
		return {
			"status": "error",
			"message": str(e),
			"events_published": 0
		}


def publish_bulk_tc_events(line_ids: list, tc_status: str, tc_comments: str = None, reviewer: str = None) -> Dict[str, Any]:
	"""
	Publish People Ops Events for bulk TC actions.
	
	Args:
		line_ids: List of PayrollImportLine IDs
		tc_status: TC status applied
		tc_comments: Optional comments
		reviewer: User performing the action
		
	Returns:
		Summary of events published
	"""
	
	try:
		published_count = 0
		error_count = 0
		
		for line_id in line_ids:
			try:
				line_doc = frappe.get_doc("Payroll Import Line", line_id)
				event_id = publish_tc_review_event(line_doc, tc_status, tc_comments, reviewer)
				if event_id:
					published_count += 1
				else:
					error_count += 1
			except Exception:
				error_count += 1
		
		return {
			"status": "success",
			"tc_action": tc_status,
			"lines_processed": len(line_ids),
			"events_published": published_count,
			"errors": error_count
		}
		
	except Exception as e:
		frappe.log_error(f"Error publishing bulk TC events: {str(e)}")
		return {
			"status": "error",
			"message": str(e),
			"events_published": 0
		}


# =============================================================================
# Integration Hooks
# =============================================================================

def on_payroll_import_line_save(doc, method=None):
	"""
	Hook: Called when PayrollImportLine is saved.
	Publishes appropriate events based on changes.
	"""
	
	# Skip if this is a new document without changes
	if doc.is_new():
		return
	
	# Check what changed and publish relevant events
	if doc.has_value_changed("tc_status") and doc.tc_status in ["Aprobado", "Rechazado"]:
		publish_tc_review_event(doc, doc.tc_status, doc.rule_notes)
	
	if doc.has_value_changed("rule_applied") and doc.rule_applied:
		publish_business_rule_event(doc, doc.rule_applied, doc.rule_notes)


def on_payroll_import_batch_save(doc, method=None):
	"""
	Hook: Called when PayrollImportBatch is saved.
	Publishes TP approval events when appropriate.
	"""
	
	# Skip if this is a new document
	if doc.is_new():
		return
	
	# Check for TP approval changes
	if doc.has_value_changed("aprobado_tc_por") and doc.aprobado_tc_por:
		publish_tp_approval_event(doc, "Aprobado", doc.aprobado_tc_por)


# =============================================================================
# Public API Functions
# =============================================================================

@frappe.whitelist()
def publish_events_for_batch(batch_name):
	"""
	API endpoint to manually publish events for a batch.
	"""
	return publish_batch_import_events(batch_name)


def publish_liquidation_event(liquidation_doc):
	"""
	Publish People Ops Event when liquidation case is closed.
	"""
	try:
		event_data = {
			"area": "nomina",
			"taxonomy": "nomina.liquidacion_cerrada",
			"sensitivity": "operational",
			"persona": liquidation_doc.employee,
			"source_doctype": "Payroll Liquidation Case",
			"source_name": liquidation_doc.name,
			"refs": {
				"total_liquidacion": str(liquidation_doc.total_liquidacion),
				"retirement_date": str(liquidation_doc.retirement_date),
				"status": liquidation_doc.status
			}
		}
		publish_people_ops_event(event_data)
	except Exception as e:
		frappe.log_error(f"Error publishing liquidation event: {e}")


@frappe.whitelist()
def get_payroll_taxonomy_info():
	"""
	API endpoint to get available payroll taxonomies.
	"""
	return {
		"taxonomies": PAYROLL_TAXONOMIES,
		"sensitivity_map": NOVELTY_SENSITIVITY_MAP
	}
