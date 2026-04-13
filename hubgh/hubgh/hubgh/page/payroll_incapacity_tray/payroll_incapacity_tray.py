import frappe
from frappe.utils import now_datetime

from hubgh.hubgh.payroll_incapacity_tray import get_payroll_incapacity_tray_service
from hubgh.hubgh.payroll_permissions import enforce_payroll_access


@frappe.whitelist()
def get_page_data(search=None, status=None, limit=200):
	try:
		enforce_payroll_access("tp_tray")
		service = get_payroll_incapacity_tray_service()
		result = service.get_tray_data(search=search, status=status, limit=limit)
		result.setdefault("contract_version", "nomina-incapacidades-v1")
		result["traceability"] = {
			"stage": "payroll_incapacity_tray",
			"source": "Novedad SST",
			"generated_at": now_datetime().isoformat(),
			"filters": {"search": search, "status": status, "limit": limit},
		}
		return result
	except Exception as exc:
		frappe.log_error(f"Error loading payroll incapacity tray: {exc}")
		return {"status": "error", "message": str(exc), "items": [], "summary": {}}
