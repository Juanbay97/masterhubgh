from uuid import uuid4

import frappe
from frappe.tests.utils import FrappeTestCase

from hubgh.api import feed


class TestHubghFeedApi(FrappeTestCase):
	def setUp(self):
		super().setUp()
		self._original_user = frappe.session.user
		frappe.set_user("Administrator")
		self._created_posts = []

	def tearDown(self):
		for post_name in self._created_posts:
			if frappe.db.exists("GH Post", post_name):
				frappe.delete_doc("GH Post", post_name, force=1, ignore_permissions=True)
		frappe.set_user(self._original_user)
		super().tearDown()

	def test_get_posts_returns_empty_without_demo_fallback(self):
		unique_area = f"AREA-EMPTY-{uuid4().hex[:8]}"
		rows = feed.get_posts(limit=5, area=unique_area)
		self.assertEqual(rows, [])

	def test_get_posts_returns_real_post_fields(self):
		unique_area = f"AREA-POST-{uuid4().hex[:8]}"
		post = frappe.get_doc(
			{
				"doctype": "GH Post",
				"titulo": f"Post prueba {unique_area}",
				"cuerpo_corto": "Contenido real de prueba",
				"area": unique_area,
				"publicado": 1,
				"audiencia_roles": "System Manager",
			}
		).insert(ignore_permissions=True)
		self._created_posts.append(post.name)

		rows = feed.get_posts(limit=5, area=unique_area)
		self.assertEqual(len(rows), 1)
		self.assertEqual(rows[0]["name"], post.name)
		self.assertEqual(rows[0]["titulo"], f"Post prueba {unique_area}")
		self.assertIn("fecha_publicacion", rows[0])

	def test_get_home_feed_returns_phase2_contract(self):
		payload = feed.get_home_feed(limit=3)

		self.assertIn("feed", payload)
		self.assertIn("widgets", payload)
		self.assertIn("meta", payload)

		self.assertIn("posts", payload["feed"])
		self.assertIn("empty", payload["feed"])

		widgets = payload["widgets"]
		self.assertIn("alerts", widgets)
		self.assertIn("birthdays", widgets)
		self.assertIn("lms_pending", widgets)
		self.assertIn("profile_completion", widgets)

		self.assertIsInstance(widgets["alerts"].get("items", []), list)
		self.assertIsInstance(widgets["birthdays"].get("items", []), list)
		self.assertIsInstance(widgets["lms_pending"].get("items", []), list)

