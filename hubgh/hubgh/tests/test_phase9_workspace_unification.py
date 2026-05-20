import json
import os
from unittest.mock import patch

import frappe
from frappe.tests.utils import FrappeTestCase

from hubgh.access_profiles import WORKSPACE_ROLE_MAP, apply_workspace_role_matrix


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _workspace_json_path(folder, filename):
	"""Return the absolute path to a workspace fixture JSON."""
	base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
	return os.path.join(base, "hubgh", "workspace", folder, filename)


# ---------------------------------------------------------------------------
# Phase 9 Workspace Role Unification Tests
# ---------------------------------------------------------------------------

class TestPhase9WorkspaceUnification(FrappeTestCase):

	# --- T-1.2: WORKSPACE_ROLE_MAP completeness --------------------------------

	def test_workspace_role_map_has_sst(self):
		"""R2 — SST must be present in WORKSPACE_ROLE_MAP."""
		self.assertIn("SST", WORKSPACE_ROLE_MAP)

	# --- T-1.3: Mi Perfil out-of-matrix roles preserved in the map -----------

	def test_workspace_role_map_mi_perfil_preserves_out_of_matrix(self):
		"""R5 — LMS Student and Employee must be in WORKSPACE_ROLE_MAP['Mi Perfil']."""
		self.assertTrue(
			{"LMS Student", "Employee"}.issubset(set(WORKSPACE_ROLE_MAP["Mi Perfil"]))
		)

	# --- T-1.4: JSON roles match WORKSPACE_ROLE_MAP ---------------------------

	def _load_json_roles(self, folder, filename):
		"""Load role names from a workspace JSON fixture."""
		path = _workspace_json_path(folder, filename)
		with open(path, encoding="utf-8") as fh:
			doc = json.load(fh)
		return set(entry["role"] for entry in doc.get("roles", []))

	def test_json_roles_match_workspace_role_map(self):
		"""R1 — Every affected JSON fixture must contain exactly the canonical role set."""
		cases = [
			("selección", "selección.json", "Selección"),
			("relaciones_laborales", "relaciones_laborales.json", "Relaciones Laborales"),
			("formacion_bienestar", "formacion_bienestar.json", None),  # deprecated — roles list contains only HR Training & Wellbeing
			("bienestar", "bienestar.json", "Bienestar"),
			("operación", "operación.json", "Operación"),
			("mi_perfil", "mi_perfil.json", "Mi Perfil"),
		]
		for folder, filename, map_key in cases:
			with self.subTest(workspace=folder):
				actual = self._load_json_roles(folder, filename)
				if map_key is None:
					# formacion_bienestar is deprecated — only HR Training & Wellbeing must remain
					self.assertEqual(actual, {"HR Training & Wellbeing"})
				else:
					expected = set(WORKSPACE_ROLE_MAP[map_key])
					self.assertEqual(
						actual,
						expected,
						msg=f"{filename}: expected {expected}, got {actual}",
					)

	# --- T-1.5: Patch wrapper survives engine exception -----------------------

	def test_patch_wrapper_survives_engine_exception(self):
		"""R3 — execute() must not re-raise when apply_workspace_role_matrix raises."""
		from hubgh.patches import phase9_workspace_role_unification

		with patch(
			"hubgh.patches.phase9_workspace_role_unification.apply_workspace_role_matrix",
			side_effect=RuntimeError("boom"),
		), patch(
			"hubgh.patches.phase9_workspace_role_unification.frappe.logger",
		) as mock_logger:
			result = phase9_workspace_role_unification.execute()

		self.assertIsNone(result)
		mock_logger.return_value.error.assert_called_once()
		call_kwargs = mock_logger.return_value.error.call_args
		self.assertIn("engine_failed", call_kwargs[0][0])

	# --- T-1.6: Reconciles mixed legacy+canonical on a Workspace doc ----------

	def test_phase9_reconciles_mixed_legacy_canonical(self):
		"""R3, R6 — execute() replaces legacy+canonical mix with canonical-only set."""
		from hubgh.patches import phase9_workspace_role_unification

		workspace_name = "Selección"
		if not frappe.db.exists("Workspace", workspace_name):
			self.skipTest(f"Workspace '{workspace_name}' not found on test site")

		# Set the workspace to a mixed legacy+canonical state
		ws = frappe.get_doc("Workspace", workspace_name)
		ws.set("roles", [])
		for role in ["Selección", "HR Selection"]:
			ws.append("roles", {"role": role})
		ws.save(ignore_permissions=True)
		frappe.db.commit()

		phase9_workspace_role_unification.execute()

		ws.reload()
		actual = {row.role for row in ws.roles if row.role}
		expected = set(WORKSPACE_ROLE_MAP["Selección"])
		self.assertEqual(actual, expected)

	# --- T-1.7: No-op when workspace already canonical -------------------------

	def test_phase9_is_noop_when_already_canonical(self):
		"""R4 — execute() must not modify a workspace already at canonical state."""
		from hubgh.patches import phase9_workspace_role_unification

		workspace_name = "Selección"
		if not frappe.db.exists("Workspace", workspace_name):
			self.skipTest(f"Workspace '{workspace_name}' not found on test site")

		# Set workspace to exact canonical state
		ws = frappe.get_doc("Workspace", workspace_name)
		ws.set("roles", [])
		for role in sorted(WORKSPACE_ROLE_MAP["Selección"]):
			ws.append("roles", {"role": role})
		ws.save(ignore_permissions=True)
		frappe.db.commit()

		# Capture modified timestamp before second run
		modified_before = frappe.db.get_value("Workspace", workspace_name, "modified")

		# Second run — should be a no-op
		phase9_workspace_role_unification.execute()

		modified_after = frappe.db.get_value("Workspace", workspace_name, "modified")
		self.assertEqual(
			modified_before,
			modified_after,
			msg="Workspace was modified on a second execute() call — idempotency broken",
		)

	# --- T-1.8: Skips a workspace that does not exist -------------------------

	def test_phase9_skips_nonexistent_workspace(self):
		"""R3 — execute() must not raise when a workspace in the map is missing from DB."""
		from hubgh.patches import phase9_workspace_role_unification

		_FAKE_WS = "NonexistentWS2026"

		# Monkeypatch WORKSPACE_ROLE_MAP to include a non-existent workspace
		fake_map = dict(WORKSPACE_ROLE_MAP)
		fake_map[_FAKE_WS] = ["System Manager"]

		with patch(
			"hubgh.access_profiles.WORKSPACE_ROLE_MAP",
			fake_map,
		):
			# Must not raise
			try:
				phase9_workspace_role_unification.execute()
			except Exception as exc:
				self.fail(f"execute() raised an exception for missing workspace: {exc}")

	# --- T-1.9: Preserves out-of-matrix roles on Mi Perfil -------------------

	def test_phase9_preserves_out_of_matrix_roles_on_mi_perfil(self):
		"""R5 — LMS Student and Employee survive a phase9 run on Mi Perfil."""
		from hubgh.patches import phase9_workspace_role_unification

		workspace_name = "Mi Perfil"
		if not frappe.db.exists("Workspace", workspace_name):
			self.skipTest(f"Workspace '{workspace_name}' not found on test site")
		legacy_role = "Jefe de tienda"
		if not frappe.db.exists("Role", legacy_role):
			self.skipTest(f"Legacy Role '{legacy_role}' not present — already cleaned up")
		for role in ("LMS Student", "Employee"):
			if not frappe.db.exists("Role", role):
				self.skipTest(f"Role '{role}' not present on test site")

		# Set Mi Perfil to include out-of-matrix + legacy role
		ws = frappe.get_doc("Workspace", workspace_name)
		ws.set("roles", [])
		for role in [legacy_role, "LMS Student", "Employee"]:
			ws.append("roles", {"role": role})
		ws.save(ignore_permissions=True)
		frappe.db.commit()

		phase9_workspace_role_unification.execute()

		ws.reload()
		actual = {row.role for row in ws.roles if row.role}

		# LMS Student and Employee must survive
		self.assertIn("LMS Student", actual)
		self.assertIn("Employee", actual)

		# Jefe de tienda is a legacy alias → must be replaced by Jefe_PDV (canonical)
		self.assertNotIn("Jefe de tienda", actual)
		self.assertIn("Jefe_PDV", actual)
