# Copyright (c) 2026, Antigravity and contributors
# For license information, please see license.txt

"""Tests del endpoint `hubgh.hubgh.api.correcciones` y del controller del DocType.

Convención (igual que test_candidate_correction_service.py): mockeamos `frappe`
en el módulo bajo test. La intención es validar la LÓGICA de transporte
(permission checks, dispatch save vs submit, validaciones de inputs) y la
LÓGICA del controller (recálculo de fase, enforce de rol aprobador), no la
interacción real con la DB.
"""

from __future__ import annotations

import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from hubgh.hubgh.api import correcciones as api
from hubgh.hubgh.doctype.correccion_datos_candidato import (
	correccion_datos_candidato as ctrl,
)


# ---------------------------------------------------------------------------
# Helpers compartidos
# ---------------------------------------------------------------------------

class _FrappeError(Exception):
	pass


class _PermissionError(_FrappeError):
	pass


def _install_frappe_mock(target_module, *, user="solicitante@example.com", roles=None):
	"""Instala un mock de `frappe` sobre `target_module`.

	Devuelve el mock para que el test configure return_values específicos.
	`throw` siempre levanta excepción. `_()` es identidad.
	"""
	mock = MagicMock(name=f"frappe_in_{target_module.__name__}")
	mock.ValidationError = _FrappeError
	mock.PermissionError = _PermissionError
	mock.session = SimpleNamespace(user=user)
	mock.get_roles.return_value = list(roles or [])

	def _throw(msg, exc=None, *a, **kw):
		raise (exc or _FrappeError)(str(msg))

	mock.throw.side_effect = _throw
	# `_` (gettext) se importa también en los módulos; lo monkey-patcheamos.
	target_module._ = lambda s: s
	# parse_json / as_json no necesitan ser inteligentes acá.
	mock.parse_json.side_effect = lambda s: {} if not s else {"_parsed": True}
	mock.as_json.side_effect = lambda obj: "{}" if obj is None else str(obj)
	return mock


# ===========================================================================
# 1) submit_candidate_correction
# ===========================================================================

