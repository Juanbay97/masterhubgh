"""
Payroll Liquidation Service - End-of-period liquidation calculations.

Handles:
- Vacaciones (Vacations)
- Cesantías (Severance)
- Intereses Cesantías (Severance Interest)
- Prima de Servicios (Service Bonus)

Sprint 6: Core liquidation calculations for period-end settlements.
"""

import frappe
from frappe.utils import now_datetime, date_diff, flt
from typing import Dict, Any, List

from hubgh.hubgh.payroll_employee_compat import (
	build_employee_parametrization_message,
	get_payroll_employee_context,
)


class PayrollLiquidationService:
	"""Service for payroll liquidation calculations."""

	TYPE_VACACIONES = "VACACIONES"
	TYPE_CESANTIAS = "CESANTIAS"
	TYPE_INTERESES = "INTERESES_CESANTIAS"
	TYPE_PRIMA = "PRIMA_SERVICIOS"

	def __init__(self):
		self.base_liquidation_days = 360
		self._employee_context_cache = {}
		self._salary_context_cache = {}

	def calculate_vacaciones(self, employee_id: str, start_date: str, end_date: str) -> Dict[str, Any]:
		salary = self.get_employee_salary(employee_id)
		days = date_diff(end_date, start_date) + 1
		vacation_days = (days / 30) * 1.25
		vacation_pay = (salary / 30) * vacation_days
		return {
			"employee_id": employee_id,
			"type": self.TYPE_VACACIONES,
			"period_start": start_date,
			"period_end": end_date,
			"days_worked": days,
			"vacation_days_due": vacation_days,
			"base_salary": salary,
			"vacation_pay": flt(vacation_pay, 2),
			"formula": f"({salary}/30) * {vacation_days:.2f}",
		}

	def calculate_cesantias(self, employee_id: str, start_date: str, end_date: str) -> Dict[str, Any]:
		salary = self.get_employee_salary(employee_id)
		days = date_diff(end_date, start_date) + 1
		cesantias = (salary * 12) / 360 * days
		return {
			"employee_id": employee_id,
			"type": self.TYPE_CESANTIAS,
			"period_start": start_date,
			"period_end": end_date,
			"days_worked": days,
			"base_salary": salary,
			"cesantias": flt(cesantias, 2),
			"formula": f"({salary} * 12) / 360 * {days}",
		}

	def calculate_intereses_cesantias(self, employee_id: str, start_date: str, end_date: str) -> Dict[str, Any]:
		cesantias_result = self.calculate_cesantias(employee_id, start_date, end_date)
		cesantias = cesantias_result["cesantias"]
		days = cesantias_result["days_worked"]
		intereses = (cesantias * days * 0.12) / 360
		return {
			"employee_id": employee_id,
			"type": self.TYPE_INTERESES,
			"period_start": start_date,
			"period_end": end_date,
			"days_worked": days,
			"cesantias_base": cesantias,
			"interes_rate": 0.12,
			"intereses": flt(intereses, 2),
			"formula": f"{cesantias} * {days} * 0.12 / 360",
		}

	def calculate_prima_servicios(self, employee_id: str, start_date: str, end_date: str) -> Dict[str, Any]:
		salary = self.get_employee_salary(employee_id)
		days = date_diff(end_date, start_date) + 1
		prima = (salary * 12) / 360 * days
		return {
			"employee_id": employee_id,
			"type": self.TYPE_PRIMA,
			"period_start": start_date,
			"period_end": end_date,
			"days_worked": days,
			"base_salary": salary,
			"prima": flt(prima, 2),
			"formula": f"({salary} * 12) / 360 * {days}",
		}

	def calculate_all_liquidations(self, employee_id: str, start_date: str, end_date: str) -> Dict[str, Any]:
		vacaciones = self.calculate_vacaciones(employee_id, start_date, end_date)
		cesantias = self.calculate_cesantias(employee_id, start_date, end_date)
		intereses = self.calculate_intereses_cesantias(employee_id, start_date, end_date)
		prima = self.calculate_prima_servicios(employee_id, start_date, end_date)
		total = (
			vacaciones["vacation_pay"]
			+ cesantias["cesantias"]
			+ intereses["intereses"]
			+ prima["prima"]
		)
		employee_context = self._get_employee_context(employee_id)
		salary_context = self._get_salary_context(employee_id)
		return {
			"employee_id": employee_context.get("employee_id") or employee_id,
			"employee_name": employee_context.get("employee_name") or employee_id,
			"period_start": start_date,
			"period_end": end_date,
			"calculated_on": now_datetime(),
			"salary_source": salary_context.get("source"),
			"parameterization_warnings": salary_context.get("warnings") or [],
			"vacaciones": vacaciones,
			"cesantias": cesantias,
			"intereses_cesantias": intereses,
			"prima_servicios": prima,
			"total_liquidacion": flt(total, 2),
		}

	def get_employee_salary(self, employee_id: str) -> float:
		return flt(self._get_salary_context(employee_id).get("salary") or 0)

	def _get_employee_context(self, employee_id: str) -> Dict[str, Any]:
		if employee_id not in self._employee_context_cache:
			self._employee_context_cache[employee_id] = get_payroll_employee_context(employee_id)
		return self._employee_context_cache[employee_id]

	def _get_salary_context(self, employee_id: str) -> Dict[str, Any]:
		if employee_id in self._salary_context_cache:
			return self._salary_context_cache[employee_id]

		employee_context = self._get_employee_context(employee_id)
		warnings = []
		salary = flt(employee_context.get("salary") or 0)
		source = "Contrato" if salary else None

		if not salary:
			legacy_salary = frappe.db.get_value(
				"Salary Slip",
				{"employee": employee_id, "docstatus": 1},
				"base_salary",
				order_by="start_date desc",
			)
			if legacy_salary:
				salary = flt(legacy_salary)
				source = "Salary Slip"

		param_warning = build_employee_parametrization_message(employee_context, ["contrato", "salary"])
		if param_warning:
			warnings.append(param_warning)

		if not salary:
			salary = 1500000
			source = source or "fallback"
			warnings.append(
				"No se encontro salario en Contrato ni Salary Slip. Se usa 1500000 como base temporal para no bloquear el Desk."
			)

		result = {"salary": salary, "source": source, "warnings": warnings}
		self._salary_context_cache[employee_id] = result
		return result


