# Copyright (c) 2026, Antigravity and contributors
# For license information, please see license.txt

"""
TDD — PR B: per-document exemption backend.

Covers:
- Phase B3 (pure): _compute_candidate_progress Exento predicate (no DB).
- Phase B2/B3 (integration): exempt/revoke service pair + whitelisted endpoint
  gates, using real FrappeTestCase fixtures (Document Type, Candidato,
  Person Document), mirroring test_document_type_read_permission.py's style.

Binding overrides pinned here:
- exempt/revoke never call set_candidate_status_from_progress (B3.9).
- Exemption rejected for Rechazado, allowed for Contratado and every other
  state (B3.10/B3.11).
- Audit trail is an explicit Comment doc insert (api/correcciones.py pattern),
  never doc.add_comment (B3.7/B4.3/B4.4).
- allows_multiple types may create a new Person Document row via
  ensure_person_document (B3.8).
- SAGRILAFT stays hard-gated by file + Subido/Aprobado regardless of
  exemption (B3.3/B3.14). See document_service.py's sagrilaft_ok loop for the
  code comment warning against merging that gate with the exemption predicate.
"""

import contextlib
import uuid
from unittest import TestCase
from unittest.mock import patch

import frappe
from frappe.tests.utils import FrappeTestCase

from hubgh.hubgh.document_service import (
	_compute_candidate_progress,
	get_candidate_progress,
	get_candidates_progress_bulk,
)
from hubgh.hubgh.page.seleccion_documentos import seleccion_documentos


HR_EXT_ROLES = ["HR Selection", "Gestión Humana", "GH - Bandeja General", "Gerente GH"]

# Module-level registry of everything this module's fixtures create, so
# tearDownModule() can remove it deterministically regardless of how many
# times the module is re-run within the same hour. Populated by the _seed_*
# helpers below; consumed once, at the very end, by tearDownModule().
_CREATED_CANDIDATOS = []
_CREATED_DOCUMENT_TYPES = []
_CREATED_USERS = []


@contextlib.contextmanager
def _bypass_user_creation_throttle():
	"""Test-only bypass for frappe.core.doctype.user.user.throttle_user_creation,
	which frappe.throw()s once more than `throttle_user_limit` (default 60)
	User docs were created in the last 60 minutes — a real, previously-hit
	failure mode for this module (it seeds one real User per Candidato, since
	Candidato.before_insert's "existing user" fast path requires a
	pre-created, uniquely-emailed User).

	throttle_user_creation() itself returns early when frappe.flags.in_import
	is truthy — the exact bypass this codebase's own bulk-import code already
	relies on (hubgh/hubgh/utils.py:179-180). Using the same flag here makes
	this fixture immune to the ambient hourly quota regardless of how many
	Users any other test/process created in the same window; it does not
	depend on — and must never depend on — clearing or waiting out that
	quota."""
	flags = frappe.flags
	previous = getattr(flags, "in_import", False)
	flags.in_import = True
	try:
		yield
	finally:
		flags.in_import = previous


def _ensure_user(email, roles):
	if not frappe.db.exists("User", email):
		with _bypass_user_creation_throttle():
			frappe.get_doc({
				"doctype": "User", "email": email, "first_name": email.split("@")[0],
				"enabled": 1, "send_welcome_email": 0,
			}).insert(ignore_permissions=True)
		_CREATED_USERS.append(email)
	frappe.db.delete("Has Role", {"parent": email})
	for role in roles:
		if frappe.db.exists("Role", role):
			frappe.get_doc({
				"doctype": "Has Role", "parent": email, "parenttype": "User",
				"parentfield": "roles", "role": role,
			}).insert(ignore_permissions=True)
	frappe.db.commit()


def _seed_document_type(prefix, is_active=1, is_required_for_hiring=1, applies_to="Candidato", allows_multiple=0, requires_approval=0):
	name = f"{prefix}-{uuid.uuid4().hex[:6].upper()}"
	if not frappe.db.exists("Document Type", name):
		frappe.get_doc({
			"doctype": "Document Type",
			"document_name": name,
			"is_active": is_active,
			"is_required_for_hiring": is_required_for_hiring,
			"applies_to": applies_to,
			"allows_multiple": allows_multiple,
			"requires_approval": requires_approval,
		}).insert(ignore_permissions=True)
	_CREATED_DOCUMENT_TYPES.append(name)
	return name


