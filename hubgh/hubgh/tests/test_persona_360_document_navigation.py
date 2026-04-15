from pathlib import Path
from unittest import TestCase


class TestPersona360DocumentNavigation(TestCase):
	def test_view_documents_action_routes_to_workspace(self):
		js_path = Path(__file__).resolve().parents[1] / "hubgh" / "page" / "persona_360" / "persona_360.js"
		content = js_path.read_text(encoding="utf-8")

		self.assertIn("function navigate_to_document_workspace(action, employee)", content)
		self.assertIn("frappe.route_options = Object.assign({ employee: employee, open_drawer: 1 }, (action && action.prefill) || {});", content)
		self.assertIn("navigate_to_document_workspace(action, emp_id);", content)
		self.assertNotIn("if (action.key === 'view_documents') {\n\t\topen_document_drawer(page, emp_id);", content)
