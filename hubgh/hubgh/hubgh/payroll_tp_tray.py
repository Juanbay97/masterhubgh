"""
TP Tray Service - Business logic for TP operational-stage consolidation and review.

Provides executive-level consolidation of TC-approved lines, showing employee summaries 
with totals per novelty type, and final approval workflow for Prenomina generation.

Sprint 4: TP tray consolidation with Prenomina export integration.
"""

import frappe
from frappe import _
from frappe.utils import now_datetime, getdate, nowdate, flt, cstr
from typing import List, Dict, Any, Optional
import json

from hubgh.hubgh.payroll_employee_compat import (
	build_employee_parametrization_message,
	get_payroll_employee_context,
	normalize_tipo_jornada,
)
from hubgh.hubgh.payroll_permissions import enforce_payroll_access
from hubgh.hubgh.payroll_publishers import publish_tp_approval_event, publish_prenomina_generation_event
from hubgh.hubgh.payroll_export_prenomina import generate_prenomina_export


class PayrollTPTrayService:
	"""Service for managing TP review workflow and Prenomina generation."""
	
	def __init__(self):
		self.supported_statuses = ["Pendiente", "Revisado", "Aprobado", "Rechazado"]
		self.valid_tc_statuses = ["Aprobado"]  # Only TC-approved lines go to TP
	
	def consolidate_by_period(
		self,
		period_filter: str = None,
		batch_filter: str = None,
		limit: int = 500,
		jornada_filter: str = None,
	) -> Dict[str, Any]:
		"""
		Consolidate TC-approved lines by period for TP executive review.
		
		Args:
			period_filter: Optional period filter (YYYY-MM format)
			batch_filter: Optional specific batch filter
			limit: Maximum lines to process
			
		Returns:
			Dict with consolidated data ready for TP tray UI
		"""
		
		try:
			# Build filters - only TC-approved lines are eligible for TP review
			filters = {
				"status": ["in", ["Válido", "Procesado"]],
				"tc_status": ["in", self.valid_tc_statuses]  # Only TC-approved
			}
			
			if period_filter:
				# Filter by nomina_period in the batch
				batch_filters = {"nomina_period": ["like", f"%{period_filter}%"]}
				batch_names = [b.name for b in frappe.get_all("Payroll Import Batch", 
															 filters=batch_filters, 
															 fields=["name"])]
				if batch_names:
					filters["batch"] = ["in", batch_names]
				else:
					# No batches for this period
					return self._empty_consolidation_result(period_filter)
			
			if batch_filter:
				filters["batch"] = batch_filter
			
			# Query TC-approved lines
			lines = frappe.get_all("Payroll Import Line",
				filters=filters,
				fields=[
					"name", "batch", "employee_id", "employee_name", "matched_employee", "matched_employee_doctype",
					"novedad_type", "novedad_date", "quantity", "amount", 
					"rule_applied", "rule_notes", "tc_status", "tp_status",
					"source_sheet", "source_row_data"
				],
				order_by="batch desc, employee_name asc, novedad_type asc",
				limit=limit
			)
			lines, jornada_context = self._filter_lines_by_jornada(lines, jornada_filter)
			
			if not lines:
				return self._empty_consolidation_result(
					period_filter,
					jornada_filter=jornada_filter,
					jornada_context=jornada_context,
				)
			
			# Consolidate by employee with novelty type breakdown
			employee_consolidation = self.consolidate_by_employee_with_recargos(lines)
			
			# Get period summary statistics
			period_summary = self.get_period_summary(lines, period_filter or batch_filter)
			
			# Calculate totals for executive summary
			executive_summary = self.calculate_executive_summary(employee_consolidation, period_summary)
			
			return {
				"status": "success",
				"period": period_filter or "Batch Específico",
				"total_lines": len(lines),
				"total_employees": len(employee_consolidation),
				"employee_consolidation": employee_consolidation,
				"period_summary": period_summary,
				"executive_summary": executive_summary,
				"filters_applied": filters,
				"jornada_filter": jornada_context.get("canonical_filter") or "Todas",
				"jornada_filter_warning": self._build_jornada_filter_warning(jornada_context),
				"employees_missing_jornada": jornada_context.get("missing_employee_count", 0),
				"employees_missing_jornada_labels": jornada_context.get("missing_employee_labels", []),
			}
			
		except Exception as e:
			frappe.log_error(f"Error consolidating TP period data: {str(e)}")
			return {
				"status": "error",
				"message": str(e),
				"employee_consolidation": [],
				"period_summary": {},
				"executive_summary": {},
				"jornada_filter": normalize_tipo_jornada(jornada_filter) or "Todas",
			}
	
	def consolidate_by_employee_with_recargos(self, lines: List[Dict]) -> List[Dict[str, Any]]:
		"""
		Consolidate lines by employee, calculating recargos (nocturnal/dominical) and totals.
		
		Sprint 5: Enhanced with HOME12 prorated subsidy calculation.
		
		Args:
			lines: List of TC-approved PayrollImportLine records
			
		Returns:
			List of employee consolidations with novelty type breakdowns and totals
		"""
		
		employee_map = {}
		
		for line in lines:
			emp_key = line.get("matched_employee") or line.get("employee_id") or "UNKNOWN"
			emp_name = line.get("employee_name") or "Sin Nombre"
			employee_context = get_payroll_employee_context(emp_key)
			param_warning = build_employee_parametrization_message(
				employee_context,
				required_fields=["contrato", "salary", "pdv", "monthly_hours"],
			)
			
			if emp_key not in employee_map:
				jornada_label = employee_context.get("tipo_jornada") or ""
				jornada_source = employee_context.get("tipo_jornada_source") or ""
				jornada_display = jornada_label or "Sin dato canónico en Ficha Empleado"
				if jornada_label and jornada_source == "contrato_fallback":
					jornada_display = f"{jornada_label} (fallback Contrato/RRLL)"
				employee_map[emp_key] = {
					"employee_id": emp_key,
					"employee_name": emp_name,
					"matched_employee": line.get("matched_employee"),
					"matched_employee_doctype": line.get("matched_employee_doctype") or employee_context.get("employee_doctype"),
					"employee_parametrization_warning": param_warning,
					"tipo_jornada": jornada_label,
					"tipo_jornada_source": jornada_source,
					"tipo_jornada_display": jornada_display,
					"batches": set(),
					"novelty_breakdown": {},
					"hour_totals": {
						"HD": 0,  # Horas Diurnas
						"HN": 0,  # Horas Nocturnas  
						"HED": 0, # Horas Extras Diurnas
						"HEN": 0  # Horas Extras Nocturnas
					},
					"recargos": {
						"nocturnal_amount": 0,
						"dominical_amount": 0,
						"extra_hours_amount": 0
					},
					"devengo_total": 0,
					"deduccion_total": 0,
					"auxilios_total": 0,
					"home12_subsidy": 0,  # Sprint 5: HOME12 subsidy tracking
					"tp_status_summary": {},
					"lines": []
				}
			
			emp_data = employee_map[emp_key]
			emp_data["lines"].append(line)
			emp_data["batches"].add(line.get("batch"))
			
			# Consolidate by novelty type
			novelty_type = line.get("novedad_type", "UNKNOWN")
			if novelty_type not in emp_data["novelty_breakdown"]:
				emp_data["novelty_breakdown"][novelty_type] = {
					"quantity": 0,
					"amount": 0,
					"line_count": 0,
					"dates": set()
				}
			
			breakdown = emp_data["novelty_breakdown"][novelty_type]
			breakdown["quantity"] += flt(line.get("quantity", 0))
			breakdown["amount"] += flt(line.get("amount", 0))
			breakdown["line_count"] += 1
			breakdown["dates"].add(str(line.get("novedad_date", "")))
			
			# Calculate hour totals for recargo calculation
			quantity = flt(line.get("quantity", 0))
			amount = flt(line.get("amount", 0))
			
			if novelty_type in ["HD", "HN", "HED", "HEN"] and quantity > 0:
				emp_data["hour_totals"][novelty_type] += quantity
			
			# Apply recargo calculations
			recargo_info = self.calculate_recargos(novelty_type, quantity, line)
			emp_data["recargos"]["nocturnal_amount"] += recargo_info.get("nocturnal", 0)
			emp_data["recargos"]["dominical_amount"] += recargo_info.get("dominical", 0)
			emp_data["recargos"]["extra_hours_amount"] += recargo_info.get("extra_hours", 0)
			
			# Categorize amounts for summary
			if amount > 0:
				if novelty_type.startswith("DESC-") or "DEDUC" in novelty_type:
					emp_data["deduccion_total"] += amount
				elif novelty_type.startswith("AUX-"):
					emp_data["auxilios_total"] += amount
				else:
					emp_data["devengo_total"] += amount
			elif amount < 0:
				emp_data["deduccion_total"] += abs(amount)
			
			# Sprint 5: Apply HOME12 prorated subsidy if applicable
			if novelty_type == "AUX-HOME12":
				emp_data["home12_subsidy"] += amount
			elif novelty_type in ["INC-EG", "INC-AT", "LICENCIA"]:
				# Mark employee as having incapacity/license for proration
				emp_data["has_incapacidad_or_licencia"] = True
			
			# Track TP status
			tp_status = line.get("tp_status", "Pendiente")
			emp_data["tp_status_summary"][tp_status] = emp_data["tp_status_summary"].get(tp_status, 0) + 1
		
		# Convert sets to lists and calculate derived values
		result = []
		for emp_data in employee_map.values():
			emp_data["batches"] = list(emp_data["batches"])
			
			# Sprint 5: Calculate HOME12 prorated subsidy if needed
			emp_data = self._apply_home12_proration(emp_data)
			
			# Convert date sets to lists in novelty breakdown
			for novelty_type, breakdown in emp_data["novelty_breakdown"].items():
				breakdown["dates"] = list(breakdown["dates"])
			
			# Calculate net pay
			total_devengos = emp_data["devengo_total"] + emp_data["auxilios_total"]
			total_devengos += sum(emp_data["recargos"].values())
			total_deducciones = emp_data["deduccion_total"]
			
			emp_data["neto_a_pagar"] = total_devengos - total_deducciones
			emp_data["total_devengado"] = total_devengos
			emp_data["total_deducciones"] = total_deducciones
			
			# Determine overall TP status
			status_counts = emp_data["tp_status_summary"]
			total_lines = sum(status_counts.values())
			
			if status_counts.get("Rechazado", 0) > 0:
				emp_data["overall_tp_status"] = "Rechazado"
			elif status_counts.get("Aprobado", 0) == total_lines:
				emp_data["overall_tp_status"] = "Aprobado"
			elif status_counts.get("Revisado", 0) > 0:
				emp_data["overall_tp_status"] = "Revisado"
			else:
				emp_data["overall_tp_status"] = "Pendiente"

			emp_data["recobro_priority"] = self._calculate_weighted_recobro_priority(emp_data)
			emp_data["traceability"] = {
				"contract": "nomina-operativa-v2",
				"stage": "tp_consolidation",
				"generated_at": now_datetime().isoformat(),
				"source": "Payroll Import Line",
				"line_count": len(emp_data.get("lines") or []),
			}

			result.append(emp_data)
		
		# Sort by total neto (highest first) for executive view
		result.sort(key=lambda x: x["neto_a_pagar"], reverse=True)
		return result
	
	def calculate_recargos(self, novelty_type: str, quantity: float, line: Dict) -> Dict[str, float]:
		"""
		Calculate recargos (nocturnal, dominical, extra hours) based on novelty type and context.
		
		Sprint 5 Enhancement: Employee-specific base rates and enhanced recargo rules.
		
		Args:
			novelty_type: Type of novelty (HD, HN, etc.)
			quantity: Number of hours
			line: Full line data for context
			
		Returns:
			Dict with recargo amounts
		"""
		
		recargos = {"nocturnal": 0, "dominical": 0, "extra_hours": 0}
		
		try:
			# Get employee-specific base rate from salary or default
			base_hourly_rate = self._get_employee_base_rate(line)
			
			if novelty_type == "HN":  # Horas Nocturnas
				# Labor law: nocturnal hours = base * 1.25 (9PM-6AM)
				recargos["nocturnal"] = quantity * base_hourly_rate * 0.25  # Additional 25%
			
			elif novelty_type in ["HED", "HEN"]:  # Horas Extras
				# Extra hours have different rates
				if novelty_type == "HED":  # Extras Diurnas
					# First 2 hours: base * 1.25 (25% extra)
					recargos["extra_hours"] = quantity * base_hourly_rate * 0.25
				else:  # HEN - Extras Nocturnas  
					# Nocturnal extra = base * 1.75 (25% night + 50% extra)
					recargos["nocturnal"] = quantity * base_hourly_rate * 0.25
					recargos["extra_hours"] = quantity * base_hourly_rate * 0.50
			
			# Check for dominical work (Sunday/holiday work)
			if self._is_dominical_work(line):
				# Dominical = base * 2.0 (100% additional for Sunday/festive)
				dominical_hours = self._extract_dominical_hours(line)
				recargos["dominical"] = dominical_hours * base_hourly_rate * 1.0
			
		except Exception as e:
			frappe.log_error(f"Error calculating recargos for {novelty_type}: {str(e)}")
		
		return recargos
	
	def _get_employee_base_rate(self, line: Dict) -> float:
		"""
		Get employee-specific base hourly rate from salary data.
		
		Sprint 5: Enhanced to pull from employee salary or PDV defaults.
		
		Args:
			line: Line data with employee information
			
		Returns:
			Base hourly rate for recargo calculations
		"""
		try:
			employee_id = line.get("matched_employee") or line.get("employee_id")
			if not employee_id:
				return 15000  # Default rate
			
			employee_context = get_payroll_employee_context(employee_id)
			monthly_salary = flt(employee_context.get("salary") or 0)
			monthly_hours = flt(employee_context.get("monthly_hours") or 220)
			if monthly_salary > 0 and monthly_hours > 0:
				# Calculate hourly rate from monthly salary
				hourly_rate = monthly_salary / monthly_hours
				if hourly_rate > 5000:
					return hourly_rate
			
			# Fallback: PDV-specific or company defaults
			branch = cstr(employee_context.get("branch") or "")
			if 'HOME12' in branch.upper():
				return 18000  # HOME12 higher rate
			elif 'PDV' in branch.upper():
				return 16000  # PDV standard rate
			else:
				return 15000  # General default
				
		except Exception as e:
			frappe.log_error(f"Error getting employee base rate: {str(e)}")
			return 15000  # Safe fallback
	
	def _apply_home12_proration(self, emp_data: Dict[str, Any]) -> Dict[str, Any]:
		"""
		Apply HOME12 prorated subsidy calculation.
		
		Sprint 5: HOME12 FIJO: $110,000/month if employee in HOME12 PDV with >= 6 PDVs
		HOME12 PROP: Prorated if employee had Incapacidad/Licencia during period
		Proration: (days_worked / days_in_period) * $110,000
		
		Args:
			emp_data: Employee consolidation data
			
		Returns:
			Updated employee data with HOME12 subsidy applied
		"""
		try:
			employee_id = emp_data.get("employee_id")
			if not employee_id:
				return emp_data
			
			# Check if employee is in HOME12 PDV
			if not self._is_home12_employee(employee_id):
				return emp_data
			
			# HOME12 base subsidy amount
			home12_base = 110000
			
			# Check if employee had incapacidad/licencia during period
			has_incapacidad = emp_data.get("has_incapacidad_or_licencia", False)
			
			if has_incapacidad:
				# Calculate prorated subsidy based on days worked vs incapacidad days
				proration_factor = self._calculate_home12_proration_factor(emp_data)
				prorated_amount = home12_base * proration_factor
				
				# Update subsidy and add note
				emp_data["home12_subsidy"] = prorated_amount
				emp_data["home12_proration_note"] = f"Prorrateado: {proration_factor:.2%} por Incapacidad/Licencia"
			else:
				# Full subsidy for FIJO employees
				emp_data["home12_subsidy"] = home12_base
				emp_data["home12_proration_note"] = "HOME12 FIJO: Subsidio completo"
			
			# Add to auxilios total
			emp_data["auxilios_total"] += emp_data["home12_subsidy"]
			
		except Exception as e:
			frappe.log_error(f"Error applying HOME12 proration: {str(e)}")
			emp_data["home12_proration_note"] = f"Error calculando prorreo: {str(e)}"
		
		return emp_data
	
	def _is_home12_employee(self, employee_id: str) -> bool:
		"""Check if employee belongs to HOME12 PDV."""
		try:
			employee_context = get_payroll_employee_context(employee_id)
			branch = cstr(employee_context.get("branch") or "")
			
			# Check if employee is in HOME12 with FIJO contract type
			if 'HOME12' in branch.upper() or 'HOME 12' in branch.upper():
				# Additional check: >= 6 PDVs (simplified for now)
				return True
			return False
		except Exception:
			return False
	
	def _calculate_home12_proration_factor(self, emp_data: Dict[str, Any]) -> float:
		"""
		Calculate proration factor for HOME12 subsidy based on incapacidad/licencia days.
		
		Args:
			emp_data: Employee data with novelty breakdown
			
		Returns:
			Proration factor (0.0 to 1.0)
		"""
		try:
			# Get period from batches to calculate days
			batches = emp_data.get("batches", [])
			if not batches:
				return 1.0
			
			# For simplicity, assume 30 days in period
			days_in_period = 30
			
			# Count incapacidad/licencia days from novelty breakdown
			incapacidad_days = 0
			for novelty_type, breakdown in emp_data.get("novelty_breakdown", {}).items():
				if novelty_type in ["INC-EG", "INC-AT", "LICENCIA"]:
					incapacidad_days += breakdown.get("quantity", 0)
			
			# Calculate days worked
			days_worked = max(0, days_in_period - incapacidad_days)
			proration_factor = days_worked / days_in_period if days_in_period > 0 else 1.0
			
			# Ensure factor is between 0 and 1
			return max(0.0, min(1.0, proration_factor))
			
		except Exception as e:
			frappe.log_error(f"Error calculating HOME12 proration factor: {str(e)}")
			return 1.0  # Default to full subsidy on error
	
	def _is_dominical_work(self, line: Dict) -> bool:
		"""Check if work was performed on Sunday or holiday."""
		try:
			novelty_date = line.get("novedad_date")
			if not novelty_date:
				return False
			
			date_obj = getdate(novelty_date)
			is_sunday = date_obj.weekday() == 6  # Sunday = 6
			
			# Should also check holiday calendar, simplified for now
			return is_sunday
		except Exception:
			return False
	
	def _extract_dominical_hours(self, line: Dict) -> float:
		"""Extract dominical hours from line data."""
		try:
			# If it's a dominical day, assume all hours count
			if self._is_dominical_work(line):
				return flt(line.get("quantity", 0))
			return 0
		except Exception:
			return 0

	def _calculate_weighted_recobro_priority(self, emp_data: Dict[str, Any]) -> Dict[str, Any]:
		"""Build weighted recobro priority for manual TP/TC review."""
		today = getdate(nowdate())
		lines = emp_data.get("lines") or []
		deduccion_total = float(emp_data.get("deduccion_total") or 0)
		line_count = max(len(lines), 1)

		aging_days = 0
		for row in lines:
			date_value = row.get("novedad_date")
			if not date_value:
				continue
			try:
				aging_days = max(aging_days, (today - getdate(date_value)).days)
			except Exception:
				continue

		legality_signal = min(100.0, deduccion_total / 50000.0)
		aging_signal = min(100.0, max(aging_days, 0) * 2.0)
		amount_signal = min(100.0, deduccion_total / 10000.0)
		employee_state_signal = 70.0 if emp_data.get("has_incapacidad_or_licencia") else 35.0
		source_quality_signal = 85.0 if all((row.get("source_sheet") or "").strip() for row in lines) else 45.0
		operational_signal = min(100.0, line_count * 8.0)

		weighted_score = (
			(0.24 * legality_signal)
			+ (0.19 * aging_signal)
			+ (0.21 * amount_signal)
			+ (0.12 * employee_state_signal)
			+ (0.09 * source_quality_signal)
			+ (0.15 * operational_signal)
		)
		score = round(max(0.0, min(100.0, weighted_score)), 2)

		if score >= 75:
			level = "alta"
		elif score >= 45:
			level = "media"
		else:
			level = "baja"

		trace_id = f"TC-TP-{str(emp_data.get('employee_id') or 'NA')}-{today}"
		return {
			"score": score,
			"level": level,
			"drivers": {
				"legality": round(legality_signal, 2),
				"aging": round(aging_signal, 2),
				"amount": round(amount_signal, 2),
				"employee_state": round(employee_state_signal, 2),
				"source_quality": round(source_quality_signal, 2),
				"operational_impact": round(operational_signal, 2),
			},
			"trace_id": trace_id,
			"deduccion_total": round(deduccion_total, 2),
			"aging_days": aging_days,
		}
	
	def get_period_summary(self, lines: List[Dict], period_identifier: str) -> Dict[str, Any]:
		"""Get summary statistics for the period."""
		
		summary = {
			"period_identifier": period_identifier,
			"total_lines": len(lines),
			"unique_employees": len(set(line.get("matched_employee") or line.get("employee_id") for line in lines)),
			"batches": list(set(line.get("batch") for line in lines if line.get("batch"))),
			"novelty_type_counts": {},
			"amount_totals": {
				"devengos": 0,
				"deducciones": 0,
				"neto": 0
			},
			"status_breakdown": {
				"tc_approved": 0,
				"tp_pending": 0,
				"tp_approved": 0,
				"tp_rejected": 0
			}
		}
		
		for line in lines:
			# Count novelty types
			novelty_type = line.get("novedad_type", "UNKNOWN")
			summary["novelty_type_counts"][novelty_type] = summary["novelty_type_counts"].get(novelty_type, 0) + 1
			
			# Accumulate amounts
			amount = flt(line.get("amount", 0))
			if amount > 0:
				if novelty_type.startswith("DESC-") or "DEDUC" in novelty_type:
					summary["amount_totals"]["deducciones"] += amount
				else:
					summary["amount_totals"]["devengos"] += amount
			elif amount < 0:
				summary["amount_totals"]["deducciones"] += abs(amount)
			
			# Count statuses
			tc_status = line.get("tc_status", "")
			tp_status = line.get("tp_status", "Pendiente")
			
			if tc_status == "Aprobado":
				summary["status_breakdown"]["tc_approved"] += 1
			
			if tp_status == "Pendiente":
				summary["status_breakdown"]["tp_pending"] += 1
			elif tp_status == "Aprobado":
				summary["status_breakdown"]["tp_approved"] += 1
			elif tp_status == "Rechazado":
				summary["status_breakdown"]["tp_rejected"] += 1
		
		summary["amount_totals"]["neto"] = summary["amount_totals"]["devengos"] - summary["amount_totals"]["deducciones"]
		
		return summary
	
	def calculate_executive_summary(self, employee_consolidation: List[Dict], 
								   period_summary: Dict) -> Dict[str, Any]:
		"""Calculate executive-level summary for TP dashboard."""
		
		summary = {
			"total_employees": len(employee_consolidation),
			"employees_ready_for_approval": 0,
			"employees_with_issues": 0,
			"total_payroll_amount": 0,
			"average_per_employee": 0,
			"top_cost_employees": [],
			"novelty_summary": {
				"most_common": [],
				"high_impact": []
			},
			"approval_readiness": {
				"ready": 0,
				"needs_review": 0,
				"has_rejections": 0
			},
			"recobro_weighted": {
				"high_priority": 0,
				"medium_priority": 0,
				"low_priority": 0,
				"top_cases": [],
			},
		}
		
		employee_amounts = []
		novelty_impact = {}
		
		for emp in employee_consolidation:
			neto = emp.get("neto_a_pagar", 0)
			employee_amounts.append({
				"employee_name": emp.get("employee_name"),
				"employee_id": emp.get("employee_id"),
				"neto_a_pagar": neto
			})
			
			summary["total_payroll_amount"] += neto
			
			# Analyze novelty impact
			for novelty_type, breakdown in emp.get("novelty_breakdown", {}).items():
				if novelty_type not in novelty_impact:
					novelty_impact[novelty_type] = {"count": 0, "total_amount": 0}
				novelty_impact[novelty_type]["count"] += breakdown.get("line_count", 0)
				novelty_impact[novelty_type]["total_amount"] += breakdown.get("amount", 0)
			
			# Check approval readiness
			status = emp.get("overall_tp_status", "Pendiente")
			if status == "Aprobado":
				summary["approval_readiness"]["ready"] += 1
			elif status == "Rechazado":
				summary["approval_readiness"]["has_rejections"] += 1
				summary["employees_with_issues"] += 1
			else:
				summary["approval_readiness"]["needs_review"] += 1

			recobro = emp.get("recobro_priority") or {}
			level = recobro.get("level")
			if level == "alta":
				summary["recobro_weighted"]["high_priority"] += 1
			elif level == "media":
				summary["recobro_weighted"]["medium_priority"] += 1
			else:
				summary["recobro_weighted"]["low_priority"] += 1
			summary["recobro_weighted"]["top_cases"].append(
				{
					"employee_id": emp.get("employee_id"),
					"employee_name": emp.get("employee_name"),
					"score": recobro.get("score", 0),
					"level": level or "baja",
					"trace_id": recobro.get("trace_id"),
				}
			)
		
		# Calculate averages
		if summary["total_employees"] > 0:
			summary["average_per_employee"] = summary["total_payroll_amount"] / summary["total_employees"]
		
		# Top 5 employees by amount
		summary["top_cost_employees"] = sorted(employee_amounts, 
											  key=lambda x: x["neto_a_pagar"], 
											  reverse=True)[:5]
		
		# Most common novelties
		novelty_by_count = sorted(novelty_impact.items(), 
								 key=lambda x: x[1]["count"], 
								 reverse=True)[:5]
		summary["novelty_summary"]["most_common"] = [
			{"type": k, "count": v["count"], "total_amount": v["total_amount"]}
			for k, v in novelty_by_count
		]
		
		# High impact novelties by amount
		novelty_by_amount = sorted(novelty_impact.items(), 
								  key=lambda x: abs(x[1]["total_amount"]), 
								  reverse=True)[:5]
		summary["novelty_summary"]["high_impact"] = [
			{"type": k, "count": v["count"], "total_amount": v["total_amount"]}
			for k, v in novelty_by_amount
		]
		
		summary["employees_ready_for_approval"] = summary["approval_readiness"]["ready"]
		summary["recobro_weighted"]["top_cases"] = sorted(
			summary["recobro_weighted"]["top_cases"],
			key=lambda row: float(row.get("score") or 0),
			reverse=True,
		)[:5]

		return summary
	
	def _empty_consolidation_result(
		self,
		period: str = None,
		jornada_filter: str = None,
		jornada_context: Dict[str, Any] | None = None,
	) -> Dict[str, Any]:
		"""Return empty result structure when no data found."""
		jornada_context = jornada_context or self._build_jornada_context(jornada_filter)
		return {
			"status": "success",
			"period": period or "Sin Datos",
			"total_lines": 0,
			"total_employees": 0,
			"employee_consolidation": [],
			"period_summary": {
				"period_identifier": period,
				"total_lines": 0,
				"unique_employees": 0,
				"batches": [],
				"novelty_type_counts": {},
				"amount_totals": {"devengos": 0, "deducciones": 0, "neto": 0},
				"status_breakdown": {"tc_approved": 0, "tp_pending": 0, "tp_approved": 0, "tp_rejected": 0}
			},
			"executive_summary": {
				"total_employees": 0,
				"employees_ready_for_approval": 0,
				"total_payroll_amount": 0,
				"approval_readiness": {"ready": 0, "needs_review": 0, "has_rejections": 0}
			},
			"jornada_filter": jornada_context.get("canonical_filter") or "Todas",
			"jornada_filter_warning": self._build_jornada_filter_warning(jornada_context),
			"employees_missing_jornada": jornada_context.get("missing_employee_count", 0),
			"employees_missing_jornada_labels": jornada_context.get("missing_employee_labels", []),
		}
	
	def bulk_approve_tp(
		self,
		employee_ids: List[str] = None,
		batch_filter: str = None,
		comments: str = None,
		approver: str = None,
		jornada_filter: str = None,
	) -> Dict[str, Any]:
		"""
		Bulk approve TP status for employees or entire batch.
		
		Args:
			employee_ids: List of specific employee IDs to approve (optional)
			batch_filter: Batch to approve entirely (optional)
			comments: Optional approval comments
			approver: User performing approval (defaults to current user)
			
		Returns:
			Result summary with success/failure counts and prenomina generation
		"""
		
		try:
			approver = approver or frappe.session.user
			
			# Build filters for lines to approve
			filters = {
				"status": ["in", ["Válido", "Procesado"]],
				"tc_status": ["in", self.valid_tc_statuses],  # Only TC-approved
				"tp_status": ["in", ["Pendiente", "Revisado"]]  # Not already approved
			}
			
			if employee_ids:
				filters["$or"] = [
					{"matched_employee": ["in", employee_ids]},
					{"employee_id": ["in", employee_ids]}
				]
			elif batch_filter:
				filters["batch"] = batch_filter
			else:
				return {"status": "error", "message": "Debe especificar fichas de empleado o lote para aprobar."}
			
			# Get lines to approve
			lines_to_approve = frappe.get_all("Payroll Import Line",
				filters=filters,
				fields=["name", "batch", "matched_employee", "employee_id", "employee_name"]
			)
			lines_to_approve, jornada_context = self._filter_lines_by_jornada(lines_to_approve, jornada_filter)
			
			if not lines_to_approve:
				message = "No hay líneas elegibles para aprobación TP"
				warning = self._build_jornada_filter_warning(jornada_context)
				if warning:
					message = f"{message}. {warning}"
				return {"status": "error", "message": message}
			
			# Update TP status
			success_count = 0
			error_count = 0
			errors = []
			affected_batches = set()
			
			for line_data in lines_to_approve:
				try:
					line_doc = frappe.get_doc("Payroll Import Line", line_data["name"])
					line_doc.tp_status = "Aprobado"
					
					# Add approval notes
					approval_note = f"TP Aprobado por {approver} en {now_datetime()}"
					if comments:
						approval_note += f" - {comments}"
					
					existing_notes = line_doc.rule_notes or ""
					line_doc.rule_notes = f"{existing_notes}\n{approval_note}" if existing_notes else approval_note
					
					line_doc.save(ignore_permissions=True)
					success_count += 1
					affected_batches.add(line_data["batch"])
					
				except Exception as e:
					errors.append(f"{line_data['name']}: {str(e)}")
					error_count += 1
			
			# Commit the status updates
			frappe.db.commit()
			
			# Generate prenomina for affected batches
			prenomina_results = []
			for batch_name in affected_batches:
				try:
					# Mark batch as TP approved
					batch_doc = frappe.get_doc("Payroll Import Batch", batch_name)
					if not batch_doc.aprobado_tc_por:  # This should be TP approval tracking
						batch_doc.aprobado_tc_por = approver  # Reusing field for now
						batch_doc.aprobado_tc_fecha = now_datetime()
						batch_doc.save(ignore_permissions=True)
					
					# Generate prenomina export
					prenomina_result = generate_prenomina_export(batch_name, jornada_filter=jornada_filter)
					prenomina_results.append({
						"batch": batch_name,
						"prenomina_status": prenomina_result.get("status", "error"),
						"file_path": prenomina_result.get("file_path", ""),
						"message": prenomina_result.get("message", ""),
						"jornada_filter": prenomina_result.get("jornada_filter") or jornada_context.get("canonical_filter") or "Todas",
					})
					
					# Publish TP approval event
					publish_tp_approval_event(batch_doc, "Aprobado", approver)
					
					# Publish prenomina generation event
					if prenomina_result.get("status") == "success":
						publish_prenomina_generation_event(batch_doc, prenomina_result.get("file_path"))
					
				except Exception as e:
					prenomina_results.append({
						"batch": batch_name,
						"prenomina_status": "error",
						"file_path": "",
						"message": f"Error generando prenomina: {str(e)}"
					})
					frappe.log_error(f"Error generating prenomina for batch {batch_name}: {str(e)}")
			
			return {
				"status": "success" if error_count == 0 else "partial",
				"message": f"{success_count} líneas aprobadas, {error_count} errores",
				"success_count": success_count,
				"error_count": error_count,
				"errors": errors,
				"affected_batches": list(affected_batches),
				"prenomina_results": prenomina_results,
				"approver": approver,
				"jornada_filter": jornada_context.get("canonical_filter") or "Todas",
				"jornada_filter_warning": self._build_jornada_filter_warning(jornada_context),
			}
			
		except Exception as e:
			frappe.log_error(f"Error in bulk TP approval: {str(e)}")
			return {"status": "error", "message": str(e)}

	def _build_jornada_context(self, jornada_filter: str = None) -> Dict[str, Any]:
		canonical = normalize_tipo_jornada(jornada_filter)
		return {
			"canonical_filter": canonical,
			"missing_employee_count": 0,
			"missing_employee_labels": [],
		}

	def _filter_lines_by_jornada(self, lines: List[Dict], jornada_filter: str = None):
		context = self._build_jornada_context(jornada_filter)
		canonical_filter = context["canonical_filter"]
		if not lines:
			return lines, context

		filtered_lines = []
		missing_labels = set()
		employee_cache = {}

		for line in lines:
			emp_key = line.get("matched_employee") or line.get("employee_id")
			if not emp_key:
				filtered_lines.append(line)
				continue

			if emp_key not in employee_cache:
				employee_context = get_payroll_employee_context(emp_key)
				employee_cache[emp_key] = {
					"tipo_jornada": normalize_tipo_jornada(employee_context.get("tipo_jornada")),
					"label": employee_context.get("employee_name") or emp_key,
				}

			employee_info = employee_cache[emp_key]
			tipo_jornada = employee_info.get("tipo_jornada")
			if not tipo_jornada:
				missing_labels.add(str(employee_info.get("label") or emp_key))

			if canonical_filter and tipo_jornada != canonical_filter:
				continue

			filtered_lines.append(line)

		context["missing_employee_labels"] = sorted(missing_labels)
		context["missing_employee_count"] = len(missing_labels)
		return filtered_lines, context

	def _build_jornada_filter_warning(self, jornada_context: Dict[str, Any]) -> str | None:
		missing_count = jornada_context.get("missing_employee_count", 0)
		if not missing_count:
			return None

		canonical_filter = jornada_context.get("canonical_filter")
		base_message = (
			f"{missing_count} empleado(s) no tienen Tipo de Jornada canónico parametrizado en Ficha Empleado."
		)
		if canonical_filter:
			return f"{base_message} No se incluyen cuando filtrás por {canonical_filter}."
		return base_message


