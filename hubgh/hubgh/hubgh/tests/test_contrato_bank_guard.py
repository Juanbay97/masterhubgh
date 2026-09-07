# Copyright (c) 2026, Antigravity and contributors
# For license information, please see license.txt

"""
Regression tests for the Contrato bank-data submit guard and snapshot sync.

Production incident (candidate 1032391786, contract CONT--10516): the contract
was submitted before the bank data existed and the fields are not
allow_on_submit, so the SIESA export could never resolve the bank account.
The fix is twofold:

1. ``_sync_candidate_snapshot`` also falls back to Datos Contratacion when the
   Candidato has no bank data yet.
2. ``before_submit`` refuses to submit when the candidate is expected to have
   a bank account and the contract still has blank bank fields.

Pure unit tests (no site, no DB): the module-level ``frappe`` attribute of the
contrato module is patched and the document is built with ``__new__`` so
``Document.__init__`` never touches the database.
"""

from unittest import TestCase
from unittest.mock import MagicMock, patch

import frappe
from frappe.exceptions import ValidationError

from hubgh.hubgh.doctype.contrato import contrato as contrato_module
from hubgh.hubgh.doctype.contrato.contrato import Contrato


CANDIDATO = "1032391786"

BANK_DATA = {
	"numero_cuenta_bancaria": "525-971625-29",
	"banco_siesa": "Davivienda",
	"tipo_cuenta_bancaria": "Corriente",
}
BLANK_BANK_DATA = {
	"numero_cuenta_bancaria": None,
	"banco_siesa": None,
	"tipo_cuenta_bancaria": None,
}


def _make_contrato(**fields):
	doc = Contrato.__new__(Contrato)
	doc.__dict__.update(
		{
			"name": "CONT--10516",
			"doctype": "Contrato",
			"candidato": CANDIDATO,
			"numero_documento": CANDIDATO,
			"nombres": "Ana",
			"apellidos": "Perez",
			"email": "ana@example.com",
			"cuenta_bancaria": None,
			"banco_siesa": None,
			"tipo_cuenta_bancaria": None,
			"entidad_eps_siesa": "EPS",
			"entidad_afp_siesa": "AFP",
			"entidad_cesantias_siesa": "CES",
			"entidad_ccf_siesa": "CCF",
		}
	)
	doc.__dict__.update(fields)
	return doc


def _candidate(tiene_cuenta_bancaria=None, bank=None):
	record = frappe._dict(
		{
			"name": CANDIDATO,
			"numero_documento": CANDIDATO,
			"nombres": "Ana",
			"apellidos": "Perez",
			"email": "ana@example.com",
			"eps_siesa": "EPS",
			"afp_siesa": "AFP",
			"cesantias_siesa": "CES",
			"ccf_siesa": "CCF",
			"tiene_cuenta_bancaria": tiene_cuenta_bancaria,
		}
	)
	record.update(BLANK_BANK_DATA)
	record.update(bank or {})
	return record


def _datos_contratacion(tiene_cuenta_bancaria=None, bank=None):
	record = frappe._dict({"tiene_cuenta_bancaria": tiene_cuenta_bancaria})
	record.update(BLANK_BANK_DATA)
	record.update(bank or {})
	return record


class _FrappeStub:
	def __init__(self, candidate, datos):
		self.candidate = candidate
		self.datos = datos

	def build(self):
		mock_frappe = MagicMock()
		mock_frappe.throw.side_effect = ValidationError
		mock_frappe.get_doc.side_effect = self.get_doc
		mock_frappe.db.get_value.side_effect = self.get_value
		return mock_frappe

	def get_doc(self, doctype, name=None):
		if doctype == "Candidato":
			return self.candidate
		raise AssertionError(f"unexpected get_doc({doctype!r}, {name!r})")

	def get_value(self, doctype, filters=None, fieldname=None, **kwargs):
		if doctype == "Datos Contratacion":
			if filters != {"candidato": CANDIDATO}:
				raise AssertionError(f"Datos Contratacion must be looked up by candidato, got {filters!r}")
			return self.datos
		if doctype == "Candidato":
			return self.candidate
		raise AssertionError(f"unexpected get_value({doctype!r}, {filters!r}, {fieldname!r})")