def _seed_candidato(estado_proceso="En Proceso"):
	cedula = f"DEX{uuid.uuid4().hex[:8].upper()}"
	user_email = f"{cedula.lower()}@example.com"
	with _bypass_user_creation_throttle():
		user_doc = frappe.get_doc({
			"doctype": "User", "email": user_email, "first_name": "ExemptionTest",
			"enabled": 1, "send_welcome_email": 0, "user_type": "Website User",
			"roles": [{"role": "Candidato"}],
		})
		user_doc.insert(ignore_permissions=True)
	_CREATED_USERS.append(user_doc.name)

	doc = frappe.new_doc("Candidato")
	doc.tipo_documento = "Cedula"
	doc.numero_documento = cedula
	doc.nombres = "ExemptionTest"
	doc.primer_apellido = doc.apellidos = "Candidato"
	doc.email = user_email
	doc.user = user_doc.name
	doc.celular = "3000000000"
	doc.direccion = "Calle Falsa 123"
	doc.ciudad = "Barranquilla"
	doc.estado_proceso = "En Proceso"
	doc.insert(ignore_permissions=True)
	frappe.db.commit()
	_CREATED_CANDIDATOS.append(doc.name)
	if estado_proceso != "En Proceso":
		# Workflow validation on Candidato.insert only allows the default
		# initial transition. Direct frappe.db.set_value bypasses that
		# validation for test fixtures — the same pattern production code
		# uses for every real state transition (reject_candidate,
		# send_to_medical_exam, etc. never call doc.save() to move state).
		frappe.db.set_value("Candidato", doc.name, "estado_proceso", estado_proceso)
		frappe.db.commit()
	return doc.name


def _comment_count(candidate):
	return frappe.db.count("Comment", {"reference_doctype": "Candidato", "reference_name": candidate})


def _seed_person_document(candidate, document_type, status="Pendiente", file=None):
	doc = frappe.get_doc({
		"doctype": "Person Document",
		"person_type": "Candidato",
		"person_doctype": "Candidato",
		"person": candidate,
		"candidate": candidate,
		"document_type": document_type,
		"status": status,
		"file": file,
	})
	doc.insert(ignore_permissions=True)
	frappe.db.commit()
	return doc


# ---------------------------------------------------------------------------
# Phase B3 (pure) — _compute_candidate_progress Exento predicate, no DB
# ---------------------------------------------------------------------------

def _req(name, requires_approval=0):
	return {"name": name, "requires_approval": requires_approval}


def _pd_row(status, file="/private/files/x.pdf"):
	return {"status": status, "file": file}


class TestComputeCandidateProgressExemption(TestCase):

	def test_exento_counts_as_ok_and_not_missing(self):
		required = [_req("Cedula")]
		vigentes_by_type = {"Cedula": [_pd_row("Exento", file=None)]}
		result = _compute_candidate_progress(required, vigentes_by_type)
		self.assertTrue(result["is_complete"])
		self.assertEqual(result["missing"], [])
		self.assertEqual(result["exempted"], ["Cedula"])

	def test_exento_short_circuits_requires_approval(self):
		required = [_req("SAGRILAFT", requires_approval=1)]
		vigentes_by_type = {"SAGRILAFT": [_pd_row("Exento", file=None)]}
		result = _compute_candidate_progress(required, vigentes_by_type)
		self.assertTrue(result["is_complete"])
		self.assertEqual(result["exempted"], ["SAGRILAFT"])
		self.assertEqual(result["missing"], [])

	def test_progress_all_exempted(self):
		required = [_req("Cedula"), _req("EPS"), _req("SAGRILAFT", requires_approval=1)]
		vigentes_by_type = {
			"Cedula": [_pd_row("Exento", file=None)],
			"EPS": [_pd_row("Exento", file=None)],
			"SAGRILAFT": [_pd_row("Exento", file=None)],
		}
		result = _compute_candidate_progress(required, vigentes_by_type)
		self.assertEqual(result["percent"], 100)
		self.assertTrue(result["is_complete"])
		self.assertEqual(result["missing"], [])
		self.assertEqual(sorted(result["exempted"]), ["Cedula", "EPS", "SAGRILAFT"])

	def test_non_exempted_missing_doc_not_listed_as_exempted(self):
		required = [_req("Cedula"), _req("EPS")]
		vigentes_by_type = {"Cedula": [_pd_row("Exento", file=None)]}
		result = _compute_candidate_progress(required, vigentes_by_type)
		self.assertFalse(result["is_complete"])
		self.assertEqual(result["missing"], ["EPS"])
		self.assertEqual(result["exempted"], ["Cedula"])


