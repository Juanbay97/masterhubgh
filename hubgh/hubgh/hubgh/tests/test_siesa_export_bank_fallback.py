# Copyright (c) 2026, Antigravity and contributors
# For license information, please see license.txt

"""
Regression tests for the bank-data fallback of the SIESA contract export.

Production incident (candidate 1032391786, contract CONT--10516): the contract
was submitted before the bank data existed, so ``Contrato.cuenta_bancaria``,
``banco_siesa`` and ``tipo_cuenta_bancaria`` stayed blank forever (not
allow_on_submit). The bank data was later captured on Candidato and on Datos
Contratacion, but ``_build_contract_context`` only read the contract and kept
failing with "Faltan: CUENTA BANCARIA, ID BANCO EMPLEADO".

These tests are pure (no site, no DB): the module-level ``frappe`` attribute of
``hubgh.hubgh.siesa_export`` is patched, mirroring the mock style of
``hubgh/page/seleccion_documentos/test_seleccion_documentos.py``.
"""

from unittest import TestCase
from unittest.mock import MagicMock, patch

import frappe

from hubgh.hubgh import siesa_export


CANDIDATO = "1032391786"
CONTRATO = "CONT--10516"
EMPLEADO = "FE-0001"

BANK_ON_CONTRACT = {
	"cuenta_bancaria": "111-222-333",
	"banco_siesa": "Bancolombia",
	"tipo_cuenta_bancaria": "Ahorros",
}
BANK_ON_SOURCE = {
	"numero_cuenta_bancaria": "525-971625-29",
	"banco_siesa": "Davivienda",
	"tipo_cuenta_bancaria": "Corriente",
}
BLANK_BANK_ON_SOURCE = {
	"numero_cuenta_bancaria": None,
	"banco_siesa": "",
	"tipo_cuenta_bancaria": None,
}


def _make_contrato(bank=None, empleado=EMPLEADO):
	doc = frappe._dict(
		{
			"name": CONTRATO,
			"doctype": "Contrato",
			"numero_documento": CANDIDATO,
			"candidato": CANDIDATO,
			"empleado": empleado,
			"pdv_destino": "PDV-01",
			"cargo": "Cocinero",
			"tipo_contrato": "Fijo",
			"estado_contrato": "Activo",
			"salario": 1500000,
			"horas_trabajadas_mes": 220,
			"fecha_ingreso": "2026-08-01",
			"fecha_fin_contrato": "2026-12-31",
			"entidad_ccf_siesa": "CCF",
			"cuenta_bancaria": None,
			"banco_siesa": None,
			"tipo_cuenta_bancaria": None,
		}
	)
	doc.update(bank or {})
	return doc


def _make_candidato(bank=None):
	doc = frappe._dict(
		{
			"name": CANDIDATO,
			"doctype": "Candidato",
			"numero_documento": CANDIDATO,
			"ccf_siesa": "CCF",
			"es_extranjero": 0,
			"personas_a_cargo": 0,
		}
	)
	doc.update(BLANK_BANK_ON_SOURCE)
	doc.update(bank or {})
	return doc


def _make_datos_contratacion(bank=None):
	doc = frappe._dict(
		{
			"name": "DC-0001",
			"doctype": "Datos Contratacion",
			"candidato": CANDIDATO,
			"contrato": CONTRATO,
			"ccf_siesa": "CCF",
			"aplica_auxilio_transporte": "3",
			"es_extranjero": 0,
		}
	)
	doc.update(BLANK_BANK_ON_SOURCE)
	doc.update(bank or {})
	return doc


class _Fixture:
	"""In-memory stand-in for the ``frappe`` calls issued by ``_build_contract_context``."""

	def __init__(self, contrato, candidato, employee_bank=None, employee_exists=True):
		self.contrato = contrato
		self.candidato = candidato
		self.employee_bank = employee_bank
		self.employee_exists = employee_exists

	def get_doc(self, doctype, name=None):
		if doctype == "Contrato":
			return self.contrato
		if doctype == "Candidato":
			return self.candidato
		raise AssertionError(f"unexpected get_doc({doctype!r}, {name!r})")

	def exists(self, doctype, name=None):
		if doctype == "Contrato":
			return name == CONTRATO
		if doctype == "Ficha Empleado":
			return self.employee_exists and name == EMPLEADO
		return False

	def get_value(self, doctype, name=None, fieldname=None, **kwargs):
		if doctype in ("Punto de Venta", "Cargo"):
			return "CODE"
		if doctype == "Ficha Empleado":
			self.assert_employee_lookup_shape(fieldname, kwargs)
			return frappe._dict(self.employee_bank or {})
		raise AssertionError(f"unexpected get_value({doctype!r}, {name!r}, {fieldname!r})")

	@staticmethod
	def assert_employee_lookup_shape(fieldname, kwargs):
		if not kwargs.get("as_dict"):
			raise AssertionError("Ficha Empleado bank fields must be read with as_dict=True")
		if not isinstance(fieldname, (list, tuple)):
			raise AssertionError("Ficha Empleado bank fields must be read as a field list")