class TestSubmitCandidateCorrection(unittest.TestCase):
	def setUp(self):
		self.patcher = patch.object(api, "frappe")
		self.frappe = self.patcher.start()
		self.addCleanup(self.patcher.stop)

		self.frappe.ValidationError = _FrappeError
		self.frappe.PermissionError = _PermissionError
		self.frappe.session = SimpleNamespace(user="solicitante@example.com")
		self.frappe.get_roles.return_value = ["HR Selection"]
		self.frappe.db.exists.return_value = True

		def _throw(msg, exc=None, *a, **kw):
			raise (exc or _FrappeError)(str(msg))
		self.frappe.throw.side_effect = _throw
		api._ = lambda s: s
		self.frappe.as_json.side_effect = lambda obj: "JSON" if obj else "{}"
		self.frappe.parse_json.side_effect = lambda s: {"x": 1} if s else {}

	def _make_doc(self, *, fase, name="CORR-CDC-2026-00001"):
		doc = MagicMock(name="correccion_doc")
		doc.name = name
		doc.fase = fase
		doc.afectados_resumen = '{"campo": "email"}'
		return doc

	def test_pre_contrato_applies_immediately(self):
		doc = self._make_doc(fase="pre_contrato")
		self.frappe.get_doc.return_value = doc

		res = api.submit_candidate_correction(
			candidato="12345678",
			campo="email",
			valor_nuevo="nuevo@ej.com",
			motivo="typo",
		)

		doc.insert.assert_called_once_with(ignore_permissions=False)
		doc.reload.assert_called_once()
		doc.submit.assert_called_once()
		self.assertEqual(res["status"], "applied")
		self.assertEqual(res["name"], "CORR-CDC-2026-00001")
		self.assertIsNotNone(res["afectados"])

	def test_post_contrato_stays_pending(self):
		doc = self._make_doc(fase="post_contrato")
		self.frappe.get_doc.return_value = doc

		res = api.submit_candidate_correction(
			candidato="12345678",
			campo="email",
			valor_nuevo="nuevo@ej.com",
			motivo="cambio legítimo",
		)

		doc.insert.assert_called_once()
		doc.submit.assert_not_called()
		self.assertEqual(res["status"], "pending_approval")
		self.assertIsNone(res["afectados"])

	def test_sin_permiso_lanza_permission_error(self):
		self.frappe.get_roles.return_value = ["Employee"]
		with self.assertRaises(_PermissionError):
			api.submit_candidate_correction(
				candidato="12345678",
				campo="email",
				valor_nuevo="a@b.com",
				motivo="x",
			)
		self.frappe.get_doc.assert_not_called()

	def test_campo_invalido_lanza_validation(self):
		with self.assertRaises(_FrappeError):
			api.submit_candidate_correction(
				candidato="12345678",
				campo="telefono",  # no soportado
				valor_nuevo="3001234567",
				motivo="x",
			)

	def test_candidato_inexistente_lanza_validation(self):
		self.frappe.db.exists.return_value = False
		with self.assertRaises(_FrappeError):
			api.submit_candidate_correction(
				candidato="99999",
				campo="email",
				valor_nuevo="a@b.com",
				motivo="x",
			)

	def test_motivo_vacio_lanza_validation(self):
		with self.assertRaises(_FrappeError):
			api.submit_candidate_correction(
				candidato="12345678",
				campo="email",
				valor_nuevo="a@b.com",
				motivo="   ",
			)

	def test_valor_nuevo_vacio_lanza_validation(self):
		with self.assertRaises(_FrappeError):
			api.submit_candidate_correction(
				candidato="12345678",
				campo="email",
				valor_nuevo="",
				motivo="x",
			)

	def test_datos_personales_pre_contrato_happy_path(self):
		"""Submit con campo `datos_personales` pasa el whitelist y aplica directo."""
		doc = self._make_doc(fase="pre_contrato")
		self.frappe.get_doc.return_value = doc

		res = api.submit_candidate_correction(
			candidato="12345678",
			campo="datos_personales",
			valor_nuevo={"nombres": "Carlos", "primer_apellido": "Gomez"},
			motivo="Corrección de nombre",
		)
		doc.submit.assert_called_once()
		self.assertEqual(res["status"], "applied")

	def test_valor_nuevo_dict_se_serializa(self):
		doc = self._make_doc(fase="pre_contrato")
		self.frappe.get_doc.return_value = doc

		api.submit_candidate_correction(
			candidato="12345678",
			campo="cuenta_bancaria",
			valor_nuevo={"numero_cuenta_bancaria": "123456"},
			motivo="cambio cuenta",
		)
		# Verificamos que el payload que llegó a get_doc tenga valor_nuevo serializado.
		payload = self.frappe.get_doc.call_args[0][0]
		self.assertNotIsInstance(payload["valor_nuevo"], dict)


# ===========================================================================
# 2) approve_correction
# ===========================================================================

class TestApproveCorrection(unittest.TestCase):
	def setUp(self):
		self.patcher = patch.object(api, "frappe")
		self.frappe = self.patcher.start()
		self.addCleanup(self.patcher.stop)
		self.frappe.ValidationError = _FrappeError
		self.frappe.PermissionError = _PermissionError

		def _throw(msg, exc=None, *a, **kw):
			raise (exc or _FrappeError)(str(msg))
		self.frappe.throw.side_effect = _throw
		api._ = lambda s: s
		self.frappe.parse_json.side_effect = lambda s: {"ok": True} if s else {}

	def _make_doc(self, *, docstatus=0, fase="post_contrato"):
		doc = MagicMock(name="correccion_doc")
		doc.name = "CORR-CDC-2026-00010"
		doc.docstatus = docstatus
		doc.fase = fase
		doc.afectados_resumen = '{"campo": "cedula"}'
		return doc

	def test_doc_ya_submitted_throws(self):
		self.frappe.get_doc.return_value = self._make_doc(docstatus=1)
		with self.assertRaises(_FrappeError):
			api.approve_correction("CORR-CDC-2026-00010")

	def test_fase_pre_contrato_throws(self):
		self.frappe.get_doc.return_value = self._make_doc(fase="pre_contrato")
		with self.assertRaises(_FrappeError):
			api.approve_correction("CORR-CDC-2026-00010")

	def test_happy_path_aplica(self):
		doc = self._make_doc()
		self.frappe.get_doc.return_value = doc
		res = api.approve_correction("CORR-CDC-2026-00010")
		doc.submit.assert_called_once()
		self.assertEqual(res["status"], "applied")
		self.assertEqual(res["name"], "CORR-CDC-2026-00010")