# =============================================================================
# Public API Functions
# =============================================================================

@frappe.whitelist()
def get_tp_consolidation(period_filter=None, batch_filter=None, limit=500, jornada_filter=None):
	"""
	API endpoint to get TP tray consolidation data for UI.
	
	Returns consolidated data with executive summary and employee breakdowns.
	"""
	
	enforce_payroll_access("tp_tray")
	service = PayrollTPTrayService()
	return service.consolidate_by_period(
		period_filter=period_filter,
		batch_filter=batch_filter,
		limit=int(limit or 500),
		jornada_filter=jornada_filter,
	)


@frappe.whitelist()
def approve_tp_batch(batch_name, comments=None, jornada_filter=None):
	"""
	API endpoint to approve entire batch for TP and generate prenomina.
	
	Args:
		batch_name: Name of the batch to approve
		comments: Optional approval comments
	"""
	
	enforce_payroll_access("tp_tray")
	service = PayrollTPTrayService()
	return service.bulk_approve_tp(
		batch_filter=batch_name,
		comments=comments,
		jornada_filter=jornada_filter,
	)


@frappe.whitelist()
def approve_tp_employees(employee_ids, comments=None, jornada_filter=None):
	"""
	API endpoint to approve specific employees for TP.
	
	Args:
		employee_ids: JSON string or list of employee IDs
		comments: Optional approval comments
	"""
	
	enforce_payroll_access("tp_tray")
	if isinstance(employee_ids, str):
		employee_ids = frappe.parse_json(employee_ids)
	
	service = PayrollTPTrayService()
	return service.bulk_approve_tp(
		employee_ids=employee_ids,
		comments=comments,
		jornada_filter=jornada_filter,
	)


@frappe.whitelist()
def get_available_periods():
	"""
	API endpoint to get available periods for TP review.
	"""
	
	try:
		enforce_payroll_access("tp_tray")
		
		return {
			"status": "success",
			"periods": [p.nomina_period for p in frappe.db.sql("""
				SELECT DISTINCT pb.nomina_period
				FROM `tabPayroll Import Batch` pb
				INNER JOIN `tabPayroll Import Line` pl ON pl.batch = pb.name
				WHERE pl.tc_status = 'Aprobado'
				AND pb.nomina_period IS NOT NULL
				ORDER BY pb.nomina_period DESC
			""", as_dict=True) if p.nomina_period]
		}
		
	except Exception as e:
		frappe.log_error(f"Error getting available periods: {str(e)}")
		return {"status": "error", "message": str(e), "periods": []}


def get_tp_tray_service() -> PayrollTPTrayService:
	"""Get singleton instance of PayrollTPTrayService."""
	return PayrollTPTrayService()
