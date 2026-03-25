import json

import frappe
from frappe.model.document import Document

from hubgh.hubgh.people_ops_flags import resolve_backbone_mode


ALLOWED_AREAS = {"seleccion", "rrll", "sst", "bienestar", "documental", "operacion", "nomina"}
ALLOWED_SENSITIVITY = {"operational", "documental", "disciplinary", "clinical", "financial"}


class PeopleOpsEvent(Document):
	def validate(self):
		mode = resolve_backbone_mode(self.area)
		warnings = []
		self.area = str(self.area or "operacion").strip().lower()
		if self.area not in ALLOWED_AREAS:
			if mode == "enforce":
				frappe.throw("Área People Ops no soportada para este evento.")
			self.area = "operacion"
			warnings.append("area_normalized")

		self.sensitivity = str(self.sensitivity or "operational").strip().lower()
		if self.sensitivity not in ALLOWED_SENSITIVITY:
			if mode == "enforce":
				frappe.throw("Sensibilidad no soportada para People Ops Event.")
			self.sensitivity = "operational"
			warnings.append("sensitivity_normalized")

		self.taxonomy = str(self.taxonomy or "").strip().lower()
		if not self.taxonomy.startswith(f"{self.area}."):
			if mode == "enforce":
				frappe.throw("Taxonomía inválida para el área canónica del evento.")
			self.taxonomy = f"{self.area}.{self.taxonomy.split('.', 1)[-1] if self.taxonomy else 'evento'}"
			warnings.append("taxonomy_normalized")

		if self.refs_json:
			try:
				json.loads(self.refs_json)
			except Exception as exc:
				frappe.throw(f"refs_json inválido: {exc}")

		if warnings and not self.warning_message:
			self.warning_message = "; ".join(warnings)
