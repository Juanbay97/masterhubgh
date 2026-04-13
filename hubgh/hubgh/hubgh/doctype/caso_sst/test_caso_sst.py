# Copyright (c) 2026, Antigravity and Contributors
# See license.txt

import frappe
from frappe.tests.utils import FrappeTestCase


class TestCasoSST(FrappeTestCase):
	def test_validate_blocks_new_legacy_case_creation(self):
		doc = frappe.get_doc({"doctype": "Caso SST"})

		with self.assertRaises(frappe.ValidationError):
			doc.validate()

	def test_validate_allows_existing_legacy_case_updates(self):
		doc = frappe.get_doc({"doctype": "Caso SST"})
		doc.is_new = lambda: False

		doc.validate()