# ===========================================================================
# 3) Controller — enforcement de rol aprobador en before_submit
# ===========================================================================

class TestControllerBeforeSubmit(unittest.TestCase):
	"""El endpoint approve_correction llama doc.submit(); el chequeo de rol
	está en el controller. Acá lo verificamos directamente."""

	def setUp(self):
		self.patcher = patch.object(ctrl, "frappe")
		self.frappe = self.patcher.start()
		self.addCleanup(self.patcher.stop)
		self.frappe.PermissionError = _PermissionError
		self.frappe.session = SimpleNamespace(user="aprobador@example.com")

		def _throw(msg, exc=None, *a, **kw):
			raise (exc or _FrappeError)(str(msg))
		self.frappe.throw.side_effect = _throw
		ctrl._ = lambda s: s

	def _make_instance(self, **overrides):
		inst = ctrl.CorreccionDatosCandidato.__new__(ctrl.CorreccionDatosCandidato)
		inst.candidato = overrides.get("candidato", "12345678")
		inst.campo_corregido = overrides.get("campo_corregido", "email")
		inst.fase = overrides.get("fase", "post_contrato")
		inst.motivo = overrides.get("motivo", "x")
		inst.solicitante = overrides.get("solicitante", "sol@ej.com")
		inst.aprobador = overrides.get("aprobador", None)
		return inst

	def test_post_contrato_sin_rol_aprobador_throws(self):
		self.frappe.get_roles.return_value = ["HR Selection"]
		inst = self._make_instance()
		with self.assertRaises(_PermissionError):
			inst.before_submit()

	def test_post_contrato_con_gerente_gh_aplica(self):
		self.frappe.get_roles.return_value = ["Gerente GH"]
		inst = self._make_instance()
		with patch.object(ctrl, "apply_correction") as mock_apply:
			inst.before_submit()
		mock_apply.assert_called_once_with(inst)
		self.assertEqual(inst.aprobador, "aprobador@example.com")

	def test_pre_contrato_no_chequea_rol(self):
		self.frappe.get_roles.return_value = ["HR Selection"]  # rol no aprobador
		inst = self._make_instance(fase="pre_contrato")
		with patch.object(ctrl, "apply_correction") as mock_apply:
			inst.before_submit()
		mock_apply.assert_called_once_with(inst)
		# aprobador NO se setea en pre_contrato
		self.assertIsNone(inst.aprobador)

	def test_fase_desconocida_throws(self):
		self.frappe.get_roles.return_value = ["System Manager"]
		inst = self._make_instance(fase="???")
		with self.assertRaises(_FrappeError):
			inst.before_submit()


# ===========================================================================
# 4) get_bank_cert_url
# ===========================================================================

class TestGetBankCertUrl(unittest.TestCase):
	def setUp(self):
		self.patcher = patch.object(api, "frappe")
		self.frappe = self.patcher.start()
		self.addCleanup(self.patcher.stop)
		self.frappe.PermissionError = _PermissionError
		self.frappe.session = SimpleNamespace(user="solicitante@example.com")
		self.frappe.get_roles.return_value = ["HR Selection"]
		self.frappe.has_permission.return_value = True

		def _throw(msg, exc=None, *a, **kw):
			raise (exc or _FrappeError)(str(msg))
		self.frappe.throw.side_effect = _throw
		api._ = lambda s: s

	def test_sin_read_permission_throws(self):
		self.frappe.has_permission.return_value = False
		with self.assertRaises(_PermissionError):
			api.get_bank_cert_url(candidato="12345678")

	def test_candidato_sin_adjunto_devuelve_null(self):
		with patch.object(api, "get_bank_certification_file", return_value=None):
			res = api.get_bank_cert_url(candidato="12345678")
		self.assertEqual(res, {"file_url": None})

	def test_candidato_con_adjunto_devuelve_url(self):
		with patch.object(
			api,
			"get_bank_certification_file",
			return_value="/files/cert.pdf",
		):
			res = api.get_bank_cert_url(candidato="12345678")
		self.assertEqual(res, {"file_url": "/files/cert.pdf"})

	def test_sin_rol_solicitante_throws_antes_de_permission_check(self):
		self.frappe.get_roles.return_value = ["Employee"]
		with self.assertRaises(_PermissionError):
			api.get_bank_cert_url(candidato="12345678")
		self.frappe.has_permission.assert_not_called()