@frappe.whitelist()
def get_employee_liquidations(employee_id: str, start_date: str, end_date: str) -> Dict[str, Any]:
    """
    API endpoint to get liquidation calculations for an employee.
    """
    service = PayrollLiquidationService()
    return service.calculate_all_liquidations(employee_id, start_date, end_date)


@frappe.whitelist()
def get_period_liquidations(period: str) -> List[Dict[str, Any]]:
	"""Get liquidations for all employees in a period."""
	period_doc = frappe.get_doc("Payroll Period Config", period)
	employee_ids = set(
		frappe.get_all(
			"Contrato",
			filters={
				"docstatus": ["<", 2],
				"fecha_ingreso": ["<=", period_doc.end_date],
			},
			or_filters={
				"fecha_fin_contrato": ["is", "not set"],
				"estado_contrato": ["in", ["Activo", "Pendiente", "Retirado"]],
			},
			pluck="empleado",
		)
	)
	legacy_employees = frappe.get_all(
		"Salary Slip",
		filters={
			"start_date": [">=", period_doc.start_date],
			"end_date": ["<=", period_doc.end_date],
			"docstatus": 1,
		},
		distinct=True,
		pluck="employee",
	)
	for employee_id in legacy_employees:
		resolved = get_payroll_employee_context(employee_id)
		employee_ids.add(resolved.get("employee_id") or employee_id)

	service = PayrollLiquidationService()
	results = []
	for emp in sorted(employee_ids):
		if not emp:
			continue
		results.append(service.calculate_all_liquidations(emp, period_doc.start_date, period_doc.end_date))
	return results


@frappe.whitelist()
def generate_liquidation_report(period: str, output_format: str = "json") -> Dict[str, Any]:
	"""Generate comprehensive liquidation report for period."""
	liquidations = get_period_liquidations(period)
	totals = {
		"vacaciones": sum(l["vacaciones"]["vacation_pay"] for l in liquidations),
		"cesantias": sum(l["cesantias"]["cesantias"] for l in liquidations),
		"intereses": sum(l["intereses_cesantias"]["intereses"] for l in liquidations),
		"prima": sum(l["prima_servicios"]["prima"] for l in liquidations),
		"total": sum(l["total_liquidacion"] for l in liquidations),
	}
	return {
		"period": period,
		"employee_count": len(liquidations),
		"liquidations": liquidations,
		"totals": totals,
		"generated_on": now_datetime(),
	}
