# Copyright (c) 2026, Antigravity and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from frappe.utils import now_datetime


VALID_TRANSITIONS: dict[str, set[str]] = {
	"draft": {"ingesting", "failed", "archived"},
	"ingesting": {"parsed", "failed"},
	# Desde "parsed" se puede ir directo a "exported" (revisión es
	# opcional en v1) o pasar primero por "reviewing".
	"parsed": {"reviewing", "exported", "failed"},
	"reviewing": {"exported", "failed"},
	"exported": {"reviewing", "archived"},
	"archived": set(),
	"failed": {"draft", "archived"},
}


class PayrollRun(Document):
	def before_insert(self) -> None:
		if not self.owner_user:
			self.owner_user = frappe.session.user
		if not self.started_at:
			self.started_at = now_datetime()

	def validate(self) -> None:
		self._validate_period()
		self._validate_transition()

	def _validate_period(self) -> None:
		if not self.period_year or self.period_year < 2020 or self.period_year > 2099:
			frappe.throw("Año fuera de rango razonable.")
		try:
			month = int(self.period_month or 0)
		except (TypeError, ValueError):
			frappe.throw("Mes inválido.")
		if month < 1 or month > 12:
			frappe.throw("Mes fuera de rango (1-12).")

	def _validate_transition(self) -> None:
		if self.is_new():
			return
		previous = (self.get_doc_before_save() or {}).get("status")
		current = self.status
		if previous == current or not previous:
			return
		allowed = VALID_TRANSITIONS.get(previous, set())
		if current not in allowed:
			frappe.throw(
				f"Transición de estado inválida: {previous} → {current}. "
				f"Permitidas: {sorted(allowed) or '∅'}"
			)
		if current in {"exported", "archived"} and not self.closed_at:
			self.closed_at = now_datetime()