# ===========================================================================
# 5) get_correction_phase_api
# ===========================================================================

class TestGetCorrectionPhaseApi(unittest.TestCase):
	def setUp(self):
		self.patcher = patch.object(api, "frappe")
		self.frappe = self.patcher.start()
		self.addCleanup(self.patcher.stop)
		self.frappe.PermissionError = _PermissionError
		self.frappe.session = SimpleNamespace(user="x@y.com")
		self.frappe.get_roles.return_value = ["HR Selection"]

		def _throw(msg, exc=None, *a, **kw):
			raise (exc or _FrappeError)(str(msg))
		self.frappe.throw.side_effect = _throw
		api._ = lambda s: s

	def test_retorna_fase(self):
		with patch.object(
			api, "get_correction_phase", return_value="post_contrato"
		) as mock_phase:
			res = api.get_correction_phase_api(candidato="12345678")
		mock_phase.assert_called_once_with("12345678")
		self.assertEqual(res, {"fase": "post_contrato"})

	def test_candidato_vacio_throws(self):
		with self.assertRaises(_FrappeError):
			api.get_correction_phase_api(candidato="")

	def test_sin_rol_throws(self):
		self.frappe.get_roles.return_value = []
		with self.assertRaises(_PermissionError):
			api.get_correction_phase_api(candidato="12345678")


# ===========================================================================
# 4) delete_person_document
# ===========================================================================

