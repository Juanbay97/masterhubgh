from types import SimpleNamespace
from unittest.mock import patch

from frappe.tests.utils import FrappeTestCase

from hubgh.hubgh.doctype.candidato.candidato import Candidato


class TestCandidato(FrappeTestCase):
	def test_attach_existing_persona_does_not_create_employee(self):
		doc = Candidato.__new__(Candidato)
		doc.persona = None
		doc.numero_documento = "1001"
		doc.user = "candidate@example.com"
		doc.email = "candidate@example.com"

		with patch(
			"hubgh.hubgh.doctype.candidato.candidato.frappe.db.get_value",
			return_value=None,
		), patch("hubgh.hubgh.doctype.candidato.candidato.reconcile_person_identity") as reconcile_mock:
			Candidato._attach_existing_persona(doc)

		self.assertIsNone(doc.persona)
		reconcile_mock.assert_not_called()
