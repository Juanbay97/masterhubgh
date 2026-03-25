"""
Payroll Novedad Service - Business rules engine for payroll novelties.

This service acts as the domain layer for payroll novelty processing,
applying business rules and transformations to import lines before
they become Payroll Events.

Sprint 3 will expand this with full rule engine implementation.
"""

import frappe
import json
from typing import List, Dict, Any

from hubgh.hubgh.payroll_employee_compat import (
	build_employee_parametrization_message,
	get_payroll_employee_context,
)


class PayrollNovedadService:
	"""Service for handling payroll novelty business logic."""
	
	def __init__(self):
		self.rules_cache = {}
		
	def apply_business_rules(self, import_lines: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
		"""
		Apply business rules to a list of import lines.
		
		This is the main entry point for rule processing.
		Sprint 3 will implement the full rule engine here.
		
		Args:
			import_lines: List of PayrollImportLine dicts
			
		Returns:
			List of processed lines with rule_applied and rule_notes populated
		"""
		
		processed_lines = []
		
		for line in import_lines:
			try:
				processed_line = self._apply_line_rules(line)
				processed_lines.append(processed_line)
			except Exception as e:
				# Mark line with error but don't fail entire batch
				line["status"] = "Error"
				line["validation_errors"] = f"Error aplicando reglas: {str(e)}"
				processed_lines.append(line)
				
		return processed_lines
	
	def _apply_line_rules(self, line: Dict[str, Any]) -> Dict[str, Any]:
		"""
		Apply business rules to a single import line.
		
		Implements the full rule engine for Sprint 3:
		- HOME12-FIJO / HOME12-PROP rules
		- AUX-DOM-NOCHE calculation  
		- TOPE-DESC-702K validation
		- SANITAS-PREM pairing
		- GAFAS-CONV subsidies
		- INC-LEGAL days mapping
		"""
		
		# Clone the line to avoid mutations
		processed_line = line.copy()
		
		# Initialize rule tracking
		processed_line["rule_applied"] = None
		processed_line["rule_notes"] = None
		
		# Get novelty type and employee context
		novelty_type = processed_line.get("novedad_type")
		employee_id = processed_line.get("matched_employee") or processed_line.get("employee_id")
		
		if not novelty_type or not employee_id:
			processed_line["rule_notes"] = "Datos insuficientes: falta Ficha Empleado resuelta o tipo de novedad para aplicar reglas."
			return processed_line
		
		# Get employee context for rule evaluation
		batch = processed_line.get("batch") or ""
		employee_context = self._get_employee_context(employee_id, batch)
		param_warning = employee_context.get("parametrization_warning")
		
		try:
			# Apply rules in priority order
			
			# 1. HOME12-FIJO: AUX-HOME12 if pdv_count >= 6
			if self._should_apply_home12_fijo(novelty_type, employee_context):
				processed_line = self._apply_home12_fijo_rule(processed_line, employee_context)
			
			# 2. HOME12-PROP: AUX-HOME12 proporcional si hay INC-* en período
			elif self._should_apply_home12_prop(novelty_type, employee_context):
				processed_line = self._apply_home12_prop_rule(processed_line, employee_context)
			
			# 3. AUX-DOM-NOCHE: AUX-DOMINICAL if turno >21:55 en domingo
			elif self._should_apply_aux_dom_noche(novelty_type, processed_line):
				processed_line = self._apply_aux_dom_noche_rule(processed_line)
			
			# 4. TOPE-DESC-702K: Validar suma deducciones <= 702000
			elif self._should_validate_deduction_cap(novelty_type):
				processed_line = self._validate_deduction_cap(processed_line, employee_context)
			
			# 5. SANITAS-PREM: Crear devengo+descuento par (neto 0)
			elif self._should_apply_sanitas_prem(novelty_type):
				processed_line = self._apply_sanitas_prem_rule(processed_line)
			
			# 6. GAFAS-CONV: Aplicar subsidio según regla
			elif self._should_apply_gafas_conv(novelty_type):
				processed_line = self._apply_gafas_conv_rule(processed_line, employee_context)
			
			# 7. INC-LEGAL: Mapear días EG/AT a IBC calculation
			elif self._should_apply_inc_legal(novelty_type):
				processed_line = self._apply_inc_legal_rule(processed_line, employee_context)
			
			# Default validation for other types
			else:
				processed_line = self._apply_default_validation(processed_line, novelty_type)
		
		except Exception as e:
			processed_line["rule_applied"] = "ERROR"
			processed_line["rule_notes"] = f"Error aplicando reglas: {str(e)}"
			processed_line["status"] = "Error"
			frappe.log_error(f"Rule engine error for line {line.get('name')}: {str(e)}")

		if param_warning:
			existing_notes = processed_line.get("rule_notes") or ""
			processed_line["rule_notes"] = f"{existing_notes}\n{param_warning}".strip()
		
		return processed_line
	
	def _get_employee_context(self, employee_id: str, batch: str = "") -> Dict[str, Any]:
		"""Get employee context data needed for rule evaluation."""
		
		context = {
			"employee_id": employee_id,
			"pdv_count": 0,
			"contract_type": None,
			"home12_eligible": False,
			"monthly_deductions": 0,
			"has_incapacity_in_period": False,
			"domingo_hours_after_2155": 0
		}
		
		try:
			# Get employee master data
			emp_data = get_payroll_employee_context(employee_id)
			if emp_data:
				context["contract_type"] = emp_data.get("employment_type") or None
				context["parametrization_warning"] = build_employee_parametrization_message(
					emp_data,
					["contrato", "salary", "pdv"],
				)
				
				# Check if employee works at HOME 12 PDVs
				# This would typically come from employee assignment or PDV mapping
				# For now, we'll use a simple heuristic based on company/department
				company = emp_data.get("company") or ""
				department = emp_data.get("department") or ""
				branch = emp_data.get("branch") or ""
				
				if any("home" in value.lower() for value in [company, department, branch] if value):
					context["home12_eligible"] = True
					# Assume 6+ PDV count for HOME locations (should be dynamic in production)
					context["pdv_count"] = 6
			
			# Calculate monthly deductions for this period
			if batch:
				period_deductions = frappe.db.sql("""
					SELECT SUM(amount) as total
					FROM `tabPayroll Import Line`
					WHERE batch = %s 
					AND (matched_employee = %s OR employee_id = %s)
					AND novedad_type LIKE '%%DESC%%'
					AND status != 'Duplicado'
				""", [batch, employee_id, employee_id], as_dict=True)
				
				if period_deductions and period_deductions[0].total:
					context["monthly_deductions"] = float(period_deductions[0].total)
			
			# Check for incapacity in current period
			if batch:
				incapacity_count = frappe.get_all(
					"Payroll Import Line",
					filters={
						"batch": batch,
						"novedad_type": ["like", "INC-%"],
						"status": ["!=", "Duplicado"],
					},
					or_filters={
						"matched_employee": employee_id,
						"employee_id": employee_id,
					},
					fields=["name"],
					limit=1,
				)
				context["has_incapacity_in_period"] = incapacity_count > 0
		
		except Exception as e:
			frappe.log_error(f"Error getting employee context for {employee_id}: {str(e)}")
		
		return context
	
	# Rule condition checkers
	def _should_apply_home12_fijo(self, novelty_type: str, employee_context: Dict) -> bool:
		"""Check if HOME12-FIJO rule should apply."""
		return (bool(employee_context.get("home12_eligible")) and 
				employee_context.get("contract_type") == "Full-time" and
				employee_context.get("pdv_count", 0) >= 6 and
				novelty_type in ["VACACIONES", "LICENCIA", "DESCANSO"])
	
	def _should_apply_home12_prop(self, novelty_type: str, employee_context: Dict) -> bool:
		"""Check if HOME12-PROP rule should apply."""
		return (bool(employee_context.get("home12_eligible")) and 
				bool(employee_context.get("has_incapacity_in_period")) and
				novelty_type.startswith("INC-"))
	
	def _should_apply_aux_dom_noche(self, novelty_type: str, line: Dict) -> bool:
		"""Check if AUX-DOM-NOCHE rule should apply."""
		source_data = line.get("source_row_data") or {}
		return (novelty_type in ["HD", "HN"] and 
				self._is_sunday_after_2155(line.get("novedad_date"), source_data))
	
	def _should_validate_deduction_cap(self, novelty_type: str) -> bool:
		"""Check if deduction cap validation should apply."""
		return novelty_type in ["PAYFLOW", "LIBRANZAS", "DESC-OTROS"]
	
	def _should_apply_sanitas_prem(self, novelty_type: str) -> bool:
		"""Check if SANITAS-PREM rule should apply."""
		return novelty_type == "SANITAS-PREM"
	
	def _should_apply_gafas_conv(self, novelty_type: str) -> bool:
		"""Check if GAFAS-CONV rule should apply."""
		return novelty_type == "GAFAS-CONV"
	
	def _should_apply_inc_legal(self, novelty_type: str) -> bool:
		"""Check if INC-LEGAL rule should apply."""
		return novelty_type in ["INC-EG", "INC-AT"]
	
	# Rule implementations
	def _apply_home12_fijo_rule(self, line: Dict, employee_context: Dict) -> Dict:
		"""Apply HOME12-FIJO rule: $110K/month fixed subsidy."""
		try:
			# Add AUX-HOME12 fixed amount (monthly)
			line["rule_applied"] = "HOME12-FIJO"
			line["rule_notes"] = f"Subsidio HOME12 fijo $110,000/mes aplicado - PDV count: {employee_context.get('pdv_count', 0)}"
			
			# In production, this would create an additional line or modify amount
			# For now, we just mark it for downstream processing
			if not line.get("amount"):
				line["amount"] = 110000
			else:
				line["amount"] = float(line["amount"]) + 110000
			
			return line
		except Exception as e:
			line["rule_notes"] = f"Error aplicando HOME12-FIJO: {str(e)}"
			return line
	
	def _apply_home12_prop_rule(self, line: Dict, employee_context: Dict) -> Dict:
		"""Apply HOME12-PROP rule: proportional subsidy based on incapacity days."""
		try:
			# Calculate proportional subsidy based on days worked vs incapacity
			incapacity_days = float(line.get("quantity", 0))
			working_days_in_month = 30  # Simplified, should be calendar-based
			
			proportion = max(0, (working_days_in_month - incapacity_days) / working_days_in_month)
			proportional_amount = 110000 * proportion
			
			line["rule_applied"] = "HOME12-PROP"
			line["rule_notes"] = f"Subsidio HOME12 proporcional: ${proportional_amount:,.0f} ({proportion:.2%} de $110,000)"
			
			if not line.get("amount"):
				line["amount"] = proportional_amount
			else:
				line["amount"] = float(line["amount"]) + proportional_amount
			
			return line
		except Exception as e:
			line["rule_notes"] = f"Error aplicando HOME12-PROP: {str(e)}"
			return line
	
	def _apply_aux_dom_noche_rule(self, line: Dict) -> Dict:
		"""Apply AUX-DOM-NOCHE rule: $7K per Sunday after 21:55."""
		try:
			# Extract hours from source data to determine if after 21:55
			source_data = line.get("source_row_data") or {}
			sunday_hours = self._extract_sunday_night_hours(source_data)
			
			if sunday_hours > 0:
				aux_amount = 7000 * sunday_hours
				line["rule_applied"] = "AUX-DOM-NOCHE"
				line["rule_notes"] = f"Auxiliar dominical nocturno: ${aux_amount:,} ({sunday_hours} horas después 21:55)"
				
				if not line.get("amount"):
					line["amount"] = aux_amount
				else:
					line["amount"] = float(line["amount"]) + aux_amount
			
			return line
		except Exception as e:
			line["rule_notes"] = f"Error aplicando AUX-DOM-NOCHE: {str(e)}"
			return line
	
	def _validate_deduction_cap(self, line: Dict, employee_context: Dict) -> Dict:
		"""Validate TOPE-DESC-702K: deduction cap at $702,000."""
		try:
			current_deduction = float(line.get("amount", 0))
			total_deductions = employee_context.get("monthly_deductions", 0) + current_deduction
			deduction_cap = 702000
			
			if total_deductions > deduction_cap:
				excess = total_deductions - deduction_cap
				adjusted_amount = current_deduction - excess
				
				line["rule_applied"] = "TOPE-DESC-702K"
				line["rule_notes"] = f"Descuento ajustado por tope: ${adjusted_amount:,} (reducido ${excess:,})"
				line["amount"] = max(0, adjusted_amount)
				
				if adjusted_amount <= 0:
					line["status"] = "Error"
					line["validation_errors"] = f"Descuento excede tope mensual de ${deduction_cap:,}"
			else:
				line["rule_applied"] = "TOPE-DESC-VALIDATED"
				line["rule_notes"] = f"Descuento dentro del tope: ${total_deductions:,} / ${deduction_cap:,}"
			
			return line
		except Exception as e:
			line["rule_notes"] = f"Error validando tope descuentos: {str(e)}"
			return line
	
	def _apply_sanitas_prem_rule(self, line: Dict) -> Dict:
		"""Apply SANITAS-PREM rule: create offsetting devengo+descuento pair."""
		try:
			amount = float(line.get("amount", 0))
			
			line["rule_applied"] = "SANITAS-PREM"
			line["rule_notes"] = f"Sanitas Premium: Devengo ${amount:,} + Descuento ${amount:,} (neto $0)"
			
			# In production, this would create two separate lines
			# For now, we mark it for downstream processing
			line["amount"] = 0  # Net effect is zero
			
			return line
		except Exception as e:
			line["rule_notes"] = f"Error aplicando SANITAS-PREM: {str(e)}"
			return line
	
	def _apply_gafas_conv_rule(self, line: Dict, employee_context: Dict) -> Dict:
		"""Apply GAFAS-CONV rule: eyewear subsidy according to policy."""
		try:
			# Standard eyewear subsidy amount (should come from policy catalog)
			subsidy_amount = 50000  # Example amount
			
			line["rule_applied"] = "GAFAS-CONV"
			line["rule_notes"] = f"Subsidio gafas convencionales: ${subsidy_amount:,}"
			
			if not line.get("amount"):
				line["amount"] = subsidy_amount
			
			return line
		except Exception as e:
			line["rule_notes"] = f"Error aplicando GAFAS-CONV: {str(e)}"
			return line
	
	def _apply_inc_legal_rule(self, line: Dict, employee_context: Dict) -> Dict:
		"""Apply INC-LEGAL rule: map EG/AT days to IBC calculation."""
		try:
			incapacity_days = float(line.get("quantity", 0))
			incapacity_type = line.get("novedad_type", "")
			
			# Different calculations for EG vs AT
			if incapacity_type == "INC-EG":
				# Enfermedad General: 2/3 of salary from day 4
				calculation_days = max(0, incapacity_days - 3)
				calculation_rate = 0.67
			elif incapacity_type == "INC-AT":
				# Accidente de Trabajo: 100% from day 1
				calculation_days = incapacity_days
				calculation_rate = 1.0
			else:
				calculation_days = incapacity_days
				calculation_rate = 0.67
			
			line["rule_applied"] = "INC-LEGAL"
			line["rule_notes"] = f"Incapacidad {incapacity_type}: {calculation_days} días x {calculation_rate:.0%} = IBC calculation"
			
			# Mark for downstream IBC calculation
			line["ibc_days"] = calculation_days
			line["ibc_rate"] = calculation_rate
			
			return line
		except Exception as e:
			line["rule_notes"] = f"Error aplicando INC-LEGAL: {str(e)}"
			return line
	
	def _apply_default_validation(self, line: Dict, novelty_type: str) -> Dict:
		"""Apply default validation for novelty types without specific rules."""
		
		if novelty_type in ["HD", "HN", "HED", "HEN"]:
			line["rule_applied"] = "HORA-VALIDATION"
			line["rule_notes"] = "Horas validadas - sin reglas especiales aplicables"
		elif novelty_type in ["VACACIONES", "DESCANSO"]:
			line["rule_applied"] = "TIEMPO-VALIDATION"
			line["rule_notes"] = "Tiempo libre validado"
		elif novelty_type == "AUSENTISMO":
			line["rule_applied"] = "AUSENTISMO-CHECK"
			line["rule_notes"] = "Ausentismo detectado - requiere validación de soporte"
		else:
			line["rule_applied"] = "GENERAL-VALIDATION"
			line["rule_notes"] = f"Novedad {novelty_type} procesada sin reglas especiales"
		
		return line
	
	# Helper methods
	def _is_sunday_after_2155(self, novelty_date, source_row_data: Dict) -> bool:
		"""Check if work hours were on Sunday after 21:55."""
		try:
			from frappe.utils import getdate
			import datetime
			
			if not novelty_date:
				return False
			
			date_obj = getdate(novelty_date)
			is_sunday = date_obj.weekday() == 6  # Sunday = 6
			
			if not is_sunday:
				return False
			
			# Extract time info from source data
			# This would depend on CLONK file structure
			if isinstance(source_row_data, str):
				source_row_data = json.loads(source_row_data) if source_row_data else {}
			elif source_row_data is None:
				source_row_data = {}
			
			# Look for hour indicators in source data
			hour_data = source_row_data.get("hora_fin") or source_row_data.get("turno_fin")
			if hour_data:
				# Parse hour format (assuming HH:MM or similar)
				try:
					hour_parts = str(hour_data).split(":")
					if len(hour_parts) >= 2:
						hour = int(hour_parts[0])
						minute = int(hour_parts[1])
						return hour > 21 or (hour == 21 and minute >= 55)
				except (ValueError, TypeError):
					pass
			
			# Fallback: check if it's a night shift novelty
			return "HN" in source_row_data.get("tipo_hora", "") or "nocturno" in str(source_row_data).lower()
			
		except Exception:
			return False
	
	def _extract_sunday_night_hours(self, source_row_data: Dict) -> int:
		"""Extract number of Sunday night hours from source data."""
		try:
			if isinstance(source_row_data, str):
				source_row_data = json.loads(source_row_data) if source_row_data else {}
			elif source_row_data is None:
				source_row_data = {}
			
			# Look for Sunday night hour count
			sunday_hours = source_row_data.get("horas_domingo_noche", 0)
			if sunday_hours:
				return int(sunday_hours)
			
			# Fallback: estimate based on shift type
			if "dominical" in str(source_row_data).lower() and "noche" in str(source_row_data).lower():
				return 1  # Assume 1 hour if we can't get exact count
			
			return 0
		except Exception:
			return 0
		
	def get_applicable_rules(self, novelty_type: str, employee_context: Dict = {}) -> List[str]:
		"""
		Get list of business rules that apply to a novelty type.
		
		Sprint 3 will implement this based on PayrollRuleCatalog.
		"""
		
		# Load rules from catalog (cached)
		if not self.rules_cache:
			self._load_rules_cache()
			
		applicable = []
		
		# Stub implementation - Sprint 3 will query PayrollRuleCatalog
		rule_map = {
			"INC-EG": ["HOME12-FIJO", "HOME12-PROP"],
			"INC-AT": ["HOME12-FIJO", "HOME12-PROP"], 
			"HD": ["AUX-DOM-NOCHE"],
			"HN": ["AUX-DOM-NOCHE"],
		}
		
		return rule_map.get(novelty_type, [])
		
	def _load_rules_cache(self):
		"""Load active business rules from PayrollRuleCatalog."""
		
		try:
			rules = frappe.get_all("Payroll Rule Catalog", 
				filters={"activa": 1},
				fields=["codigo_regla", "nombre_regla", "parametros", "aplica_a"]
			)
			
			for rule in rules:
				self.rules_cache[rule.codigo_regla] = rule
				
		except Exception as e:
			frappe.log_error(f"Error loading payroll rules cache: {str(e)}")
			self.rules_cache = {}


# =============================================================================
# Public API Functions
# =============================================================================

@frappe.whitelist()
def apply_business_rules_to_batch(batch_name: str) -> Dict[str, Any]:
	"""
	Apply business rules to all lines in a batch.
	
	This is the main API endpoint for rule processing from the UI.
	"""
	
	try:
		# Get all lines in the batch
		lines = frappe.get_all("Payroll Import Line",
			filters={"batch": batch_name, "status": ["!=", "Duplicado"]},
			fields=["name", "employee_id", "novedad_type", "quantity", 
				   "novedad_date", "source_sheet", "status"]
		)
		
		if not lines:
			return {"status": "error", "message": "No hay líneas válidas para procesar"}
			
		# Initialize service and process
		service = PayrollNovedadService()
		processed_lines = service.apply_business_rules(lines)
		
		# Update the lines with rule results
		updated_count = 0
		for processed_line in processed_lines:
			try:
				line_doc = frappe.get_doc("Payroll Import Line", processed_line["name"])
				
				# Update rule fields
				if processed_line.get("rule_applied"):
					line_doc.rule_applied = processed_line["rule_applied"]
				if processed_line.get("rule_notes"):
					line_doc.rule_notes = processed_line["rule_notes"]
				if processed_line.get("status"):
					line_doc.status = processed_line["status"]
				if processed_line.get("validation_errors"):
					line_doc.validation_errors = processed_line["validation_errors"]
					
				line_doc.save(ignore_permissions=True)
				updated_count += 1
				
			except Exception as e:
				frappe.log_error(f"Error updating line {processed_line.get('name')}: {str(e)}")
				
		return {
			"status": "success",
			"message": f"Reglas aplicadas a {updated_count} líneas",
			"processed_count": updated_count,
			"total_lines": len(lines)
		}
		
	except Exception as e:
		frappe.log_error(f"Error applying business rules to batch {batch_name}: {str(e)}")
		return {"status": "error", "message": str(e)}


def get_payroll_service() -> PayrollNovedadService:
	"""Get singleton instance of PayrollNovedadService."""
	return PayrollNovedadService()
