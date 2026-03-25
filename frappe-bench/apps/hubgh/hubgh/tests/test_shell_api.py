from frappe.tests.utils import FrappeTestCase

from hubgh.api.access import has_doc_access


class TestHubghShellApi(FrappeTestCase):
	def test_has_doc_access_handles_missing_doc(self):
		self.assertFalse(has_doc_access("Page", "page-does-not-exist", {"Empleado"}))

	def test_has_doc_access_system_manager_short_circuit(self):
		self.assertTrue(has_doc_access("Page", "mi_perfil", {"System Manager"}))
