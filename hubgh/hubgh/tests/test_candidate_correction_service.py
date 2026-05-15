# Copyright (c) 2026, Antigravity and contributors
# For license information, please see license.txt

import json
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from frappe.tests.utils import FrappeTestCase

from hubgh.hubgh import candidate_correction_service


class TestGetCorrectionPhase(FrappeTestCase):
	def test_returns_pre_contrato_when_candidato_name_empty(self):
		# Sin nombre → siempre pre_contrato, sin tocar la DB.
		self.assertEqual(candidate_correction_service.get_correction_phase(""), "pre_contrato")
		self.assertEqual(candidate_correction_service.get_correction_phase(None), "pre_contrato")

	def test_returns_pre_contrato_when_candidato_has_no_persona(self):
		with patch(
			"hubgh.hubgh.candidate_correction_service.frappe.db.get_value",
			return_value=None,
		) as get_value_mock, patch(
			"hubgh.hubgh.candidate_correction_service.frappe.db.exists",
		) as exists_mock:
			result = candidate_correction_service.get_correction_phase("CAND-001")

		self.assertEqual(result, "pre_contrato")
		get_value_mock.assert_called_once_with("Candidato", "CAND-001", "persona")
		# Si no hay persona, ni siquiera consultamos Contrato.
		exists_mock.assert_not_called()

	def test_returns_pre_contrato_when_persona_exists_but_no_active_contract(self):
		with patch(
			"hubgh.hubgh.candidate_correction_service.frappe.db.get_value",
			return_value="EMP-001",
		), patch(
			"hubgh.hubgh.candidate_correction_service.frappe.db.exists",
			return_value=None,
		) as exists_mock:
			result = candidate_correction_service.get_correction_phase("CAND-001")

		self.assertEqual(result, "pre_contrato")
		exists_mock.assert_called_once_with(
			"Contrato",
			{"candidato": "CAND-001", "docstatus": 1},
		)

	def test_returns_post_contrato_when_persona_and_submitted_contract_exist(self):
		with patch(
			"hubgh.hubgh.candidate_correction_service.frappe.db.get_value",
			return_value="EMP-001",
		), patch(
			"hubgh.hubgh.candidate_correction_service.frappe.db.exists",
			return_value="CONT-001",
		):
			result = candidate_correction_service.get_correction_phase("CAND-001")

		self.assertEqual(result, "post_contrato")


class TestGetBankCertificationFile(FrappeTestCase):
	def test_returns_none_when_candidato_name_empty(self):
		self.assertIsNone(candidate_correction_service.get_bank_certification_file(""))
		self.assertIsNone(candidate_correction_service.get_bank_certification_file(None))

	def test_returns_none_when_no_attachment(self):
		with patch(
			"hubgh.hubgh.candidate_correction_service.frappe.get_all",
			return_value=[],
		) as get_all_mock:
			result = candidate_correction_service.get_bank_certification_file("CAND-001")

		self.assertIsNone(result)
		get_all_mock.assert_called_once()

	def test_returns_file_url_when_attachment_exists(self):
		with patch(
			"hubgh.hubgh.candidate_correction_service.frappe.get_all",
			return_value=[{"file": "/files/cert.pdf"}],
		) as get_all_mock:
			result = candidate_correction_service.get_bank_certification_file("CAND-001")

		self.assertEqual(result, "/files/cert.pdf")
		# Filtros: person_type, person, document_type LIKE 'Certificación bancaria%'
		call_kwargs = get_all_mock.call_args.kwargs
		self.assertEqual(call_kwargs["filters"]["person_type"], "Candidato")
		self.assertEqual(call_kwargs["filters"]["person"], "CAND-001")
		self.assertEqual(call_kwargs["filters"]["document_type"], ["like", "Certificación bancaria%"])


