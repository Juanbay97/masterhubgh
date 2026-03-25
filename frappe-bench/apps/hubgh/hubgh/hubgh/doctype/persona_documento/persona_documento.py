# Copyright (c) 2026, Antigravity and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from frappe.utils import now


class PersonaDocumento(Document):
	def validate(self):
		self._validate_motivo_rechazo()
		self._sync_revision_metadata()
		self._sync_estado_por_archivo()

	def _validate_motivo_rechazo(self):
		if self.estado_documento == "Rechazado" and not self.motivo_rechazo:
			frappe.throw("El motivo de rechazo es obligatorio cuando el documento es Rechazado.")

	def _sync_revision_metadata(self):
		if self.estado_documento in {"En Revision", "Aprobado", "Rechazado"}:
			if not self.fecha_ultima_revision:
				self.fecha_ultima_revision = now()
			if self.estado_documento in {"Aprobado", "Rechazado"} and not self.revisado_por:
				self.revisado_por = frappe.session.user

	def _sync_estado_por_archivo(self):
		if self.archivo and self.estado_documento in {"Pendiente", "Rechazado"}:
			self.estado_documento = "En Revision"
			self.motivo_rechazo = None
