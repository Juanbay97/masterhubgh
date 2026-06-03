# Copyright (c) 2026, Antigravity and contributors
# For license information, please see license.txt

"""
Tests para hubgh.hubgh.candidate_correction_service.

Estos tests usan mocks de `frappe` (no DB real) porque la cascada de corrección
cruza varios DocTypes con FKs y autoname por cédula, lo cual sería muy caro de
montar en un FrappeTestCase clásico. La intención es validar la LÓGICA del
servicio: orden de validaciones, llamadas a rename_doc/set_value, rollback,
bloqueos por afiliación, etc.
"""

from __future__ import annotations

import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock, patch, call

from hubgh.hubgh import candidate_correction_service as ccs


def _make_doc(**overrides):
	"""Helper: arma un fake `Correccion Datos Candidato` con los campos mínimos."""
	defaults = {
		"candidato": "12345678",
		"campo_corregido": "cedula",
		"valor_nuevo": "87654321",
		"motivo": "Error de digitación",
		"solicitante": "tester@example.com",
	}
	defaults.update(overrides)
	return SimpleNamespace(**defaults)


class TestApplyCedulaChange(unittest.TestCase):
	"""Tests de la cascada real de corrección de cédula (Batch 4)."""

	def setUp(self):
		# Patch global de frappe dentro del módulo bajo test. Cada test
		# configura los return_values que necesita.
		self.patcher = patch.object(ccs, "frappe")
		self.frappe = self.patcher.start()
		self.addCleanup(self.patcher.stop)

		# `rename_doc_unrestricted` se importa por separado (no es atributo de
		# frappe), así que se patchea aparte. El código usa la función de bajo
		# nivel con `ignore_permissions=True` en vez de `frappe.rename_doc`.
		self.rename_patcher = patch.object(ccs, "rename_doc_unrestricted")
		self.rename_doc = self.rename_patcher.start()
		self.addCleanup(self.rename_patcher.stop)

		# `frappe.throw` debe levantar excepción; por defecto Mock no levanta.
		def _throw(msg, *args, **kwargs):
			raise ccs.frappe.ValidationError(str(msg))
		self.frappe.throw.side_effect = _throw
		self.frappe.ValidationError = type("ValidationError", (Exception,), {})
		# `_()` es identidad para tests.
		self.frappe._ = lambda s: s
		# Reusar el `_` que importa el módulo.
		self._orig_underscore = ccs._
		ccs._ = lambda s: s

	def tearDown(self):
		ccs._ = self._orig_underscore

	# ---------- helpers ----------

	def _setup_basic_candidato(
		self,
		old_cedula="12345678",
		persona="12345678",
		user="user@example.com",
	):
		"""Configura `frappe.db.get_value("Candidato", ...)` para devolver el estado base."""
		def _get_value(doctype, name, fields=None, **kwargs):
			if doctype == "Candidato" and fields == ["numero_documento", "persona", "user"]:
				return {
					"numero_documento": old_cedula,
					"persona": persona,
					"user": user,
				}
			return None
		self.frappe.db.get_value.side_effect = _get_value

	def _setup_no_dups_no_blocks(self):
		"""Por defecto: no hay duplicados, no hay afiliaciones bloqueantes."""
		self.frappe.db.exists.return_value = False
		self.frappe.get_all.return_value = []  # sin afiliaciones

	# ---------- tests ----------

	def test_happy_path_full(self):
		"""Candidato + Ficha + User, sin afiliaciones → cascada completa."""
		self._setup_basic_candidato()
		self._setup_no_dups_no_blocks()
		# `User` existe para el set_value de username.
		self.frappe.db.exists.side_effect = lambda dt, *a, **kw: (dt == "User")

		comment_mock = MagicMock(name="CommentDoc")
		comment_mock.name = "COMMENT-001"
		self.frappe.get_doc.return_value.insert.return_value = comment_mock
		self.frappe.get_doc.return_value.name = "COMMENT-001"

		doc = _make_doc(valor_nuevo="87654321")
		result = ccs._apply_cedula_change(doc)

		# Validaciones clave de la cascada:
		# 1. rename del Candidato.
		self.rename_doc.assert_any_call(
			"Candidato", "12345678", "87654321", merge=False, ignore_permissions=True,
		)
		# 2. rename de la Ficha Empleado.
		self.rename_doc.assert_any_call(
			"Ficha Empleado", "12345678", "87654321", merge=False, ignore_permissions=True,
		)
		# 3. set_value de User.username (NO rename).
		self.frappe.db.set_value.assert_any_call("User", "user@example.com", "username", "87654321")

		# 4. Comment auditable insertado.
		self.frappe.get_doc.assert_called()

		# 5. Savepoint y NO rollback.
		self.frappe.db.savepoint.assert_called_once_with("cedula_correction")
		self.frappe.db.rollback.assert_not_called()

		# 6. Resumen retornado.
		self.assertEqual(result["campo"], "cedula")
		self.assertEqual(result["candidato_new"], "87654321")
		self.assertEqual(result["ficha_empleado_new"], "87654321")
		self.assertTrue(result["ficha_empleado_renamed"])
		self.assertTrue(result["user_username_actualizado"])

	def test_sin_ficha_empleado(self):
		"""Candidato sin Ficha vinculada → no se llama rename de Ficha."""
		self._setup_basic_candidato(persona=None)
		self._setup_no_dups_no_blocks()
		self.frappe.db.exists.side_effect = lambda dt, *a, **kw: (dt == "User")

		comment_mock = MagicMock()
		comment_mock.name = "COMMENT-002"
		self.frappe.get_doc.return_value.insert.return_value = comment_mock
		self.frappe.get_doc.return_value.name = "COMMENT-002"

		doc = _make_doc(valor_nuevo="87654321")
		result = ccs._apply_cedula_change(doc)

		# rename_doc se llama UNA sola vez (Candidato), no para Ficha.
		rename_calls = [c.args[0] for c in self.rename_doc.call_args_list]
		self.assertIn("Candidato", rename_calls)
		self.assertNotIn("Ficha Empleado", rename_calls)
		self.assertFalse(result["ficha_empleado_renamed"])
		self.assertIsNone(result["ficha_empleado_new"])

	def test_sin_user_vinculado(self):
		"""Candidato sin User → no se actualiza username."""
		self._setup_basic_candidato(user=None)
		self._setup_no_dups_no_blocks()
		self.frappe.db.exists.return_value = False

		comment_mock = MagicMock()
		comment_mock.name = "COMMENT-003"
		self.frappe.get_doc.return_value.insert.return_value = comment_mock
		self.frappe.get_doc.return_value.name = "COMMENT-003"

		doc = _make_doc(valor_nuevo="87654321")
		result = ccs._apply_cedula_change(doc)

		# No debe haber set_value("User", ..., "username", ...).
		user_set_calls = [
			c for c in self.frappe.db.set_value.call_args_list
			if c.args and c.args[0] == "User"
		]
		self.assertEqual(user_set_calls, [])
		self.assertFalse(result["user_username_actualizado"])

	def test_cedula_no_numerica(self):
		"""valor_nuevo con letras → ValidationError antes de tocar DB."""
		doc = _make_doc(valor_nuevo="ABC123XYZ")
		with self.assertRaises(self.frappe.ValidationError):
			ccs._apply_cedula_change(doc)
		# No debe haberse abierto savepoint.
		self.frappe.db.savepoint.assert_not_called()

	def test_cedula_corta(self):
		"""valor_nuevo con menos de 6 dígitos → ValidationError."""
		doc = _make_doc(valor_nuevo="12345")
		with self.assertRaises(self.frappe.ValidationError):
			ccs._apply_cedula_change(doc)

	def test_cedula_demasiado_larga(self):
		"""valor_nuevo con más de 12 dígitos → ValidationError."""
		doc = _make_doc(valor_nuevo="1234567890123")
		with self.assertRaises(self.frappe.ValidationError):
			ccs._apply_cedula_change(doc)

	def test_cedula_igual_a_actual(self):
		"""Si la nueva cédula es igual a la actual → error."""
		self._setup_basic_candidato(old_cedula="87654321")
		self._setup_no_dups_no_blocks()
		doc = _make_doc(valor_nuevo="87654321")
		with self.assertRaises(self.frappe.ValidationError):
			ccs._apply_cedula_change(doc)

	def test_duplicada_en_otro_candidato(self):
		"""Si otro Candidato ya tiene esa cédula → ValidationError."""
		self._setup_basic_candidato()
		# Primera llamada a `exists` (Candidato) devuelve True.
		def _exists(dt, *a, **kw):
			if dt == "Candidato":
				return True
			return False
		self.frappe.db.exists.side_effect = _exists
		self.frappe.get_all.return_value = []

		doc = _make_doc(valor_nuevo="87654321")
		with self.assertRaises(self.frappe.ValidationError):
			ccs._apply_cedula_change(doc)
		# No debe haber llegado al savepoint.
		self.frappe.db.savepoint.assert_not_called()

	def test_duplicada_en_otra_ficha_empleado(self):
		"""Si otra Ficha Empleado ya tiene esa cédula → ValidationError."""
		self._setup_basic_candidato()

		def _exists(dt, *a, **kw):
			if dt == "Candidato":
				return False
			if dt == "Ficha Empleado":
				return True
			return False
		self.frappe.db.exists.side_effect = _exists
		self.frappe.get_all.return_value = []

		doc = _make_doc(valor_nuevo="87654321")
		with self.assertRaises(self.frappe.ValidationError):
			ccs._apply_cedula_change(doc)
		self.frappe.db.savepoint.assert_not_called()

	def test_bloqueo_por_afiliacion_no_pendiente(self):
		"""Si hay Afiliacion en estado 'Completado' → ValidationError con detalle."""
		self._setup_basic_candidato()
		self.frappe.db.exists.return_value = False
		self.frappe.get_all.return_value = [
			{"name": "AFIL-12345678", "estado_general": "Completado"},
		]

		doc = _make_doc(valor_nuevo="87654321")
		with self.assertRaises(self.frappe.ValidationError) as ctx:
			ccs._apply_cedula_change(doc)

		# Mensaje debe mencionar la afiliación afectada.
		self.assertIn("AFIL-12345678", str(ctx.exception))
		# No debe haber abierto savepoint ni renombrado nada.
		self.frappe.db.savepoint.assert_not_called()
		self.rename_doc.assert_not_called()

	def test_bloqueo_por_afiliacion_en_proceso(self):
		"""Si hay Afiliacion en estado 'En Proceso' → también bloquea."""
		self._setup_basic_candidato()
		self.frappe.db.exists.return_value = False
		self.frappe.get_all.return_value = [
			{"name": "AFIL-12345678", "estado_general": "En Proceso"},
		]

		doc = _make_doc(valor_nuevo="87654321")
		with self.assertRaises(self.frappe.ValidationError):
			ccs._apply_cedula_change(doc)

	def test_afiliacion_pendiente_no_bloquea(self):
		"""Afiliacion en estado 'Pendiente' NO debe bloquear (tramite todavía no externalizado)."""
		self._setup_basic_candidato()
		self.frappe.db.exists.side_effect = lambda dt, *a, **kw: (dt == "User")
		self.frappe.get_all.return_value = [
			{"name": "AFIL-12345678", "estado_general": "Pendiente"},
		]

		comment_mock = MagicMock()
		comment_mock.name = "COMMENT-004"
		self.frappe.get_doc.return_value.insert.return_value = comment_mock
		self.frappe.get_doc.return_value.name = "COMMENT-004"

		doc = _make_doc(valor_nuevo="87654321")
		# No debe levantar.
		result = ccs._apply_cedula_change(doc)
		self.assertEqual(result["afiliaciones_revisadas"], ["AFIL-12345678"])

	def test_rollback_si_falla_rename_ficha(self):
		"""Si rename_doc de Ficha falla → rollback al savepoint."""
		self._setup_basic_candidato()
		self._setup_no_dups_no_blocks()
		self.frappe.db.exists.side_effect = lambda dt, *a, **kw: (dt == "User")

		# Primera llamada (Candidato) ok; segunda (Ficha) explota.
		def _rename(*args, **kwargs):
			if args[0] == "Ficha Empleado":
				raise RuntimeError("simulated rename failure")
			return None
		self.rename_doc.side_effect = _rename

		doc = _make_doc(valor_nuevo="87654321")
		with self.assertRaises(RuntimeError):
			ccs._apply_cedula_change(doc)

		# Rollback debe haber sido llamado con el savepoint correcto.
		self.frappe.db.rollback.assert_called_once_with(save_point="cedula_correction")

	def test_ficha_rename_usa_rename_doc_no_set_value(self):
		"""
		Verifica explícitamente que para Ficha Empleado se use rename_doc (porque
		`autoname=format:{cedula}` → name = cedula como PK), no un set_value
		ingenuo que dejaría .name desincronizado de .cedula.
		"""
		self._setup_basic_candidato()
		self._setup_no_dups_no_blocks()
		self.frappe.db.exists.side_effect = lambda dt, *a, **kw: (dt == "User")

		comment_mock = MagicMock()
		comment_mock.name = "COMMENT-005"
		self.frappe.get_doc.return_value.insert.return_value = comment_mock
		self.frappe.get_doc.return_value.name = "COMMENT-005"

		doc = _make_doc(valor_nuevo="87654321")
		ccs._apply_cedula_change(doc)

		# rename_doc llamado con Ficha Empleado.
		ficha_rename_calls = [
			c for c in self.rename_doc.call_args_list
			if c.args and c.args[0] == "Ficha Empleado"
		]
		self.assertEqual(len(ficha_rename_calls), 1)