class ContratoBankGuardTest(TestCase):
	def _before_submit(self, doc, candidate, datos):
		stub = _FrappeStub(candidate, datos)
		mock_frappe = stub.build()
		with patch("hubgh.hubgh.doctype.contrato.contrato.frappe", mock_frappe):
			doc.before_submit()
		return mock_frappe

	def test_candidate_says_si_and_contract_blank_raises(self):
		doc = _make_contrato()
		with self.assertRaises(ValidationError):
			self._before_submit(doc, _candidate(tiene_cuenta_bancaria="Si"), _datos_contratacion())

	def test_error_message_names_missing_fields(self):
		doc = _make_contrato(cuenta_bancaria="123")
		stub = _FrappeStub(_candidate(tiene_cuenta_bancaria="Si"), _datos_contratacion())
		mock_frappe = stub.build()
		with patch("hubgh.hubgh.doctype.contrato.contrato.frappe", mock_frappe):
			with self.assertRaises(ValidationError):
				doc.before_submit()

		message = mock_frappe.throw.call_args.args[0]
		self.assertIn("Banco", message)
		self.assertIn("Tipo de cuenta", message)
		self.assertNotIn("Cuenta bancaria", message)
		self.assertIn("Datos Contratación", message)

	def test_candidate_says_no_and_no_data_anywhere_allows_submit(self):
		doc = _make_contrato()
		mock_frappe = self._before_submit(doc, _candidate(tiene_cuenta_bancaria="No"), _datos_contratacion())
		mock_frappe.throw.assert_not_called()

	def test_datos_contratacion_bank_data_with_blank_candidate_raises(self):
		doc = _make_contrato()
		with self.assertRaises(ValidationError):
			self._before_submit(doc, _candidate(), _datos_contratacion(bank=BANK_DATA))

	def test_datos_contratacion_says_si_with_blank_candidate_raises(self):
		doc = _make_contrato()
		with self.assertRaises(ValidationError):
			self._before_submit(doc, _candidate(tiene_cuenta_bancaria="No"), _datos_contratacion(tiene_cuenta_bancaria="sí"))

	def test_candidate_bank_data_without_flag_raises(self):
		doc = _make_contrato()
		with self.assertRaises(ValidationError):
			self._before_submit(doc, _candidate(bank={"banco_siesa": "Davivienda"}), _datos_contratacion())

	def test_complete_contract_allows_submit(self):
		doc = _make_contrato(cuenta_bancaria="525-971625-29", banco_siesa="Davivienda", tipo_cuenta_bancaria="Corriente")
		mock_frappe = self._before_submit(doc, _candidate(tiene_cuenta_bancaria="Si"), _datos_contratacion())
		mock_frappe.throw.assert_not_called()

	def test_missing_datos_contratacion_record_is_tolerated(self):
		doc = _make_contrato()
		mock_frappe = self._before_submit(doc, _candidate(tiene_cuenta_bancaria="No"), None)
		mock_frappe.throw.assert_not_called()


class ContratoSyncCandidateSnapshotTest(TestCase):
	def _sync(self, doc, candidate, datos):
		stub = _FrappeStub(candidate, datos)
		mock_frappe = stub.build()
		with patch("hubgh.hubgh.doctype.contrato.contrato.frappe", mock_frappe):
			doc._sync_candidate_snapshot()
		return mock_frappe

	def test_fills_bank_fields_from_datos_contratacion_when_candidate_lacks_them(self):
		doc = _make_contrato()
		self._sync(doc, _candidate(), _datos_contratacion(bank=BANK_DATA))

		self.assertEqual(doc.cuenta_bancaria, "525-971625-29")
		self.assertEqual(doc.banco_siesa, "Davivienda")
		self.assertEqual(doc.tipo_cuenta_bancaria, "Corriente")

	def test_candidate_bank_data_wins_over_datos_contratacion(self):
		doc = _make_contrato()
		candidate_bank = {"numero_cuenta_bancaria": "111", "banco_siesa": "Bancolombia", "tipo_cuenta_bancaria": "Ahorros"}
		self._sync(doc, _candidate(bank=candidate_bank), _datos_contratacion(bank=BANK_DATA))

		self.assertEqual(doc.cuenta_bancaria, "111")
		self.assertEqual(doc.banco_siesa, "Bancolombia")
		self.assertEqual(doc.tipo_cuenta_bancaria, "Ahorros")

	def test_only_blank_fields_are_filled_from_datos_contratacion(self):
		doc = _make_contrato()
		self._sync(doc, _candidate(bank={"banco_siesa": "Bancolombia"}), _datos_contratacion(bank=BANK_DATA))

		self.assertEqual(doc.banco_siesa, "Bancolombia")
		self.assertEqual(doc.cuenta_bancaria, "525-971625-29")
		self.assertEqual(doc.tipo_cuenta_bancaria, "Corriente")

	def test_sync_without_datos_contratacion_record_keeps_fields_blank(self):
		doc = _make_contrato()
		self._sync(doc, _candidate(), None)

		self.assertIsNone(doc.cuenta_bancaria)
		self.assertIsNone(doc.banco_siesa)
		self.assertIsNone(doc.tipo_cuenta_bancaria)

	def test_module_exposes_before_submit_hook(self):
		self.assertTrue(callable(getattr(Contrato, "before_submit", None)))
		self.assertTrue(callable(getattr(contrato_module.Contrato, "_validate_bank_data_before_submit", None)))
