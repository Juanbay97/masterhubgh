# Copyright (c) 2026, Antigravity and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document


class AfectadoDisciplinario(Document):
	def validate(self):
		self._validate_closure_requirements()
		self._validate_suspension_dates()
		self._validate_unique_empleado_per_caso()

	def on_update(self):
		# Lifecycle hook stub — lógica se llenará en Phase 3.
		# En Phase 3 se invocará sync_case_state_from_afectados(self.caso)
		pass

	def _validate_closure_requirements(self):
		"""Al cerrar, requiere decision_final_afectado, fecha_cierre_afectado y resumen_cierre_afectado."""
		if (self.estado or "") != "Cerrado":
			return
		for field in ("decision_final_afectado", "fecha_cierre_afectado", "resumen_cierre_afectado"):
			if not getattr(self, field, None):
				frappe.throw(
					_("Al cerrar un afectado se requiere el campo: {0}.").format(field),
					frappe.ValidationError,
				)

	def _validate_suspension_dates(self):
		"""Si decision_final_afectado es Suspensión, requiere fechas y valida que fin >= inicio."""
		if (self.decision_final_afectado or "") != "Suspensión":
			return
		if not self.fecha_inicio_suspension or not self.fecha_fin_suspension:
			frappe.throw(
				_("La suspensión requiere fecha de inicio y fecha de fin."),
				frappe.ValidationError,
			)
		if self.fecha_fin_suspension < self.fecha_inicio_suspension:
			frappe.throw(
				_("La fecha de fin de suspensión no puede ser anterior a la fecha de inicio."),
				frappe.ValidationError,
			)

	def _validate_unique_empleado_per_caso(self):
		"""Un empleado no puede aparecer dos veces en el mismo caso."""
		if not self.caso or not self.empleado:
			return
		existing = frappe.db.exists(
			"Afectado Disciplinario",
			{"caso": self.caso, "empleado": self.empleado, "name": ("!=", self.name or "")},
		)
		if existing:
			frappe.throw(
				_("El empleado {0} ya está registrado como afectado en este caso ({1}).").format(
					self.empleado, existing
				),
				frappe.ValidationError,
			)