# ---------------------------------------------------------------------------
# Phase B3 — sagrilaft_ok stays False when the SAGRILAFT row is Exento
# (bulk-path fixture, matches TestCandidatesProgressBulk style in
# test_flow_phase9_adjustments.py)
# ---------------------------------------------------------------------------

class TestSagrilaftOkUnaffectedByExemption(FrappeTestCase):

	def test_sagrilaft_ok_false_when_exento(self):
		# "SAGRILAFT" is a real, already-seeded Document Type (canonical
		# selection document, is_active=1, is_required_for_hiring=1) — use it
		# directly so the SAGRILAFT lookup-name resolution (module constant,
		# no query) exercises the real production path.
		candidate = _seed_candidato()
		_seed_person_document(candidate, "SAGRILAFT", status="Exento", file=None)

		result = get_candidates_progress_bulk([candidate])

		self.assertIn(candidate, result)
		self.assertFalse(result[candidate]["sagrilaft_ok"])
		self.assertIn("SAGRILAFT", result[candidate]["exempted"])


# ---------------------------------------------------------------------------
# Phase B3 — service-layer behavior (exempt_person_document / revoke)
# ---------------------------------------------------------------------------

class TestExemptPersonDocument(FrappeTestCase):

	def test_rejects_uploaded_document(self):
		from hubgh.hubgh.document_service import exempt_person_document

		doc_type = _seed_document_type("REQ-B34")
		candidate = _seed_candidato()
		_seed_person_document(candidate, doc_type, status="Subido", file="/private/files/x.pdf")

		with self.assertRaises(frappe.ValidationError):
			exempt_person_document("Candidato", candidate, doc_type, "motivo valido")

		row = frappe.db.get_value("Person Document", {"candidate": candidate, "document_type": doc_type}, "status")
		self.assertEqual(row, "Subido")

	def test_rejects_double_exempt(self):
		from hubgh.hubgh.document_service import exempt_person_document

		doc_type = _seed_document_type("REQ-B35")
		candidate = _seed_candidato()
		_seed_person_document(candidate, doc_type, status="Exento", file=None)

		with self.assertRaises(frappe.ValidationError):
			exempt_person_document("Candidato", candidate, doc_type, "motivo valido")

	def test_allows_multiple_creates_new_row(self):
		from hubgh.hubgh.document_service import exempt_person_document

		doc_type = _seed_document_type("REQ-B38", allows_multiple=1)
		candidate = _seed_candidato()
		# Existing uploaded row for this allows_multiple type — must NOT be
		# mutated; exemption should create a fresh pending row instead.
		_seed_person_document(candidate, doc_type, status="Subido", file="/private/files/x.pdf")

		doc = exempt_person_document("Candidato", candidate, doc_type, "excepcion multiple")

		self.assertEqual(doc.status, "Exento")
		rows = frappe.get_all(
			"Person Document",
			filters={"candidate": candidate, "document_type": doc_type},
			fields=["name", "status"],
		)
		self.assertEqual(len(rows), 2)
		statuses = sorted(r.status for r in rows)
		self.assertEqual(statuses, ["Exento", "Subido"])

	def test_sets_audit_fields_and_inserts_comment(self):
		from hubgh.hubgh.document_service import exempt_person_document

		doc_type = _seed_document_type("REQ-B4X")
		candidate = _seed_candidato()

		doc = exempt_person_document("Candidato", candidate, doc_type, "Aplica excepcion contractual")

		self.assertEqual(doc.status, "Exento")
		self.assertEqual(doc.exencion_motivo, "Aplica excepcion contractual")
		self.assertEqual(doc.exonerado_por, frappe.session.user)
		self.assertIsNotNone(doc.exonerado_en)

		comments = frappe.get_all(
			"Comment",
			filters={"reference_doctype": "Candidato", "reference_name": candidate},
			fields=["content"],
		)
		self.assertTrue(any("exon" in (c.content or "").lower() for c in comments))


