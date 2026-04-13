import frappe
from frappe.model.document import Document

from hubgh.hubgh.payroll_employee_compat import (
	build_employee_parametrization_message,
	get_payroll_employee_context,
)


class PayrollImportLine(Document):
	def validate(self):
		if not self.batch:
			frappe.throw("Debe asociar la línea a un lote de importación.")
		if not self.run_id and self.batch:
			self.run_id = frappe.db.get_value("Payroll Import Batch", self.batch, "run_id")
			
		# Validate employee exists
		if self.employee_id:
			self.validate_employee()
			
		# Validate novedad type
		if self.novedad_type:
			self.validate_novedad_type()
			
	def validate_employee(self):
		"""Validate that employee exists in system"""
		context = get_payroll_employee_context(self.employee_id)
		employee = context.get("employee")

		if employee:
			self.matched_employee = employee.get("name")
			self.matched_employee_doctype = employee.get("doctype")
			if not self.employee_name:
				self.employee_name = employee.get("employee_name")
			param_warning = build_employee_parametrization_message(
				context,
				required_fields=["contrato", "salary", "pdv"],
			)
			if param_warning:
				self.rule_notes = param_warning
		else:
			self.matched_employee = None
			self.matched_employee_doctype = None
			self.validation_errors = (
				f"No se encontro una Ficha Empleado para el identificador {self.employee_id}. "
				"Verifique cedula, documento o vinculacion de contrato antes de continuar."
			)
			if self.status == "Pendiente" and not self.raw_payload_json:
				self.status = "Error"
				
	def validate_novedad_type(self):
		"""Validate that novedad type exists in catalog"""
		novedad = frappe.db.get_value("Payroll Novedad Type", 
			self.novedad_type, 
			["name", "requiere_soporte", "sensitivity"]
		)
		
		if not novedad:
			message = f"Tipo de novedad {self.novedad_type} no existe en catálogo"
			if self.source_concept_code:
				message = f"{message}. La novedad exógena queda almacenada para revisión y homologación."
			self.validation_errors = message
			if self.status == "Pendiente" and not self.source_concept_code:
				self.status = "Error"
		else:
			# Check if support is required for certain types
			if novedad[1] and self.quantity and float(self.quantity) >= 3:
				# Flag for support document validation (will be implemented in Sprint 3)
				if not self.rule_notes:
					self.rule_notes = "Requiere documento de soporte"
					
	def before_save(self):
		if not self.run_id and self.batch:
			self.run_id = frappe.db.get_value("Payroll Import Batch", self.batch, "run_id")
		if self.matched_employee and not self.matched_employee_doctype:
			matched = get_payroll_employee_context(self.matched_employee).get("employee")
			if matched:
				self.matched_employee_doctype = matched.get("doctype")

		# Auto-set tc_status and tp_status to Pendiente if not set
		if not self.tc_status:
			self.tc_status = "Pendiente"
		if not self.tp_status:
			self.tp_status = "Pendiente"
