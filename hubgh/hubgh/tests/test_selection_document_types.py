import json
import sys
import types
from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import Mock, patch


_ORIGINAL_FRAPPE = sys.modules.get("frappe")


def _install_frappe_stub():
	frappe_module = types.ModuleType("frappe")
	frappe_module.db = SimpleNamespace(exists=lambda *args, **kwargs: False, sql=lambda *args, **kwargs: None)
	frappe_module.get_all = lambda *args, **kwargs: []
	frappe_module.get_doc = lambda *args, **kwargs: None
	frappe_module.rename_doc = lambda *args, **kwargs: None
	sys.modules["frappe"] = frappe_module


_install_frappe_stub()

from hubgh.hubgh.selection_document_types import (
	canonicalize_selection_document_name,
	sync_selection_document_types,
	sync_selection_workspace_shortcut,
)


def tearDownModule():
	if _ORIGINAL_FRAPPE is None:
		sys.modules.pop("frappe", None)
	else:
		sys.modules["frappe"] = _ORIGINAL_FRAPPE


class _DocumentTypeStub:
	def __init__(self, name, is_new=False):
		self.doctype = "Document Type"
		self.name = name
		self.document_name = name
		self.applies_to = "Candidato"
		self._is_new = is_new
		self.saved = 0
		self.inserted = 0

	def is_new(self):
		return self._is_new

	def insert(self, ignore_permissions=False):
		self._is_new = False
		self.inserted += 1

	def save(self, ignore_permissions=False):
		self.saved += 1


class _WorkspaceStub:
	def __init__(self):
		self.shortcuts = [
			SimpleNamespace(
				label="Documentos requeridos",
				link_to="Documento Requerido",
				type="DocType",
				doc_view="List",
			)
		]
		self.content = json.dumps(
			[
				{"type": "shortcut", "data": {"shortcut_name": "Documentos requeridos", "col": 4}},
			],
			ensure_ascii=False,
		)
		self.saved = 0

	def save(self, ignore_permissions=False):
		self.saved += 1


