# Copyright (c) 2026, Antigravity and contributors
# For license information, please see license.txt

"""
TDD — hubgh-disponibilidad-bandeja-v1, Slice 3, task 3.4 (AC-15).

The RRLL workspace requires a double-edit: the `shortcuts` array AND the
escaped `content` JSON string must both carry the same shortcut, or it
silently fails to render. No existing test in this repo guarded that
parity before this file, so the double-edit was easy to half-do.

Tests cover:
  3.4  RED+GREEN -> bidirectional shortcuts[].label <-> content shortcut_name
                    parity for the RRLL workspace (general guard, not
                    hardcoded to one shortcut)
  AC-15           -> bandeja_disponibilidad is present and lands inside the
                    "Operación RRLL" (rl-operacion) group
"""

import json

import frappe
from frappe.tests.utils import FrappeTestCase


def _load_relaciones_laborales_workspace():
	json_path = frappe.get_app_path(
		"hubgh", "hubgh", "workspace", "relaciones_laborales", "relaciones_laborales.json"
	)
	with open(json_path, encoding="utf-8") as f:
		return json.load(f)


class TestRelacionesLaboralesWorkspaceShortcutParity(FrappeTestCase):
	"""3.4 — bidirectional parity guard between `shortcuts[]` and the escaped
	`content` string. General: iterates every entry, not just the new one."""

	def test_every_shortcut_label_has_a_matching_content_shortcut_name(self):
		workspace = _load_relaciones_laborales_workspace()
		content = json.loads(workspace["content"])
		shortcut_names_in_content = {
			block["data"]["shortcut_name"] for block in content if block.get("type") == "shortcut"
		}
		labels_in_shortcuts = {entry["label"] for entry in workspace.get("shortcuts", [])}

		missing_in_content = labels_in_shortcuts - shortcut_names_in_content
		self.assertEqual(
			missing_in_content, set(),
			f"shortcuts[] entries with no matching content shortcut_name: {missing_in_content}",
		)

	def test_every_content_shortcut_name_has_a_matching_shortcuts_label(self):
		workspace = _load_relaciones_laborales_workspace()
		content = json.loads(workspace["content"])
		shortcut_names_in_content = {
			block["data"]["shortcut_name"] for block in content if block.get("type") == "shortcut"
		}
		labels_in_shortcuts = {entry["label"] for entry in workspace.get("shortcuts", [])}

		missing_in_shortcuts = shortcut_names_in_content - labels_in_shortcuts
		self.assertEqual(
			missing_in_shortcuts, set(),
			f"content shortcut_name entries with no matching shortcuts[] label: {missing_in_shortcuts}",
		)


class TestDisponibilidadShortcutReachable(FrappeTestCase):
	"""AC-15 — the new shortcut is present, points at the right page, and sits
	inside the "Operación RRLL" (rl-operacion) group in the content ordering."""

	def test_disponibilidad_shortcut_present_in_shortcuts_array(self):
		workspace = _load_relaciones_laborales_workspace()
		matches = [s for s in workspace["shortcuts"] if s["label"] == "Disponibilidad de personal"]
		self.assertEqual(len(matches), 1, "expected exactly one 'Disponibilidad de personal' shortcut entry")
		self.assertEqual(matches[0]["link_to"], "bandeja_disponibilidad")
		self.assertEqual(matches[0]["type"], "Page")

	def test_disponibilidad_shortcut_positioned_inside_operacion_rrll_group(self):
		workspace = _load_relaciones_laborales_workspace()
		content = json.loads(workspace["content"])

		group_ids = [block["id"] for block in content if block.get("type") == "header"]
		self.assertIn("rl-operacion", group_ids)

		operacion_start = next(i for i, b in enumerate(content) if b["id"] == "rl-operacion")
		next_header = next(
			(i for i, b in enumerate(content) if i > operacion_start and b.get("type") == "header"),
			len(content),
		)
		operacion_block = content[operacion_start:next_header]
		operacion_shortcut_names = {
			b["data"]["shortcut_name"] for b in operacion_block if b.get("type") == "shortcut"
		}
		self.assertIn("Disponibilidad de personal", operacion_shortcut_names)
