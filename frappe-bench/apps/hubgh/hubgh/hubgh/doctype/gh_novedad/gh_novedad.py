# Copyright (c) 2026, Antigravity and contributors
# For license information, please see license.txt

from frappe.model.document import Document


COLA_GENERAL = "GH-Bandeja General"
COLA_SST = "GH-SST"
COLA_RRLL = "GH-RRLL"


class GHNovedad(Document):
	def validate(self):
		self._set_safe_defaults()
		self._validate_dates()
		self._sync_punto_from_persona()
		self._apply_triage_routing()

	def _set_safe_defaults(self):
		if not self.estado:
			self.estado = "Recibida"
		if not self.cola_origen:
			self.cola_origen = COLA_GENERAL

	def _validate_dates(self):
		if self.fecha_inicio and self.fecha_fin and self.fecha_fin < self.fecha_inicio:
			raise ValueError("La fecha fin no puede ser menor que la fecha inicio")

	def _sync_punto_from_persona(self):
		if self.punto or not self.persona:
			return
		self.punto = self._db_get_value("Ficha Empleado", self.persona, "pdv")

	def _apply_triage_routing(self):
		self.cola_sugerida = self._get_suggested_queue(self.tipo)

		if self.is_new():
			# Toda novedad entra primero a la bandeja general.
			if not self.cola_destino:
				self.cola_destino = COLA_GENERAL
			return

		# En actualizaciones se aplica enrutamiento automático por tipo.
		self.cola_destino = self.cola_sugerida

	def _get_suggested_queue(self, tipo):
		if tipo in {"Suspensión", "Terminación", "Abandono de Cargo"}:
			return COLA_RRLL
		return COLA_GENERAL

	def _db_get_value(self, doctype, name, fieldname):
		# Aislado para pruebas y para mantener este controlador simple.
		import frappe

		return frappe.db.get_value(doctype, name, fieldname)