def _make_correccion_doc(**overrides):
	"""Crea un stand-in del Correccion Datos Candidato sin tocar la DB."""
	defaults = {
		"candidato": "CAND-001",
		"campo_corregido": "email",
		"valor_anterior": "old@example.com",
		"valor_nuevo": "new@example.com",
		"motivo": "Cambio solicitado por candidato",
		"solicitante": "admin@example.com",
		"afectados_resumen": None,
		"fecha_aplicacion": None,
	}
	defaults.update(overrides)
	return SimpleNamespace(**defaults)


class TestApplyEmailChange(FrappeTestCase):
	"""Tests de la cascada email real (Batch 2)."""

	def _patch_common(
		self,
		*,
		candidato_row,
		user_info,
		dup_candidato=None,
		existing_user_exists=False,
	):
		"""Aplica los patches comunes y devuelve un dict con los mocks útiles."""
		module = "hubgh.hubgh.candidate_correction_service"

		validate_patch = patch(f"{module}.validate_email_address")
		get_value_mock = MagicMock(side_effect=lambda dt, name, fields, **kw: (
			candidato_row if dt == "Candidato" else user_info
		))
		# `frappe.db.get_value` se llama dos veces con distintos doctypes; usamos
		# side_effect en orden: primero Candidato, luego User.
		get_value_mock = MagicMock(side_effect=[candidato_row, user_info])
		sql_mock = MagicMock(return_value=dup_candidato or [])
		exists_mock = MagicMock(return_value=existing_user_exists)
		set_value_mock = MagicMock()
		savepoint_mock = MagicMock()
		rollback_mock = MagicMock()

		patches = {
			"validate": validate_patch,
			"get_value": patch(f"{module}.frappe.db.get_value", get_value_mock),
			"sql": patch(f"{module}.frappe.db.sql", sql_mock),
			"exists": patch(f"{module}.frappe.db.exists", exists_mock),
			"set_value": patch(f"{module}.frappe.db.set_value", set_value_mock),
			"savepoint": patch(f"{module}.frappe.db.savepoint", savepoint_mock),
			"rollback": patch(f"{module}.frappe.db.rollback", rollback_mock),
			"rename_doc": patch(f"{module}.frappe.rename_doc"),
			"clear_sessions": patch(f"{module}.frappe.sessions.clear_sessions"),
			"send_activation": patch(f"{module}.send_user_activation_email"),
			"get_doc": patch(
				f"{module}.frappe.get_doc",
				return_value=MagicMock(name="comment_doc", name_="COMMENT-1"),
			),
		}
		started = {key: p.start() for key, p in patches.items()}
		# `MagicMock.name` está reservado, no se puede pasar como kw. Lo seteamos
		# manualmente para que `.name` devuelva el id esperado.
		started["get_doc"].return_value.name = "COMMENT-1"
		self.addCleanup(lambda: [p.stop() for p in patches.values()])
		return started

	def test_happy_path_user_not_activated_resends_welcome(self):
		mocks = self._patch_common(
			candidato_row={"email": "old@example.com", "user": "old@example.com"},
			user_info={"enabled": 1, "last_login": None},
		)
		doc = _make_correccion_doc()

		result = candidate_correction_service._apply_email_change(doc)

		mocks["rename_doc"].assert_called_once_with(
			"User", "old@example.com", "new@example.com",
			merge=False,
		)
		mocks["send_activation"].assert_called_once_with("new@example.com")
		mocks["clear_sessions"].assert_not_called()
		self.assertTrue(result["user_renamed"])
		self.assertTrue(result["welcome_email_resent"])
		self.assertFalse(result["sessions_invalidated"])
		self.assertFalse(result["user_was_active"])
		self.assertEqual(result["user_new"], "new@example.com")
		self.assertEqual(result["comment_id"], "COMMENT-1")

	def test_happy_path_user_active_clears_sessions(self):
		mocks = self._patch_common(
			candidato_row={"email": "old@example.com", "user": "old@example.com"},
			user_info={"enabled": 1, "last_login": "2026-01-01 10:00:00"},
		)
		doc = _make_correccion_doc()

		result = candidate_correction_service._apply_email_change(doc)

		mocks["rename_doc"].assert_called_once()
		mocks["clear_sessions"].assert_called_once_with(user="new@example.com")
		mocks["send_activation"].assert_not_called()
		self.assertTrue(result["user_was_active"])
		self.assertTrue(result["sessions_invalidated"])
		self.assertFalse(result["welcome_email_resent"])

	def test_no_user_linked_only_updates_candidato(self):
		mocks = self._patch_common(
			candidato_row={"email": "old@example.com", "user": None},
			user_info=None,
		)
		doc = _make_correccion_doc()

		result = candidate_correction_service._apply_email_change(doc)

		mocks["rename_doc"].assert_not_called()
		mocks["clear_sessions"].assert_not_called()
		mocks["send_activation"].assert_not_called()
		# Solo set_value sobre Candidato.email.
		mocks["set_value"].assert_called_once_with(
			"Candidato", "CAND-001", "email", "new@example.com"
		)
		self.assertFalse(result["user_updated"])
		self.assertFalse(result["user_renamed"])
		self.assertEqual(result.get("reason"), "no_user_linked")

	def test_invalid_email_raises(self):
		import frappe

		module = "hubgh.hubgh.candidate_correction_service"
		with patch(
			f"{module}.validate_email_address",
			side_effect=frappe.ValidationError("invalid"),
		):
			doc = _make_correccion_doc(valor_nuevo="not-an-email")
			with self.assertRaises(frappe.ValidationError):
				candidate_correction_service._apply_email_change(doc)

	def test_duplicate_email_in_other_candidato_raises(self):
		import frappe

		module = "hubgh.hubgh.candidate_correction_service"
		with patch(f"{module}.validate_email_address"), patch(
			f"{module}.frappe.db.get_value",
			return_value={"email": "old@example.com", "user": "old@example.com"},
		), patch(
			f"{module}.frappe.db.sql",
			return_value=[("CAND-OTRO",)],
		):
			doc = _make_correccion_doc()
			with self.assertRaises(frappe.ValidationError):
				candidate_correction_service._apply_email_change(doc)

	def test_rollback_when_rename_fails(self):
		mocks = self._patch_common(
			candidato_row={"email": "old@example.com", "user": "old@example.com"},
			user_info={"enabled": 0, "last_login": None},
		)
		mocks["rename_doc"].side_effect = RuntimeError("rename boom")

		doc = _make_correccion_doc()
		with self.assertRaises(RuntimeError):
			candidate_correction_service._apply_email_change(doc)

		mocks["rollback"].assert_called_once_with(save_point="email_correction")
		# El Comment no debe insertarse si el rename falló.
		mocks["get_doc"].assert_not_called()
		mocks["send_activation"].assert_not_called()
		mocks["clear_sessions"].assert_not_called()


