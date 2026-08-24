# Copyright (c) 2026, Antigravity and contributors
# For license information, please see license.txt

"""
TDD — hubgh-disponibilidad-bandeja-v1, Slice 3, task 3.1.

Page registration: the `bandeja_disponibilidad` desk Page JSON must declare
`standard: "Yes"`, `module: "Hubgh"`, and a `roles[]` array that is exactly
`DISPONIBILIDAD_ROLES` (ADR-9) — no silent role/JSON mismatch like the mold's
`CRUCE_ROLES` vs `seleccion_cruce_contratacion.json` inconsistency (design
artifact ADR-9 "Deliberate divergence from the mold"). The `.py` shim must
be a pure re-export: importing it must yield the SAME whitelisted function
objects `disponibilidad_service` defines, reachable at the dotted path Desk
actually calls (`hubgh.hubgh.page.bandeja_disponibilidad.bandeja_disponibilidad.*`).
"""

import json

import frappe
from frappe.tests.utils import FrappeTestCase

from hubgh.hubgh.disponibilidad_service import (
	DISPONIBILIDAD_ROLES,
	export_disponibilidad_xlsx as service_export,
	list_disponibilidad as service_list,
)
from hubgh.hubgh.page.bandeja_disponibilidad.bandeja_disponibilidad import (
	export_disponibilidad_xlsx as shim_export,
	list_disponibilidad as shim_list,
)


def _load_page_json():
	json_path = frappe.get_app_path(
		"hubgh", "hubgh", "page", "bandeja_disponibilidad", "bandeja_disponibilidad.json"
	)
	with open(json_path, encoding="utf-8") as f:
		return json.load(f)


class TestBandejaDisponibilidadPageRegistration(FrappeTestCase):
	def test_page_is_standard_and_in_hubgh_module(self):
		page_def = _load_page_json()
		self.assertEqual(page_def["doctype"], "Page")
		self.assertEqual(page_def["standard"], "Yes")
		self.assertEqual(page_def["module"], "Hubgh")
		self.assertEqual(page_def["name"], "bandeja_disponibilidad")

	def test_page_roles_exactly_match_disponibilidad_roles(self):
		"""ADR-9: the Page JSON roles[] must be the SAME 6 roles as
		DISPONIBILIDAD_ROLES — not a superset/subset, unlike the mold's
		CRUCE_ROLES/seleccion_cruce_contratacion.json mismatch."""
		page_def = _load_page_json()
		page_roles = {entry["role"] for entry in page_def["roles"]}
		self.assertEqual(page_roles, set(DISPONIBILIDAD_ROLES))


class TestBandejaDisponibilidadPageShim(FrappeTestCase):
	"""The page `.py` module is a pure re-export shim: the whitelisted endpoints
	resolve through `hubgh.hubgh.page.bandeja_disponibilidad.bandeja_disponibilidad.*`
	to the EXACT same function objects `disponibilidad_service` whitelists."""

	def test_shim_reexports_the_exact_same_function_objects(self):
		self.assertIs(shim_list, service_list)
		self.assertIs(shim_export, service_export)

	def test_shim_endpoints_are_whitelisted(self):
		self.assertIn(shim_list, frappe.whitelisted)
		self.assertIn(shim_export, frappe.whitelisted)