class TestSelectionDocumentTypes(TestCase):
	def test_canonicalize_selection_document_name_maps_legacy_aliases(self):
		self.assertEqual(canonicalize_selection_document_name("Carta oferta"), "Carta Oferta")
		self.assertEqual(
			canonicalize_selection_document_name("Documento autorización de ingreso"),
			"Autorización de Ingreso",
		)

	def test_sync_selection_document_types_renames_alias_into_canonical_doc(self):
		storage = {"Carta oferta": _DocumentTypeStub("Carta oferta")}

		def _get_all(doctype, filters=None, fields=None, limit_page_length=None, **kwargs):
			if doctype != "Document Type":
				return []
			name = (filters or {}).get("name")
			if name in storage:
				doc = storage[name]
				return [SimpleNamespace(name=doc.name, document_name=doc.document_name)]
			return []

		def _get_doc(*args, **kwargs):
			if len(args) == 2:
				return storage[args[1]]
			payload = args[0]
			doc = _DocumentTypeStub(payload["document_name"], is_new=True)
			storage[doc.name] = doc
			return doc

		def _rename_doc(doctype, old_name, new_name, force=False, merge=False):
			doc = storage.pop(old_name)
			doc.name = new_name
			doc.document_name = new_name
			storage[new_name] = doc

		with patch("hubgh.hubgh.selection_document_types.frappe.db.exists", return_value=True), patch(
			"hubgh.hubgh.selection_document_types.frappe.get_all",
			side_effect=_get_all,
		), patch("hubgh.hubgh.selection_document_types.frappe.get_doc", side_effect=_get_doc), patch(
			"hubgh.hubgh.selection_document_types.frappe.rename_doc",
			side_effect=_rename_doc,
		), patch("hubgh.hubgh.selection_document_types.frappe.db.sql"):
			result = sync_selection_document_types()

		self.assertIn("Carta oferta->Carta Oferta", result["renamed"])
		self.assertIn("Carta Oferta", storage)
		self.assertEqual(storage["Carta Oferta"].allowed_roles_override, "HR Selection")
		self.assertEqual(int(storage["Carta Oferta"].is_active or 0), 1)

	def test_sync_selection_document_types_repoints_duplicates_and_deactivates_alias(self):
		storage = {
			"Autorización de Ingreso": _DocumentTypeStub("Autorización de Ingreso"),
			"Documento autorización de ingreso": _DocumentTypeStub("Documento autorización de ingreso"),
		}

		def _get_all(doctype, filters=None, fields=None, limit_page_length=None, **kwargs):
			if doctype != "Document Type":
				return []
			name = (filters or {}).get("name")
			if name in storage:
				doc = storage[name]
				return [SimpleNamespace(name=doc.name, document_name=doc.document_name)]
			return []

		def _get_doc(*args, **kwargs):
			if len(args) == 2:
				return storage[args[1]]
			payload = args[0]
			doc = _DocumentTypeStub(payload["document_name"], is_new=True)
			storage[doc.name] = doc
			return doc

		sql_mock = Mock()

		with patch("hubgh.hubgh.selection_document_types.frappe.db.exists", return_value=True), patch(
			"hubgh.hubgh.selection_document_types.frappe.get_all",
			side_effect=_get_all,
		), patch("hubgh.hubgh.selection_document_types.frappe.get_doc", side_effect=_get_doc), patch(
			"hubgh.hubgh.selection_document_types.frappe.rename_doc"
		) as rename_mock, patch("hubgh.hubgh.selection_document_types.frappe.db.sql", sql_mock):
			result = sync_selection_document_types()

		rename_mock.assert_not_called()
		sql_mock.assert_any_call(
			"update `tabPerson Document` set document_type=%s where document_type=%s",
			("Autorización de Ingreso", "Documento autorización de ingreso"),
		)
		self.assertIn("Documento autorización de ingreso", result["deactivated"])
		self.assertEqual(int(storage["Documento autorización de ingreso"].is_active or 0), 0)

	def test_sync_selection_document_types_skips_missing_legacy_link(self):
		storage = {}

		def _exists(doctype, name=None, *args, **kwargs):
			if doctype == "DocType" and name == "Document Type":
				return True
			if doctype == "Documento Requerido":
				return False
			return False

		def _get_all(doctype, filters=None, fields=None, limit_page_length=None, **kwargs):
			if doctype != "Document Type":
				return []
			name = (filters or {}).get("name")
			if name in storage:
				doc = storage[name]
				return [SimpleNamespace(name=doc.name, document_name=doc.document_name)]
			return []

		def _get_doc(*args, **kwargs):
			if len(args) == 2:
				return storage[args[1]]
			payload = args[0]
			doc = _DocumentTypeStub(payload["document_name"], is_new=True)
			storage[doc.name] = doc
			return doc

		with patch("hubgh.hubgh.selection_document_types.frappe.db.exists", side_effect=_exists), patch(
			"hubgh.hubgh.selection_document_types.frappe.get_all",
			side_effect=_get_all,
		), patch("hubgh.hubgh.selection_document_types.frappe.get_doc", side_effect=_get_doc), patch(
			"hubgh.hubgh.selection_document_types.frappe.rename_doc"
		), patch("hubgh.hubgh.selection_document_types.frappe.db.sql"):
			sync_selection_document_types()

		self.assertIn("Hoja de vida actualizada.", storage)
		self.assertIsNone(storage["Hoja de vida actualizada."].legacy_documento_requerido)
		self.assertIn("Examen Médico", storage)
		self.assertEqual(storage["Examen Médico"].allowed_roles_override, "HR Selection")

	def test_sync_selection_workspace_shortcut_points_to_document_type(self):
		workspace = _WorkspaceStub()

		with patch("hubgh.hubgh.selection_document_types.frappe.db.exists", return_value=True), patch(
			"hubgh.hubgh.selection_document_types.frappe.get_doc",
			return_value=workspace,
		):
			changed = sync_selection_workspace_shortcut()

		self.assertTrue(changed)
		self.assertEqual(workspace.shortcuts[0].label, "Tipos de documento")
		self.assertEqual(workspace.shortcuts[0].link_to, "Document Type")
		self.assertIn("Tipos de documento", workspace.content)
		self.assertEqual(workspace.saved, 1)
