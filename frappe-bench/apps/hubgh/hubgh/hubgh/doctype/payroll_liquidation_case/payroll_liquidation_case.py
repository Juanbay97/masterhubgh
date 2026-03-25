import frappe
from frappe.model.document import Document
from frappe.utils import now_datetime, getdate


class PayrollLiquidationCase(Document):
	"""Payroll Liquidation Case controller."""

	def before_insert(self):
		"""Set creation timestamp and calculate liquidation."""
		self.created_on = now_datetime()
		self.set_employee_context()
		if self.employee and self.period_start and self.period_end:
			self.calculate_liquidation()

	def validate(self):
		"""Validate and auto-close if all checks are done."""
		self.set_employee_context()
		self.update_check_metadata()
		self.check_auto_close()

	def set_employee_context(self):
		"""Keep employee display data aligned with Ficha Empleado."""
		if not self.employee:
			return

		emp = frappe.get_doc("Ficha Empleado", self.employee)
		self.employee_name = " ".join(
			part for part in [emp.get("nombres"), emp.get("apellidos")] if part
		) or emp.name

	def calculate_liquidation(self):
		"""Calculate all liquidation amounts."""
		from hubgh.hubgh.payroll_liquidation_service import PayrollLiquidationService

		service = PayrollLiquidationService()
		result = service.calculate_all_liquidations(
			self.employee,
			str(self.period_start),
			str(self.period_end)
		)

		self.vacaciones_amount = result["vacaciones"]["vacation_pay"]
		self.cesantias_amount = result["cesantias"]["cesantias"]
		self.intereses_cesantias_amount = result["intereses_cesantias"]["intereses"]
		self.prima_amount = result["prima_servicios"]["prima"]
		self.total_liquidacion = result["total_liquidacion"]
		self.days_worked = result["vacaciones"]["days_worked"]
		self.base_salary = result["vacaciones"]["base_salary"]

		import json
		self.calculation_detail = json.dumps(result, default=str)

	def update_check_metadata(self):
		"""Track who and when each check was done."""
		checks = ["contabilidad", "sst", "rrll", "nomina"]
		for check in checks:
			check_field = f"check_{check}"
			by_field = f"check_{check}_by"
			date_field = f"check_{check}_date"

			if self.get(check_field) and not self.get(by_field):
				self.set(by_field, frappe.session.user)
				self.set(date_field, now_datetime())

	def check_auto_close(self):
		"""Auto-close case when all checks are marked."""
		all_checks = all([
			self.check_contabilidad,
			self.check_sst,
			self.check_rrll,
			self.check_nomina
		])

		if all_checks and self.status != "Cerrado":
			self.status = "Cerrado"

	def on_update(self):
		"""Publish event on status change."""
		if self.has_value_changed("status") and self.status == "Cerrado":
			self.publish_liquidation_event()

	def publish_liquidation_event(self):
		"""Publish People Ops Event for closed liquidation."""
		try:
			from hubgh.hubgh.payroll_publishers import publish_liquidation_event
			publish_liquidation_event(self)
		except ImportError:
			pass


@frappe.whitelist()
def create_liquidation_case(employee, retirement_date=None):
	"""
	API to create a liquidation case for an employee.
	Called when employee status changes to Retirado.
	"""
	# Check if case already exists
	existing = frappe.db.exists("Payroll Liquidation Case", {
		"employee": employee,
		"status": ["not in", ["Cancelado"]]
	})
	if existing:
		return frappe.get_doc("Payroll Liquidation Case", existing)

	# Get employee details
	emp = frappe.get_doc("Ficha Empleado", employee)
	hire_date = emp.get("fecha_ingreso") or emp.get("creation")
	ret_date = retirement_date or getdate()

	doc = frappe.get_doc({
		"doctype": "Payroll Liquidation Case",
		"employee": employee,
		"retirement_date": ret_date,
		"period_start": hire_date,
		"period_end": ret_date,
		"status": "Abierto"
	})
	doc.insert(ignore_permissions=True)
	frappe.db.commit()

	return doc
