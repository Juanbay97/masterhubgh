import frappe
from datetime import datetime, timedelta
from frappe.utils import add_months, getdate, nowdate


def get_payroll_block(employee_id):
	"""
	Get payroll data block for Persona 360 integration.
	
	Returns:
		- Last 12 months novelty summary (grouped by type, with counts and totals)
		- Vacation days remaining
		- Active incapacidades count
		- Pending deductions summary
	"""
	if not employee_id:
		return {}
	
	# Check if employee exists
	if not frappe.db.exists("Ficha Empleado", employee_id):
		return {}
	
	# Get date range for last 12 months
	today = getdate(nowdate())
	twelve_months_ago = add_months(today, -12)
	
	if not _payroll_doctypes_ready():
		return {
			"employee_id": employee_id,
			"period_from": twelve_months_ago,
			"period_to": today,
			"novelty_summary": {},
			"vacation_balance": _empty_vacation_balance(),
			"active_incapacidades": _empty_incapacidades(),
			"pending_deductions": _empty_deductions(),
			"generated_at": nowdate(),
			"payroll_ready": False,
			"note": "Módulo de nómina pendiente de migración en este sitio"
		}

	# Get payroll data
	novelty_summary = _get_novelty_summary(employee_id, twelve_months_ago, today)
	vacation_balance = _get_vacation_balance(employee_id)
	active_incapacidades = _get_active_incapacidades_count(employee_id)
	pending_deductions = _get_pending_deductions_summary(employee_id)
	
	return {
		"employee_id": employee_id,
		"period_from": twelve_months_ago,
		"period_to": today,
		"novelty_summary": novelty_summary,
		"vacation_balance": vacation_balance,
		"active_incapacidades": active_incapacidades,
		"pending_deductions": pending_deductions,
		"generated_at": nowdate(),
		"payroll_ready": True
	}


def _payroll_doctypes_ready():
	"""Return True only if payroll DocTypes are available in current site DB."""
	try:
		return bool(frappe.db.exists("DocType", "Payroll Import Line"))
	except Exception:
		return False


def _empty_vacation_balance():
	return {
		"days_remaining": 0,
		"earned_days": 0,
		"consumed_days": 0,
		"years_worked": 0,
		"calculation_note": "Sin datos de nómina aún"
	}


def _empty_incapacidades():
	return {
		"sst_active": 0,
		"payroll_recent": 0,
		"total_estimated": 0,
		"note": "Sin datos de nómina aún"
	}


def _empty_deductions():
	return {
		"by_type": {},
		"total_amount": 0,
		"total_items": 0,
		"note": "Sin datos de nómina aún"
	}


def _get_novelty_summary(employee_id, date_from, date_to):
	"""Get last 12 months novelty summary grouped by type with counts and totals."""
	
	# Query PayrollImportLine records for the employee in the period
	try:
		lines = frappe.get_all(
		"Payroll Import Line",
		filters={
			"employee_id": employee_id,
			"novedad_date": ["between", [date_from, date_to]],
			"status": ["in", ["Pendiente", "Válido", "Procesado"]]
		},
		fields=[
			"novedad_type",
			"quantity", 
			"novedad_date",
			"status",
			"batch"
		],
		order_by="novedad_date desc"
	)
	except Exception:
		return {}
	
	# Group by novelty type
	summary = {}
	for line in lines:
		novelty_type = line.novedad_type or "Sin clasificar"
		
		if novelty_type not in summary:
			summary[novelty_type] = {
				"count": 0,
				"total_quantity": 0,
				"last_date": None,
				"status_breakdown": {"Pendiente": 0, "Revisado": 0, "Aprobado": 0}
			}
		
		summary[novelty_type]["count"] += 1
		summary[novelty_type]["total_quantity"] += (line.quantity or 0)
		if line.status in summary[novelty_type]["status_breakdown"]:
			summary[novelty_type]["status_breakdown"][line.status] += 1
		
		# Track most recent date
		if not summary[novelty_type]["last_date"] or line.novedad_date > summary[novelty_type]["last_date"]:
			summary[novelty_type]["last_date"] = line.novedad_date
	
	return summary