class SiesaExportBankFallbackTest(TestCase):
	def _run(self, fixture, data):
		mock_frappe = MagicMock()
		mock_frappe.get_doc.side_effect = fixture.get_doc
		mock_frappe.db.exists.side_effect = fixture.exists
		mock_frappe.db.get_value.side_effect = fixture.get_value
		mock_frappe.throw.side_effect = frappe.exceptions.ValidationError

		def fake_resolve_bank(bank_name):
			return ("07", "1007") if bank_name else ("", "")

		with (
			patch("hubgh.hubgh.siesa_export.frappe", mock_frappe),
			patch("hubgh.hubgh.siesa_export.get_or_create_affiliation", return_value=None),
			patch(
				"hubgh.hubgh.siesa_export._resolve_retirement_export_context",
				return_value={"fecha_retiro": "", "id_motivo_retiro": "", "ind_estado": "0"},
			),
			patch("hubgh.hubgh.siesa_export._catalog_code", side_effect=lambda doctype, value: "01" if value else ""),
			patch("hubgh.hubgh.siesa_export._resolve_id_banco_empleado", side_effect=fake_resolve_bank) as resolve_bank,
		):
			ctx, missing = siesa_export._build_contract_context(data)

		return ctx, missing, mock_frappe, resolve_bank

	@staticmethod
	def _set_value_calls(mock_frappe, doctype):
		return [call for call in mock_frappe.db.set_value.call_args_list if call.args[0] == doctype]

	def test_contract_bank_data_is_used_as_is_without_healing(self):
		contrato = _make_contrato(bank=BANK_ON_CONTRACT)
		fixture = _Fixture(contrato, _make_candidato(bank=BANK_ON_SOURCE), employee_bank=BANK_ON_SOURCE)
		data = _make_datos_contratacion(bank=BANK_ON_SOURCE)

		ctx, missing, mock_frappe, resolve_bank = self._run(fixture, data)

		self.assertEqual(ctx["cuenta_bancaria"], "111222333")
		self.assertEqual(ctx["ind_tipo_cuenta"], "1")
		self.assertEqual(ctx["id_banco_empleado"], "07")
		resolve_bank.assert_called_once_with("Bancolombia")
		self.assertNotIn("CUENTA BANCARIA", missing)
		self.assertNotIn("ID BANCO EMPLEADO", missing)
		self.assertNotIn("IND TIPO CUENTA", missing)
		mock_frappe.db.set_value.assert_not_called()

	def test_blank_contract_falls_back_to_datos_contratacion_and_heals_contract_and_employee(self):
		contrato = _make_contrato()
		fixture = _Fixture(
			contrato,
			_make_candidato(bank={"numero_cuenta_bancaria": "999", "banco_siesa": "Otro", "tipo_cuenta_bancaria": "Ahorros"}),
			employee_bank=BLANK_BANK_ON_SOURCE,
		)
		data = _make_datos_contratacion(bank=BANK_ON_SOURCE)

		ctx, missing, mock_frappe, resolve_bank = self._run(fixture, data)

		# Datos Contratacion wins over Candidato; export cell has separators stripped.
		self.assertEqual(ctx["cuenta_bancaria"], "52597162529")
		self.assertEqual(ctx["ind_tipo_cuenta"], "2")
		self.assertEqual(ctx["id_banco_empleado"], "07")
		resolve_bank.assert_called_once_with("Davivienda")
		self.assertNotIn("CUENTA BANCARIA", missing)
		self.assertNotIn("ID BANCO EMPLEADO", missing)

		# In-memory contract object healed.
		self.assertEqual(contrato.cuenta_bancaria, "525-971625-29")
		self.assertEqual(contrato.banco_siesa, "Davivienda")
		self.assertEqual(contrato.tipo_cuenta_bancaria, "Corriente")

		contract_calls = self._set_value_calls(mock_frappe, "Contrato")
		self.assertEqual(len(contract_calls), 1)
		self.assertEqual(contract_calls[0].args[1], CONTRATO)
		self.assertEqual(
			contract_calls[0].args[2],
			{
				"cuenta_bancaria": "525-971625-29",
				"banco_siesa": "Davivienda",
				"tipo_cuenta_bancaria": "Corriente",
			},
		)
		self.assertFalse(contract_calls[0].kwargs.get("update_modified", True))

		employee_calls = self._set_value_calls(mock_frappe, "Ficha Empleado")
		self.assertEqual(len(employee_calls), 1)
		self.assertEqual(employee_calls[0].args[1], EMPLEADO)
		self.assertEqual(
			employee_calls[0].args[2],
			{
				"numero_cuenta_bancaria": "525-971625-29",
				"banco_siesa": "Davivienda",
				"tipo_cuenta_bancaria": "Corriente",
			},
		)
		self.assertFalse(employee_calls[0].kwargs.get("update_modified", True))

	def test_employee_heal_writes_only_blank_fields(self):
		contrato = _make_contrato()
		fixture = _Fixture(
			contrato,
			_make_candidato(),
			employee_bank={"numero_cuenta_bancaria": "777", "banco_siesa": "", "tipo_cuenta_bancaria": None},
		)
		data = _make_datos_contratacion(bank=BANK_ON_SOURCE)

		_ctx, _missing, mock_frappe, _resolve_bank = self._run(fixture, data)

		employee_calls = self._set_value_calls(mock_frappe, "Ficha Empleado")
		self.assertEqual(len(employee_calls), 1)
		self.assertEqual(
			employee_calls[0].args[2],
			{"banco_siesa": "Davivienda", "tipo_cuenta_bancaria": "Corriente"},
		)

	def test_no_employee_heal_when_contract_has_no_linked_employee(self):
		contrato = _make_contrato(empleado=None)
		fixture = _Fixture(contrato, _make_candidato(), employee_exists=False)
		data = _make_datos_contratacion(bank=BANK_ON_SOURCE)

		_ctx, missing, mock_frappe, _resolve_bank = self._run(fixture, data)

		self.assertNotIn("CUENTA BANCARIA", missing)
		self.assertEqual(self._set_value_calls(mock_frappe, "Ficha Empleado"), [])
		self.assertEqual(len(self._set_value_calls(mock_frappe, "Contrato")), 1)

	def test_blank_contract_and_datos_falls_back_to_candidato_and_heals(self):
		contrato = _make_contrato()
		fixture = _Fixture(contrato, _make_candidato(bank=BANK_ON_SOURCE), employee_bank=BLANK_BANK_ON_SOURCE)
		data = _make_datos_contratacion()

		ctx, missing, mock_frappe, resolve_bank = self._run(fixture, data)

		self.assertEqual(ctx["cuenta_bancaria"], "52597162529")
		self.assertEqual(ctx["ind_tipo_cuenta"], "2")
		self.assertEqual(ctx["id_banco_empleado"], "07")
		resolve_bank.assert_called_once_with("Davivienda")
		self.assertNotIn("CUENTA BANCARIA", missing)
		self.assertNotIn("ID BANCO EMPLEADO", missing)
		self.assertEqual(contrato.cuenta_bancaria, "525-971625-29")

		contract_calls = self._set_value_calls(mock_frappe, "Contrato")
		self.assertEqual(len(contract_calls), 1)
		self.assertEqual(
			contract_calls[0].args[2],
			{
				"cuenta_bancaria": "525-971625-29",
				"banco_siesa": "Davivienda",
				"tipo_cuenta_bancaria": "Corriente",
			},
		)
		self.assertEqual(len(self._set_value_calls(mock_frappe, "Ficha Empleado")), 1)

	def test_partial_contract_only_heals_blank_contract_fields(self):
		contrato = _make_contrato(bank={"cuenta_bancaria": "111.222.333"})
		fixture = _Fixture(contrato, _make_candidato(bank=BANK_ON_SOURCE), employee_bank=BANK_ON_SOURCE)
		data = _make_datos_contratacion()

		ctx, _missing, mock_frappe, _resolve_bank = self._run(fixture, data)

		self.assertEqual(ctx["cuenta_bancaria"], "111222333")
		contract_calls = self._set_value_calls(mock_frappe, "Contrato")
		self.assertEqual(len(contract_calls), 1)
		self.assertEqual(
			contract_calls[0].args[2],
			{"banco_siesa": "Davivienda", "tipo_cuenta_bancaria": "Corriente"},
		)

	def test_missing_everywhere_reports_required_bank_fields(self):
		contrato = _make_contrato()
		fixture = _Fixture(contrato, _make_candidato(), employee_bank=BLANK_BANK_ON_SOURCE)
		data = _make_datos_contratacion()

		ctx, missing, mock_frappe, _resolve_bank = self._run(fixture, data)

		self.assertEqual(ctx["cuenta_bancaria"], "")
		self.assertIn("CUENTA BANCARIA", missing)
		self.assertIn("ID BANCO EMPLEADO", missing)
		self.assertIn("IND TIPO CUENTA", missing)
		mock_frappe.db.set_value.assert_not_called()
