import frappe

from hubgh.hubgh import employee_retirement_service


@frappe.whitelist()
def get_retirement_flow_context(user=None):
	return employee_retirement_service.get_retirement_flow_context(user=user)


@frappe.whitelist()
def get_employee_retirement_snapshot(employee):
	return employee_retirement_service.get_employee_retirement_snapshot(employee=employee)


@frappe.whitelist()
def get_retirement_tray(filters=None):
	return employee_retirement_service.get_retirement_tray(filters=filters)


@frappe.whitelist()
def submit_employee_retirement(employee, last_worked_date, reason, closure_date=None, closure_summary=None):
	return employee_retirement_service.submit_employee_retirement(
		employee=employee,
		last_worked_date=last_worked_date,
		reason=reason,
		closure_date=closure_date,
		closure_summary=closure_summary,
	)


__all__ = [
	"get_employee_retirement_snapshot",
	"get_retirement_flow_context",
	"get_retirement_tray",
	"submit_employee_retirement",
]