def _cuenta_payload(
	numero="1234567890",
	tipo="Ahorros",
	banco="BANCOLOMBIA",
):
	return json.dumps({
		"numero_cuenta_bancaria": numero,
		"tipo_cuenta_bancaria": tipo,
		"banco_siesa": banco,
	})


class TestApplyCuentaChange(FrappeTestCase):
	"""Tests de la cascada cuenta bancaria real (Batch 3)."""

	def _patch_common(
		self,
		*,
		candidato_row=None,
		banco_exists=True,
		contratos=None,
		set_value_side_effect=None,
	):
		module = "hubgh.hubgh.candidate_correction_service"
		candidato_row = candidato_row or {
			"numero_cuenta_bancaria": "9999999999",
			"tipo_cuenta_bancaria": "Ahorros",
			"banco_siesa": "BANCO-OLD",
		}

		get_value_mock = MagicMock(return_value=candidato_row)
		# `frappe.db.exists` se llama para validar `Banco Siesa`. Default True.
		exists_mock = MagicMock(return_value=banco_exists)
		get_all_mock = MagicMock(return_value=contratos or [])
		set_value_mock = MagicMock(side_effect=set_value_side_effect)
		savepoint_mock = MagicMock()
		rollback_mock = MagicMock()

		comment_doc = MagicMock()
		comment_doc.name = "COMMENT-CUENTA-1"
		comment_doc.insert = MagicMock(return_value=None)
		get_doc_mock = MagicMock(return_value=comment_doc)

		patches = {
			"get_value": patch(f"{module}.frappe.db.get_value", get_value_mock),
			"exists": patch(f"{module}.frappe.db.exists", exists_mock),
			"get_all": patch(f"{module}.frappe.get_all", get_all_mock),
			"set_value": patch(f"{module}.frappe.db.set_value", set_value_mock),
			"savepoint": patch(f"{module}.frappe.db.savepoint", savepoint_mock),
			"rollback": patch(f"{module}.frappe.db.rollback", rollback_mock),
			"get_doc": patch(f"{module}.frappe.get_doc", get_doc_mock),
			# `parse_json` y `as_json` los dejamos pasar al real de frappe.
		}
		started = {key: p.start() for key, p in patches.items()}
		self.addCleanup(lambda: [p.stop() for p in patches.values()])
		started["comment_doc"] = comment_doc
		return started

	def test_happy_path_without_active_contract(self):
		mocks = self._patch_common(contratos=[])
		doc = _make_correccion_doc(
			campo_corregido="cuenta_bancaria",
			valor_anterior=None,
			valor_nuevo=_cuenta_payload(),
		)

		result = candidate_correction_service._apply_cuenta_change(doc)

		# Candidato actualizado con los 3 campos.
		mocks["set_value"].assert_any_call(
			"Candidato", "CAND-001",
			{
				"numero_cuenta_bancaria": "1234567890",
				"tipo_cuenta_bancaria": "Ahorros",
				"banco_siesa": "BANCOLOMBIA",
			},
		)
		# Sin contratos, set_value se llama una sola vez (solo el Candidato).
		self.assertEqual(mocks["set_value"].call_count, 1)
		self.assertEqual(result["contratos_actualizados"], [])
		self.assertEqual(result["valores_nuevos"]["numero_cuenta_bancaria"], "1234567890")
		self.assertEqual(result["valores_anteriores"]["numero_cuenta_bancaria"], "9999999999")
		self.assertFalse(result["siesa_flag_set"])
		self.assertTrue(result["siesa_comment_added"])
		self.assertEqual(result["comment_id"], "COMMENT-CUENTA-1")

	def test_happy_path_with_submitted_contract(self):
		mocks = self._patch_common(contratos=["CONT-001"])
		doc = _make_correccion_doc(
			campo_corregido="cuenta_bancaria",
			valor_nuevo=_cuenta_payload(),
		)

		result = candidate_correction_service._apply_cuenta_change(doc)

		# Contrato actualizado con cuenta_bancaria (nombre Contrato, NO numero_cuenta_bancaria).
		mocks["set_value"].assert_any_call(
			"Contrato", "CONT-001",
			{
				"cuenta_bancaria": "1234567890",
				"tipo_cuenta_bancaria": "Ahorros",
				"banco_siesa": "BANCOLOMBIA",
			},
		)
		self.assertEqual(result["contratos_actualizados"], ["CONT-001"])

	def test_happy_path_with_multiple_contracts(self):
		mocks = self._patch_common(contratos=["CONT-001", "CONT-002"])
		doc = _make_correccion_doc(
			campo_corregido="cuenta_bancaria",
			valor_nuevo=_cuenta_payload(),
		)

		result = candidate_correction_service._apply_cuenta_change(doc)

		# Una llamada por cada contrato + una para el candidato.
		contrato_calls = [
			c for c in mocks["set_value"].call_args_list
			if c.args and c.args[0] == "Contrato"
		]
		self.assertEqual(len(contrato_calls), 2)
		self.assertEqual(
			sorted(result["contratos_actualizados"]), ["CONT-001", "CONT-002"]
		)

	def test_invalid_json_raises(self):
		import frappe

		self._patch_common(contratos=[])
		doc = _make_correccion_doc(
			campo_corregido="cuenta_bancaria",
			valor_nuevo="{not valid json",
		)
		with self.assertRaises(frappe.ValidationError):
			candidate_correction_service._apply_cuenta_change(doc)

	def test_non_numeric_account_raises(self):
		import frappe

		self._patch_common(contratos=[])
		doc = _make_correccion_doc(
			campo_corregido="cuenta_bancaria",
			valor_nuevo=_cuenta_payload(numero="ABC123"),
		)
		with self.assertRaises(frappe.ValidationError):
			candidate_correction_service._apply_cuenta_change(doc)

	def test_invalid_tipo_cuenta_raises(self):
		import frappe

		self._patch_common(contratos=[])
		doc = _make_correccion_doc(
			campo_corregido="cuenta_bancaria",
			valor_nuevo=_cuenta_payload(tipo="Bitcoin"),
		)
		with self.assertRaises(frappe.ValidationError):
			candidate_correction_service._apply_cuenta_change(doc)

	def test_banco_siesa_not_exists_raises(self):
		import frappe

		self._patch_common(contratos=[], banco_exists=False)
		doc = _make_correccion_doc(
			campo_corregido="cuenta_bancaria",
			valor_nuevo=_cuenta_payload(banco="BANCO-INVENTADO"),
		)
		with self.assertRaises(frappe.ValidationError):
			candidate_correction_service._apply_cuenta_change(doc)

	def test_rollback_when_contrato_set_value_fails(self):
		# Primera llamada (Candidato) OK; segunda (Contrato) falla.
		def _side_effect(doctype, name, *args, **kwargs):
			if doctype == "Contrato":
				raise RuntimeError("contrato boom")

		mocks = self._patch_common(
			contratos=["CONT-001"],
			set_value_side_effect=_side_effect,
		)
		doc = _make_correccion_doc(
			campo_corregido="cuenta_bancaria",
			valor_nuevo=_cuenta_payload(),
		)
		with self.assertRaises(RuntimeError):
			candidate_correction_service._apply_cuenta_change(doc)

		mocks["rollback"].assert_called_once_with(save_point="cuenta_correction")
		# El Comment principal no debe insertarse (la excepción salta antes).
		# get_doc se pudo haber llamado para el comment SIESA del candidato, pero
		# el rollback debería revertir igual. No validamos el conteo exacto.

	def test_siesa_comment_path_when_flag_unavailable(self):
		mocks = self._patch_common(contratos=["CONT-001"])
		doc = _make_correccion_doc(
			campo_corregido="cuenta_bancaria",
			valor_nuevo=_cuenta_payload(),
		)

		result = candidate_correction_service._apply_cuenta_change(doc)

		# Debería haber al menos 3 inserts de Comment:
		#   - 1 comment SIESA en Candidato
		#   - 1 comment SIESA en Contrato CONT-001
		#   - 1 comment auditable principal en Candidato
		self.assertGreaterEqual(mocks["get_doc"].call_count, 3)
		self.assertFalse(result["siesa_flag_set"])
		self.assertTrue(result["siesa_comment_added"])

	def test_missing_keys_fall_back_to_current_candidato_values(self):
		# valor_nuevo solo trae numero; tipo y banco deben heredarse del candidato.
		mocks = self._patch_common(
			candidato_row={
				"numero_cuenta_bancaria": "9999999999",
				"tipo_cuenta_bancaria": "Corriente",
				"banco_siesa": "BANCO-OLD",
			},
			contratos=[],
		)
		doc = _make_correccion_doc(
			campo_corregido="cuenta_bancaria",
			valor_nuevo=json.dumps({"numero_cuenta_bancaria": "1234567890"}),
		)

		result = candidate_correction_service._apply_cuenta_change(doc)

		self.assertEqual(result["valores_nuevos"], {
			"numero_cuenta_bancaria": "1234567890",
			"tipo_cuenta_bancaria": "Corriente",
			"banco_siesa": "BANCO-OLD",
		})