def _get_vacation_balance(employee_id):
	"""Calculate vacation days remaining for the employee."""
	
	# Get employee info
	employee = frappe.get_doc("Ficha Empleado", employee_id)
	if not employee.fecha_ingreso:
		return {"days_remaining": 0, "calculation_note": "Fecha de ingreso no definida"}
	
	# Basic vacation calculation (15 days per year in Colombia)
	years_worked = (getdate(nowdate()) - getdate(employee.fecha_ingreso)).days / 365.25
	earned_days = years_worked * 15
	
	# Get consumed vacation days from payroll records
	try:
		consumed_lines = frappe.get_all(
		"Payroll Import Line",
		filters={
			"employee_id": employee_id,
			"novedad_type": ["in", ["VACACIONES", "VAC", "Vacaciones"]],
			"status": ["in", ["Válido", "Procesado"]]
		},
		fields=["quantity"],
	)
	except Exception:
		consumed_lines = []
	
	consumed_days = sum((line.quantity or 0) for line in consumed_lines)
	remaining_days = max(0, earned_days - consumed_days)
	
	return {
		"days_remaining": round(remaining_days, 1),
		"earned_days": round(earned_days, 1),
		"consumed_days": consumed_days,
		"years_worked": round(years_worked, 1),
		"calculation_note": f"15 días/año × {round(years_worked, 1)} años - {consumed_days} días tomados"
	}


def _get_active_incapacidades_count(employee_id):
	"""Count active incapacidades for the employee."""
	
	# Check both Novedad SST and payroll imports for incapacidades
	sst_count = frappe.db.count(
		"Novedad SST",
		filters={
			"empleado": employee_id,
			"tipo_novedad": ["in", ["Incapacidad", "Incapacidad por enfermedad general"]],
			"estado": ["in", ["Abierta", "En seguimiento", "Abierto"]]
		}
	)
	
	# Count from payroll imports (recent 30 days)
	thirty_days_ago = add_months(getdate(nowdate()), -1)
	try:
		payroll_count = frappe.db.count(
		"Payroll Import Line",
		filters={
			"employee_id": employee_id,
			"novedad_type": ["in", ["INC-EG", "INC-AT", "INCAPACIDAD", "Incapacidad"]],
			"novedad_date": [">=", thirty_days_ago],
			"status": ["in", ["Pendiente", "Válido", "Procesado"]]
		}
	)
	except Exception:
		payroll_count = 0
	
	return {
		"sst_active": sst_count,
		"payroll_recent": payroll_count,
		"total_estimated": sst_count + payroll_count,
		"note": "SST activas + importaciones de nómina (últimos 30 días)"
	}


def _get_pending_deductions_summary(employee_id):
	"""Get summary of pending deductions for the employee."""
	
	# Get pending deduction-type novelties
	try:
		deduction_lines = frappe.get_all(
		"Payroll Import Line",
		filters={
			"employee_id": employee_id,
			"novedad_type": ["in", ["PAYFLOW", "LIBRANZAS", "DESCUENTO", "DESC-SALUD", "DESC-PENSION"]],
			"status": ["in", ["Pendiente", "Válido"]]
		},
		fields=["novedad_type", "quantity", "novedad_date", "batch"],
		order_by="novedad_date desc"
	)
	except Exception:
		deduction_lines = []
	
	# Group by deduction type
	summary = {}
	total_amount = 0
	
	for line in deduction_lines:
		deduction_type = line.novedad_type or "Sin clasificar"
		amount = line.quantity or 0
		
		if deduction_type not in summary:
			summary[deduction_type] = {
				"count": 0,
				"total_amount": 0,
				"last_date": None
			}
		
		summary[deduction_type]["count"] += 1
		summary[deduction_type]["total_amount"] += amount
		total_amount += amount
		
		if not summary[deduction_type]["last_date"] or line.novedad_date > summary[deduction_type]["last_date"]:
			summary[deduction_type]["last_date"] = line.novedad_date
	
	return {
		"by_type": summary,
		"total_amount": total_amount,
		"total_items": len(deduction_lines),
		"note": "Deducciones pendientes de aprobación final"
	}


@frappe.whitelist()
def get_employee_payroll_data(employee_id):
	"""API endpoint for Persona 360 payroll block."""
	return get_payroll_block(employee_id)
