import frappe

from hubgh.hubgh import disciplinary_case_service


@frappe.whitelist()
def get_disciplinary_flow_context(user=None):
	return disciplinary_case_service.get_disciplinary_flow_context(user=user)


@frappe.whitelist()
def get_disciplinary_tray(filters=None):
	return disciplinary_case_service.get_disciplinary_tray(filters=filters)


@frappe.whitelist()
def close_disciplinary_case(case_name, decision, closure_date, closure_summary, suspension_start=None, suspension_end=None):
	return disciplinary_case_service.close_disciplinary_case(
		case_name=case_name,
		decision=decision,
		closure_date=closure_date,
		closure_summary=closure_summary,
		suspension_start=suspension_start,
		suspension_end=suspension_end,
	)


__all__ = [
	"close_disciplinary_case",
	"get_disciplinary_flow_context",
	"get_disciplinary_tray",
]
