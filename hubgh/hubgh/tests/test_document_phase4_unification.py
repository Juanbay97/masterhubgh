from types import SimpleNamespace
from unittest.mock import patch

import frappe
from frappe.tests.utils import FrappeTestCase

from hubgh.hubgh import document_service
from hubgh.patches import document_phase4_unification


class _DummyPersonDocument:
	def __init__(self, **kwargs):
		self.file = kwargs.get("file")
		self.status = kwargs.get("status")
		self.notes = kwargs.get("notes")
		self.approved_by = kwargs.get("approved_by")
		self.approved_on = kwargs.get("approved_on")
		self.save_calls = 0

	def save(self, ignore_permissions=False):
		self.save_calls += 1


class TestDocumentPhase4Unification(FrappeTestCase):
	def test_candidate_progress_excludes_contract_from_denominator(self):
		required = [
			frappe._dict({"name": "Cedula", "document_name": "Cedula", "requires_approval": 0}),
			frappe._dict({"name": "Contrato", "document_name": "Contrato", "requires_approval": 0}),
			frappe._dict({"name": "EPS", "document_name": "EPS", "requires_approval": 0}),
		]
		docs = [
			frappe._dict({"name": "PD-1", "document_type": "Cedula", "status": "Subido", "file": "/f/cedula.pdf"}),
			frappe._dict({"name": "PD-2", "document_type": "Contrato", "status": "Pendiente", "file": "/f/contrato.pdf"}),
			frappe._dict({"name": "PD-3", "document_type": "EPS", "status": "Subido", "file": "/f/eps.pdf"}),
		]

		def _fake_get_all(doctype, *args, **kwargs):
			if doctype == "Document Type":
				return required
			if doctype == "Person Document":
				return docs
			# Permissive fallback: silence all Frappe internal lookups
			return []

		def _fake_rules(doc_type):
			return {"document_type": doc_type, "allows_multiple": 0, "requires_approval": 0}

		with patch("hubgh.hubgh.document_service.frappe.get_all", side_effect=_fake_get_all), patch(
			"hubgh.hubgh.document_service._get_document_type_rules", side_effect=_fake_rules
		):
			progress = document_service.get_candidate_progress("CAND-001")

		self.assertEqual(progress["required_total"], 2)
		self.assertEqual(progress["required_ok"], 2)
		self.assertEqual(progress["percent"], 100)
		self.assertEqual(progress["missing"], [])
		self.assertTrue(progress["is_complete"])

	def test_candidate_progress_uses_only_unified_doctypes(self):
		"""Verify get_candidate_progress only queries Document Type + Person Document.
		Required list is empty → early return; _build_person_dossier is NOT reached."""
		calls = []

		def _fake_get_all(doctype, *args, **kwargs):
			calls.append(doctype)
			# Permissive fallback: silence all Frappe internal lookups
			return []

		with patch("hubgh.hubgh.document_service.frappe.get_all", side_effect=_fake_get_all):
			progress = document_service.get_candidate_progress("CAND-002")

		# Early return: required=[] → only Document Type is queried
		self.assertEqual(calls, ["Document Type"])
		self.assertEqual(progress["required_total"], 0)

	def test_build_person_dossier_marks_vigente_historico_and_versions(self):
		rows = [
			frappe._dict({"name": "PD-NEW", "document_type": "Cedula", "status": "Subido", "file": "/f/new.pdf", "modified": "2026-03-10"}),
			frappe._dict({"name": "PD-OLD", "document_type": "Cedula", "status": "Subido", "file": "/f/old.pdf", "modified": "2026-03-01"}),
			frappe._dict({"name": "PD-M1", "document_type": "Carta Referencia", "status": "Subido", "file": "/f/m1.pdf", "modified": "2026-03-08"}),
			frappe._dict({"name": "PD-M2", "document_type": "Carta Referencia", "status": "Subido", "file": "/f/m2.pdf", "modified": "2026-03-07"}),
		]

		def _fake_rules(doc_type):
			if doc_type == "Carta Referencia":
				return {"document_type": doc_type, "allows_multiple": 1}
			return {"document_type": doc_type, "allows_multiple": 0}

		with patch("hubgh.hubgh.document_service.frappe.get_all", return_value=rows), patch(
			"hubgh.hubgh.document_service._get_document_type_rules", side_effect=_fake_rules
		):
			dossier = document_service._build_person_dossier("Candidato", "CAND-001")

		vigentes = dossier["vigentes"]
		historico = dossier["historico"]

		cedula_vigente = [r for r in vigentes if r["document_type"] == "Cedula"]
		self.assertEqual(len(cedula_vigente), 1)
		self.assertEqual(cedula_vigente[0]["name"], "PD-NEW")
		self.assertEqual(cedula_vigente[0]["version"], 1)

		cedula_historico = [r for r in historico if r["document_type"] == "Cedula"]
		self.assertEqual(len(cedula_historico), 1)
		self.assertEqual(cedula_historico[0]["name"], "PD-OLD")
		self.assertEqual(cedula_historico[0]["version"], 2)

		cartas = [r for r in vigentes if r["document_type"] == "Carta Referencia"]
		self.assertEqual(len(cartas), 2)
		self.assertEqual({r["version"] for r in cartas}, {1, 2})

	def test_migration_merge_is_non_destructive_when_new_model_already_has_data(self):
		target = _DummyPersonDocument(
			file="/private/files/current.pdf",
			status="Aprobado",
			notes="nota vigente",
			approved_by="hr@example.com",
			approved_on="2026-01-01 10:00:00",
		)
		legacy = SimpleNamespace(
			archivo="/private/files/legacy.pdf",
			estado_documento="Aprobado",
			motivo_rechazo="observación legacy",
			revisado_por="old.hr@example.com",
			fecha_ultima_revision="2025-01-01 10:00:00",
		)

		document_phase4_unification._maybe_merge_legacy_into_person_document(target, legacy)

		self.assertEqual(target.file, "/private/files/current.pdf")
		self.assertEqual(target.status, "Aprobado")
		self.assertEqual(target.notes, "nota vigente")
		self.assertEqual(target.approved_by, "hr@example.com")
		self.assertEqual(target.approved_on, "2026-01-01 10:00:00")
		self.assertEqual(target.save_calls, 1)
