import frappe
from frappe.model.document import Document


class SiesaCatalogBase(Document):
	def validate(self):
		if self.code:
			self.code = str(self.code).strip()
		if self.description:
			self.description = str(self.description).strip()

		if not self.code:
			frappe.throw("El código es obligatorio.")