class TestRevokePersonDocumentExemption(FrappeTestCase):

	def test_rejects_non_exento(self):
		from hubgh.hubgh.document_service import revoke_person_document_exemption

		doc_type = _seed_document_type("REQ-B36")
		candidate = _seed_candidato()
		_seed_person_document(candidate, doc_type, status="Pendiente", file=None)

		with self.assertRaises(frappe.ValidationError):
			revoke_person_document_exemption("Candidato", candidate, doc_type)

	def test_keeps_audit_fields_and_inserts_revocation_comment(self):
		from hubgh.hubgh.document_service import exempt_person_document, revoke_person_document_exemption

		doc_type = _seed_document_type("REQ-B37")
		candidate = _seed_candidato()
		exempt_person_document("Candidato", candidate, doc_type, "motivo original")

		doc = revoke_person_document_exemption("Candidato", candidate, doc_type, "ya no aplica")

		self.assertEqual(doc.status, "Pendiente")
		self.assertEqual(doc.exencion_motivo, "motivo original")
		self.assertEqual(doc.exonerado_por, frappe.session.user)
		self.assertIsNotNone(doc.exonerado_en)

		comments = frappe.get_all(
			"Comment",
			filters={"reference_doctype": "Candidato", "reference_name": candidate},
			fields=["content"],
			order_by="creation desc",
		)
		self.assertGreaterEqual(len(comments), 2)
		self.assertTrue(any("revoc" in (c.content or "").lower() for c in comments))


# ---------------------------------------------------------------------------
# Phase B2/B3 — whitelisted endpoint gates (seleccion_documentos.py)
# ---------------------------------------------------------------------------

class TestExemptCandidateDocumentEndpoint(FrappeTestCase):

	def tearDown(self):
		frappe.set_user("Administrator")
		super().tearDown()

	def test_requires_selection_access(self):
		doc_type = _seed_document_type("REQ-B21")
		candidate = _seed_candidato()
		_ensure_user("b21_hrsst@example.com", ["HR SST"])
		before = _comment_count(candidate)

		with patch.object(seleccion_documentos, "exempt_person_document") as mock_exempt:
			frappe.set_user("b21_hrsst@example.com")
			try:
				with self.assertRaises(frappe.ValidationError):
					seleccion_documentos.exempt_candidate_document(candidate, doc_type, "motivo valido")
			finally:
				frappe.set_user("Administrator")

		mock_exempt.assert_not_called()
		self.assertEqual(_comment_count(candidate), before)

	def test_rejects_invalid_document_type(self):
		candidate = _seed_candidato()
		before = _comment_count(candidate)
		with patch.object(seleccion_documentos, "exempt_person_document") as mock_exempt:
			with self.assertRaises(frappe.ValidationError):
				seleccion_documentos.exempt_candidate_document(candidate, "NOT-A-REAL-TYPE", "motivo valido")
		mock_exempt.assert_not_called()
		self.assertEqual(_comment_count(candidate), before)

	def test_motivo_required(self):
		doc_type = _seed_document_type("REQ-B24")
		candidate = _seed_candidato()
		for motivo in ("", "   ", None):
			with self.subTest(motivo=motivo):
				with patch.object(seleccion_documentos, "exempt_person_document") as mock_exempt:
					with self.assertRaises(frappe.ValidationError):
						seleccion_documentos.exempt_candidate_document(candidate, doc_type, motivo)
				mock_exempt.assert_not_called()

	def test_rejected_for_rechazado_candidate(self):
		doc_type = _seed_document_type("REQ-B310")
		candidate = _seed_candidato(estado_proceso="Rechazado")
		with patch.object(seleccion_documentos, "exempt_person_document") as mock_exempt:
			with self.assertRaises(frappe.ValidationError):
				seleccion_documentos.exempt_candidate_document(candidate, doc_type, "motivo valido")
		mock_exempt.assert_not_called()

	def test_allowed_for_contratado_candidate(self):
		doc_type = _seed_document_type("REQ-B311")
		candidate = _seed_candidato(estado_proceso="Contratado")
		result = seleccion_documentos.exempt_candidate_document(candidate, doc_type, "motivo valido")
		self.assertEqual(result["status"], "Exento")
		self.assertEqual(result["document_type"], doc_type)

	def test_does_not_advance_status(self):
		doc_type = _seed_document_type("REQ-B39")
		candidate = _seed_candidato(estado_proceso="En Proceso")
		with patch("hubgh.hubgh.document_service.set_candidate_status_from_progress") as mock_advance:
			result = seleccion_documentos.exempt_candidate_document(candidate, doc_type, "motivo valido")
		mock_advance.assert_not_called()
		self.assertEqual(result["status"], "Exento")


