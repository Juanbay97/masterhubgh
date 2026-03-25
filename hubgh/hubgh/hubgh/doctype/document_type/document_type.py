# Copyright (c) 2026, Antigravity and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from hubgh.hubgh.role_matrix import AREA_ROLE_ALIASES


class DocumentType(Document):
	def validate(self):
		self._normalize_flags()
		self._validate_allowed_areas()

	def _normalize_flags(self):
		if self.is_optional:
			self.is_required_for_hiring = 0

	def _validate_allowed_areas(self):
		seen = set()
		for row in self.allowed_areas or []:
			if not row.area_role:
				continue
			if row.area_role in seen:
				frappe.throw(f"Área duplicada en Allowed Areas: {row.area_role}")
			seen.add(row.area_role)


def get_effective_area_roles(area_role):
	return sorted(AREA_ROLE_ALIASES.get(area_role, {area_role}))
