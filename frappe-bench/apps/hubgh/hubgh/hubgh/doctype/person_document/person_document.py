# Copyright (c) 2026, Antigravity and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from frappe.utils import now


STATUS_WITH_UPLOAD = {"Subido", "Aprobado", "Rechazado"}


class PersonDocument(Document):
	def validate(self):
		self._sync_person_links()
		self._validate_status_rules()
		self._sync_audit_fields()

	def _sync_person_links(self):
		if self.person_type == "Candidato":
			self.person_doctype = "Candidato"
			self.candidate = self.person
		elif self.person_type == "Empleado":
			self.person_doctype = "Ficha Empleado"
			self.employee = self.person

		if self.employee and self.person_type == "Candidato":
			# Conserva trazabilidad cuando aún cuelga del candidato.
			return

	def _validate_status_rules(self):
		if self.status in STATUS_WITH_UPLOAD and not self.file:
			frappe.throw("No puede marcar estado Subido/Aprobado/Rechazado sin archivo.")
		if self.status == "Aprobado" and not self.approved_by:
			self.approved_by = frappe.session.user

	def _sync_audit_fields(self):
		if self.file and not self.uploaded_by:
			self.uploaded_by = frappe.session.user
		if self.file and not self.uploaded_on:
			self.uploaded_on = now()
		if self.status == "Aprobado" and not self.approved_on:
			self.approved_on = now()