class TestDeletePersonDocument(unittest.TestCase):
	def setUp(self):
		self.patcher = patch.object(api, "frappe")
		self.frappe = self.patcher.start()
		self.addCleanup(self.patcher.stop)

		self.frappe.ValidationError = _FrappeError
		self.frappe.PermissionError = _PermissionError
		self.frappe.session = SimpleNamespace(user="gh@example.com")
		self.frappe.get_roles.return_value = ["Gestión Humana"]
		self.frappe.db.exists.return_value = True

		def _throw(msg, exc=None, *a, **kw):
			raise (exc or _FrappeError)(str(msg))
		self.frappe.throw.side_effect = _throw
		api._ = lambda s: s

		# get_correction_phase patcheado a pre_contrato por default.
		self.phase_patcher = patch.object(api, "get_correction_phase", return_value="pre_contrato")
		self.get_correction_phase = self.phase_patcher.start()
		self.addCleanup(self.phase_patcher.stop)

	def _make_pdoc(self, *, person_type="Candidato", person="CAND-0001", file_url="/private/files/cedula.pdf"):
		pdoc = MagicMock(name="person_document")
		pdoc.name = "PD-0001"
		pdoc.person_type = person_type
		pdoc.person = person
		pdoc.document_type = "Cedula"
		pdoc.file = file_url
		pdoc.get.side_effect = lambda key: {"uploaded_by": "user@x", "uploaded_on": None}.get(key)
		return pdoc

	def _comment_mock(self):
		comment_builder = MagicMock(name="comment_builder")
		inserted = MagicMock(name="comment_inserted")
		inserted.name = "Comment-0001"
		comment_builder.insert.return_value = inserted
		return comment_builder

	def test_happy_path_borra_pdoc_file_y_registra_audit(self):
		pdoc = self._make_pdoc()
		self.frappe.get_doc.side_effect = [pdoc, self._comment_mock()]
		self.frappe.db.get_value.return_value = "File-Doc-001"  # encuentra el File

		res = api.delete_person_document(
			person_document_name="PD-0001",
			motivo="Subido por error",
		)

		# 1) Person Document borrado.
		# 2) File borrado.
		delete_calls = self.frappe.delete_doc.call_args_list
		self.assertEqual(len(delete_calls), 2)
		self.assertEqual(delete_calls[0][0][:2], ("Person Document", "PD-0001"))
		self.assertEqual(delete_calls[1][0][:2], ("File", "File-Doc-001"))
		# 3) Savepoint + commit; sin rollback.
		self.frappe.db.savepoint.assert_called_once_with("delete_person_doc")
		self.frappe.db.commit.assert_called_once()
		self.frappe.db.rollback.assert_not_called()
		# 4) Resultado.
		self.assertEqual(res["deleted"], "PD-0001")
		self.assertEqual(res["comment_id"], "Comment-0001")
		self.assertTrue(res["file_deleted"])

	def test_sin_rol_autorizado_throws_permission(self):
		self.frappe.get_roles.return_value = ["HR Selection"]  # NO está en _DELETE_DOC_ROLES
		with self.assertRaises(_PermissionError):
			api.delete_person_document(person_document_name="PD-0001", motivo="x")
		self.frappe.delete_doc.assert_not_called()
		self.frappe.db.savepoint.assert_not_called()

	def test_motivo_vacio_throws_validation(self):
		with self.assertRaises(_FrappeError):
			api.delete_person_document(person_document_name="PD-0001", motivo="   ")
		self.frappe.delete_doc.assert_not_called()
		self.frappe.db.savepoint.assert_not_called()

	def test_person_document_inexistente_throws(self):
		self.frappe.db.exists.return_value = False
		with self.assertRaises(_FrappeError):
			api.delete_person_document(person_document_name="PD-NONE", motivo="motivo válido")
		self.frappe.delete_doc.assert_not_called()

	def test_persona_tipo_empleado_bloquea(self):
		pdoc = self._make_pdoc(person_type="Empleado")
		self.frappe.get_doc.return_value = pdoc
		with self.assertRaises(_FrappeError):
			api.delete_person_document(person_document_name="PD-0001", motivo="motivo válido")
		self.frappe.delete_doc.assert_not_called()
		self.frappe.db.savepoint.assert_not_called()

	def test_post_contrato_bloquea(self):
		self.get_correction_phase.return_value = "post_contrato"
		pdoc = self._make_pdoc()
		self.frappe.get_doc.return_value = pdoc
		# db.exists: True para Person Document, True para Candidato.
		self.frappe.db.exists.return_value = True
		with self.assertRaises(_FrappeError):
			api.delete_person_document(person_document_name="PD-0001", motivo="motivo válido")
		self.frappe.delete_doc.assert_not_called()
		self.frappe.db.savepoint.assert_not_called()

	def test_rollback_si_falla_delete_file(self):
		pdoc = self._make_pdoc()
		self.frappe.get_doc.side_effect = [pdoc, self._comment_mock()]
		self.frappe.db.get_value.return_value = "File-Doc-001"

		# Primera delete_doc (Person Document) ok; segunda (File) explota.
		def _delete_side(doctype, name, **kw):
			if doctype == "File":
				raise RuntimeError("disco lleno")
			return None
		self.frappe.delete_doc.side_effect = _delete_side

		with self.assertRaises(RuntimeError):
			api.delete_person_document(person_document_name="PD-0001", motivo="motivo válido")

		self.frappe.db.savepoint.assert_called_once_with("delete_person_doc")
		self.frappe.db.rollback.assert_called_once_with(save_point="delete_person_doc")
		self.frappe.db.commit.assert_not_called()

	def test_sin_archivo_no_intenta_borrar_file(self):
		pdoc = self._make_pdoc(file_url="")
		self.frappe.get_doc.side_effect = [pdoc, self._comment_mock()]

		res = api.delete_person_document(person_document_name="PD-0001", motivo="motivo válido")

		# Solo se borró el Person Document, no hubo segunda llamada a delete_doc para File.
		delete_calls = self.frappe.delete_doc.call_args_list
		self.assertEqual(len(delete_calls), 1)
		self.assertEqual(delete_calls[0][0][:2], ("Person Document", "PD-0001"))
		self.assertFalse(res["file_deleted"])
		self.frappe.db.commit.assert_called_once()

	def test_system_manager_puede_borrar(self):
		self.frappe.get_roles.return_value = ["System Manager"]
		pdoc = self._make_pdoc()
		self.frappe.get_doc.side_effect = [pdoc, self._comment_mock()]
		self.frappe.db.get_value.return_value = "File-Doc-001"

		res = api.delete_person_document(person_document_name="PD-0001", motivo="cleanup")
		self.assertEqual(res["deleted"], "PD-0001")


if __name__ == "__main__":
	unittest.main()