class TestRevokeCandidateDocumentExemptionEndpoint(FrappeTestCase):

	def tearDown(self):
		frappe.set_user("Administrator")
		super().tearDown()

	def test_requires_selection_access(self):
		doc_type = _seed_document_type("REQ-B22")
		candidate = _seed_candidato()
		_ensure_user("b22_hrsst@example.com", ["HR SST"])

		with patch.object(seleccion_documentos, "revoke_person_document_exemption") as mock_revoke:
			frappe.set_user("b22_hrsst@example.com")
			try:
				with self.assertRaises(frappe.ValidationError):
					seleccion_documentos.revoke_candidate_document_exemption(candidate, doc_type)
			finally:
				frappe.set_user("Administrator")

		mock_revoke.assert_not_called()

	def test_revoke_returns_pending(self):
		doc_type = _seed_document_type("REQ-B52")
		candidate = _seed_candidato()
		seleccion_documentos.exempt_candidate_document(candidate, doc_type, "motivo original")

		result = seleccion_documentos.revoke_candidate_document_exemption(candidate, doc_type)
		self.assertEqual(result["status"], "Pendiente")
		self.assertEqual(result["document_type"], doc_type)


# ---------------------------------------------------------------------------
# Phase B3.14 — SAGRILAFT hard gate at send_to_labor_relations stays isolated
# ---------------------------------------------------------------------------

class TestSendToLaborRelationsSagrilaftGate(FrappeTestCase):

	def test_blocked_by_exempted_sagrilaft(self):
		# Real, already-seeded "SAGRILAFT" Document Type — exercises the
		# production _has_uploaded_document/lookup-name path unmocked.
		candidate = _seed_candidato()
		frappe.db.set_value("Candidato", candidate, "concepto_medico", "Favorable")

		seleccion_documentos.exempt_candidate_document(candidate, "SAGRILAFT", "excepcion sagrilaft")

		with self.assertRaisesRegex(frappe.ValidationError, "falta documento SAGRILAFT"):
			seleccion_documentos.send_to_labor_relations(candidate)


def tearDownModule():
	"""Self-cleaning teardown — this module's fixtures call frappe.db.commit()
	(needed so frappe.set_user() role-switching sees committed Has Role rows;
	same pattern as test_document_type_read_permission.py), which means the
	usual FrappeTestCase per-test rollback does NOT apply here and every
	Candidato/User/Document Type this module created would otherwise persist
	in hubgh.local permanently across runs. Without this, repeated runs (CI,
	verify phase, a colleague's machine) accumulate orphan Users until
	frappe's throttle_user_creation() starts throwing "Throttled" for
	completely unrelated work — exactly the failure this teardown exists to
	prevent. Deletes only names this module itself tracked creating, in FK
	order, then commits.
	"""
	if _CREATED_CANDIDATOS:
		pd_names = frappe.get_all(
			"Person Document",
			filters={"candidate": ["in", _CREATED_CANDIDATOS]},
			pluck="name",
		)
		for name in pd_names:
			frappe.delete_doc("Person Document", name, force=1, ignore_permissions=True)
		for name in _CREATED_CANDIDATOS:
			if frappe.db.exists("Candidato", name):
				frappe.delete_doc("Candidato", name, force=1, ignore_permissions=True)

	if _CREATED_DOCUMENT_TYPES:
		pd_names = frappe.get_all(
			"Person Document",
			filters={"document_type": ["in", _CREATED_DOCUMENT_TYPES]},
			pluck="name",
		)
		for name in pd_names:
			frappe.delete_doc("Person Document", name, force=1, ignore_permissions=True)
		for name in _CREATED_DOCUMENT_TYPES:
			if frappe.db.exists("Document Type", name):
				frappe.delete_doc("Document Type", name, force=1, ignore_permissions=True)

	for name in _CREATED_USERS:
		if frappe.db.exists("User", name):
			frappe.delete_doc("User", name, force=1, ignore_permissions=True)

	frappe.db.commit()