class TestApplyPersonalDataChange(unittest.TestCase):
	"""Tests de la cascada de corrección de datos personales (extensión)."""

	def setUp(self):
		self.patcher = patch.object(ccs, "frappe")
		self.frappe = self.patcher.start()
		self.addCleanup(self.patcher.stop)

		def _throw(msg, *args, **kwargs):
			raise ccs.frappe.ValidationError(str(msg))
		self.frappe.throw.side_effect = _throw
		self.frappe.ValidationError = type("ValidationError", (Exception,), {})
		self.frappe._ = lambda s: s
		self._orig_underscore = ccs._
		ccs._ = lambda s: s

		# `parse_json` por defecto interpreta dict literal o str JSON simple.
		def _parse_json(s):
			if isinstance(s, dict):
				return s
			if not s:
				return None
			import json
			return json.loads(s)
		self.frappe.parse_json.side_effect = _parse_json
		self.frappe.as_json.side_effect = lambda obj: "JSON" if obj is None else str(obj)

		# Utilidades de fechas/utilidades — pasar a `frappe.utils`.
		from datetime import date, timedelta
		self._today = date(2026, 5, 14)
		self.frappe.utils.getdate.side_effect = lambda v: (
			v if isinstance(v, date) else date.fromisoformat(str(v))
		)
		self.frappe.utils.nowdate.return_value = self._today.isoformat()

	def tearDown(self):
		ccs._ = self._orig_underscore

	# ---------- helpers ----------

	def _setup_candidato(self, *, user="x@y.com", persona="12345678", **overrides):
		row = {f: None for f in ccs.PERSONAL_DATA_FIELDS}
		row.update({
			"nombres": "Juan",
			"primer_apellido": "Perez",
			"segundo_apellido": "Lopez",
			"apellidos": "Perez Lopez",
			"fecha_nacimiento": "1990-01-01",
			"genero": "Masculino",
			"estado_civil": "Soltero",
			"ciudad": "Bogotá",
			"direccion": "Calle 1",
			"es_extranjero": 0,
			"user": user,
			"persona": persona,
		})
		row.update(overrides)
		self.frappe.db.get_value.return_value = row

	def _setup_no_extras(self):
		self.frappe.db.exists.return_value = True
		self.frappe.get_all.return_value = []

	def _setup_comment(self, comment_name="COMMENT-PD-1"):
		comment_mock = MagicMock()
		comment_mock.name = comment_name
		self.frappe.get_doc.return_value.insert.return_value = comment_mock
		self.frappe.get_doc.return_value.name = comment_name

	def _doc(self, payload):
		import json
		return SimpleNamespace(
			candidato="12345678",
			campo_corregido="datos_personales",
			valor_nuevo=json.dumps(payload),
			motivo="Corrección",
			solicitante="tester@example.com",
		)

	# ---------- tests ----------

	def test_happy_path_solo_nombres_cascadea_user_y_ficha(self):
		self._setup_candidato()
		self._setup_no_extras()
		self._setup_comment()

		result = ccs._apply_personal_data_change(
			self._doc({"nombres": "Carlos", "primer_apellido": "Gomez"})
		)

		# Candidato actualizado con dict.
		candidato_calls = [
			c for c in self.frappe.db.set_value.call_args_list
			if c.args and c.args[0] == "Candidato"
		]
		self.assertTrue(candidato_calls)
		# User actualizado.
		user_calls = [
			c for c in self.frappe.db.set_value.call_args_list
			if c.args and c.args[0] == "User"
		]
		self.assertEqual(len(user_calls), 1)
		user_payload = user_calls[0].args[2]
		self.assertEqual(user_payload["first_name"], "Carlos")
		# Ficha Empleado actualizada.
		ficha_calls = [
			c for c in self.frappe.db.set_value.call_args_list
			if c.args and c.args[0] == "Ficha Empleado"
		]
		self.assertEqual(len(ficha_calls), 1)
		ficha_payload = ficha_calls[0].args[2]
		self.assertEqual(ficha_payload.get("nombres"), "Carlos")
		# Resumen.
		self.assertTrue(result["user_actualizado"])
		self.assertIn("nombres", result["campos_cambiados"])

	def test_happy_path_solo_fechas_no_toca_user(self):
		self._setup_candidato()
		self._setup_no_extras()
		self._setup_comment()

		result = ccs._apply_personal_data_change(
			self._doc({"fecha_nacimiento": "1985-06-15"})
		)
		user_calls = [
			c for c in self.frappe.db.set_value.call_args_list
			if c.args and c.args[0] == "User"
		]
		self.assertFalse(user_calls)
		self.assertFalse(result["user_actualizado"])

	def test_happy_path_mix_solo_envia_cambios(self):
		self._setup_candidato()
		self._setup_no_extras()
		self._setup_comment()

		ccs._apply_personal_data_change(
			self._doc({"celular": "3001234567", "genero": "Femenino"})
		)
		# Verificar payload aplicado al Candidato contiene SOLO esas keys.
		candidato_call = [
			c for c in self.frappe.db.set_value.call_args_list
			if c.args and c.args[0] == "Candidato"
		][0]
		payload = candidato_call.args[2]
		self.assertEqual(set(payload.keys()), {"celular", "genero"})

	def test_nombres_vacio_throws(self):
		self._setup_candidato()
		self._setup_no_extras()
		self._setup_comment()
		with self.assertRaises(self.frappe.ValidationError):
			ccs._apply_personal_data_change(self._doc({"nombres": ""}))

	def test_fecha_nacimiento_futura_throws(self):
		self._setup_candidato()
		self._setup_no_extras()
		self._setup_comment()
		with self.assertRaises(self.frappe.ValidationError):
			ccs._apply_personal_data_change(
				self._doc({"fecha_nacimiento": "2099-01-01"})
			)

	def test_genero_invalido_throws(self):
		self._setup_candidato()
		self._setup_no_extras()
		self._setup_comment()
		with self.assertRaises(self.frappe.ValidationError):
			ccs._apply_personal_data_change(self._doc({"genero": "Marciano"}))

	def test_nivel_educativo_inexistente_throws(self):
		self._setup_candidato()
		self._setup_no_extras()
		self._setup_comment()
		# Hacer que el Link de Nivel Educativo NO exista.
		self.frappe.db.exists.side_effect = (
			lambda dt, *a, **kw: dt != "Nivel Educativo Siesa"
		)
		with self.assertRaises(self.frappe.ValidationError):
			ccs._apply_personal_data_change(
				self._doc({"nivel_educativo_siesa": "NO-EXISTE"})
			)

	def test_key_no_whitelisted_throws(self):
		self._setup_candidato()
		self._setup_no_extras()
		self._setup_comment()
		with self.assertRaises(self.frappe.ValidationError):
			ccs._apply_personal_data_change(self._doc({"email": "x@y.com"}))

	def test_rollback_si_falla_ficha(self):
		self._setup_candidato()
		self._setup_no_extras()
		self._setup_comment()

		# set_value sobre Ficha Empleado falla.
		def _set_value(doctype, *args, **kwargs):
			if doctype == "Ficha Empleado":
				raise RuntimeError("DB error en Ficha")
		self.frappe.db.set_value.side_effect = _set_value

		with self.assertRaises(RuntimeError):
			ccs._apply_personal_data_change(self._doc({"nombres": "Pedro"}))
		# Rollback al savepoint debe haberse llamado.
		self.frappe.db.rollback.assert_called_with(save_point="personal_data_correction")

	def test_sin_user_vinculado_no_cascadea_user(self):
		self._setup_candidato(user=None)
		self._setup_no_extras()
		self._setup_comment()
		result = ccs._apply_personal_data_change(
			self._doc({"nombres": "Ana", "primer_apellido": "Diaz"})
		)
		user_calls = [
			c for c in self.frappe.db.set_value.call_args_list
			if c.args and c.args[0] == "User"
		]
		self.assertFalse(user_calls)
		self.assertFalse(result["user_actualizado"])

	def test_sin_ficha_vinculada_no_cascadea_ficha(self):
		self._setup_candidato(persona=None)
		self._setup_no_extras()
		self._setup_comment()
		ccs._apply_personal_data_change(
			self._doc({"nombres": "Ana"})
		)
		ficha_calls = [
			c for c in self.frappe.db.set_value.call_args_list
			if c.args and c.args[0] == "Ficha Empleado"
		]
		self.assertFalse(ficha_calls)

	def test_cambio_nombres_refresca_snapshot_contrato(self):
		self._setup_candidato()
		# exists True para User/Ficha; Contrato lo entrega get_all.
		self.frappe.db.exists.return_value = True
		self.frappe.get_all.return_value = ["CONT-12345678-1"]
		self._setup_comment()

		ccs._apply_personal_data_change(
			self._doc({"nombres": "Pedro", "primer_apellido": "Ramirez"})
		)
		contrato_calls = [
			c for c in self.frappe.db.set_value.call_args_list
			if c.args and c.args[0] == "Contrato"
		]
		self.assertEqual(len(contrato_calls), 1)
		payload = contrato_calls[0].args[2]
		self.assertEqual(payload.get("nombres"), "Pedro")

	def test_sin_cambios_throws(self):
		self._setup_candidato()
		self._setup_no_extras()
		self._setup_comment()
		# Payload solo con None → cambios vacíos.
		with self.assertRaises(self.frappe.ValidationError):
			ccs._apply_personal_data_change(self._doc({"nombres": None}))


if __name__ == "__main__":
	unittest.main()
