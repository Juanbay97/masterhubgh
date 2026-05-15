# Copyright (c) 2026, Antigravity and contributors
# For license information, please see license.txt

import frappe
from frappe.tests.utils import FrappeTestCase


class TestCorreccionDatosCandidato(FrappeTestCase):
	def test_doctype_exists(self):
		self.assertTrue(frappe.db.exists("DocType", "Correccion Datos Candidato"))
