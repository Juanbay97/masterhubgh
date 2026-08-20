# Copyright (c) 2026, Antigravity and contributors
# For license information, please see license.txt

"""
TDD — Batch PR2, Phase 2.2: affiliation_contract_snapshot HR-READ gate + demográficos/dotación.

Tests cover:
  2.2.1  RED  → gate accepts HR-READ via validate_hr_or_selection_read_access,
                rejects a non-HR-READ role BEFORE any Candidato DB read
  2.2.3  RED  → demográficos/dotación block populates from Candidato alone when
                no Datos Contratacion record exists

All tests are RED until the corresponding GREEN task lands (see tasks.md Phase 2.2).
"""

from unittest.mock import patch

import frappe
from frappe.tests.utils import FrappeTestCase

from hubgh.hubgh import contratacion_service as cs


def _candidato_dict(**overrides):
	base = {
		"name": "CAND-001",
		"numero_documento": "123456",
		"nombres": "Ana",
		"apellidos": "",
		"primer_apellido": "Gomez",
		"segundo_apellido": "Diaz",
		"ciudad": "BOG",
		"direccion": "Calle 1",
		"pdv_destino": None,
		"cargo_postulado": None,
		"tipo_documento": "Cedula",
		"fecha_nacimiento": "1995-05-20",
		"fecha_expedicion": None,
		"celular": "3000000000",
		"email": "ana@test.com",
		"tiene_cuenta_bancaria": "Si",
		"eps_siesa": None,
		"afp_siesa": None,
		"cesantias_siesa": None,
		"ccf_siesa": None,
		"banco_siesa": None,
		"fecha_tentativa_ingreso": None,
		"telefono_fijo": "6011234567",
		"grupo_sanguineo": "O+",
		"contacto_emergencia_nombre": "Luis",
		"contacto_emergencia_telefono": "3001111111",
		"tiene_alergias": 0,
		"descripcion_alergias": "",
		"talla_camisa": "M",
		"talla_pantalon": "32",
		"numero_zapatos": "38",
		"talla_delantal": "L",
		"estado_civil": "Soltero",
		"nivel_educativo_siesa": None,
	}
	base.update(overrides)
	return frappe._dict(base)


class TestAffiliationSnapshotHRReadGate(FrappeTestCase):
	"""2.2.1 — HR-READ gate replaces validate_hr_access for this read-only endpoint."""

	def test_rejects_non_hr_read_role_before_candidate_db_read(self):
		with (
			patch("hubgh.hubgh.seleccion_cruce_service.user_has_any_role", return_value=False),
			patch("hubgh.hubgh.seleccion_cruce_service.frappe.session") as mock_gate_session,
			patch.object(cs, "frappe") as mock_frappe,
		):
			mock_gate_session.user = "unrelated.role@homeburgers.com"
			mock_frappe.session.user = "unrelated.role@homeburgers.com"
			with self.assertRaises(frappe.exceptions.ValidationError):
				cs.affiliation_contract_snapshot("CAND-001")
		mock_frappe.db.exists.assert_not_called()
		mock_frappe.get_doc.assert_not_called()

	def test_accepts_hr_selection_without_rrll_role(self):
		"""HR Selection (Selección) has no RRLL role but IS in CRUCE_ROLES — must be allowed."""
		candidato = _candidato_dict()
		with (
			patch(
				"hubgh.hubgh.seleccion_cruce_service.user_has_any_role",
				side_effect=lambda user, *roles: "HR Selection" in roles,
			),
			patch("hubgh.hubgh.seleccion_cruce_service.frappe.session") as mock_gate_session,
			patch.object(cs, "frappe") as mock_frappe,
		):
			mock_gate_session.user = "selection.user@homeburgers.com"
			mock_frappe.session.user = "selection.user@homeburgers.com"
			mock_frappe.db.exists.return_value = True
			mock_frappe.db.get_value.return_value = None
			mock_frappe.get_doc.return_value = candidato

			result = cs.affiliation_contract_snapshot("CAND-001")

		self.assertEqual(result["candidate"]["name"], "CAND-001")


class TestAffiliationSnapshotDemograficosDotacion(FrappeTestCase):
	"""2.2.3 — demográficos/dotación populate from Candidato alone when Datos Contratacion is absent."""

	def _call_snapshot_without_datos(self, **candidato_overrides):
		candidato = _candidato_dict(**candidato_overrides)
		with (
			patch("hubgh.hubgh.seleccion_cruce_service.user_has_any_role", return_value=True),
			patch("hubgh.hubgh.seleccion_cruce_service.frappe.session") as mock_gate_session,
			patch.object(cs, "frappe") as mock_frappe,
		):
			mock_gate_session.user = "hr.selection@homeburgers.com"
			mock_frappe.session.user = "hr.selection@homeburgers.com"
			mock_frappe.db.exists.return_value = True
			mock_frappe.db.get_value.return_value = None  # no Datos Contratacion, no Afiliacion
			mock_frappe.get_doc.return_value = candidato
			return cs.affiliation_contract_snapshot("CAND-001")

	def test_demograficos_block_populates_from_candidato_alone(self):
		result = self._call_snapshot_without_datos()
		demograficos = result["blocks"]["demograficos"]
		self.assertEqual(demograficos["telefono_fijo"], "6011234567")
		self.assertEqual(demograficos["grupo_sanguineo"], "O+")
		self.assertEqual(demograficos["contacto_emergencia_nombre"], "Luis")
		self.assertEqual(demograficos["contacto_emergencia_telefono"], "3001111111")
		self.assertEqual(demograficos["tiene_alergias"], 0)
		self.assertEqual(demograficos["descripcion_alergias"], "")
		self.assertEqual(demograficos["estado_civil"], "Soltero")

	def test_dotacion_block_populates_from_candidato_alone(self):
		result = self._call_snapshot_without_datos()
		dotacion = result["blocks"]["dotacion"]
		self.assertEqual(dotacion["talla_camisa"], "M")
		self.assertEqual(dotacion["talla_pantalon"], "32")
		self.assertEqual(dotacion["numero_zapatos"], "38")
		self.assertEqual(dotacion["talla_delantal"], "L")

	def test_estado_civil_prefers_datos_over_candidato_when_both_present(self):
		candidato = _candidato_dict(estado_civil="Soltero")
		datos = frappe._dict({"estado_civil": "Casado", "nivel_educativo_siesa": None})
		with (
			patch("hubgh.hubgh.seleccion_cruce_service.user_has_any_role", return_value=True),
			patch("hubgh.hubgh.seleccion_cruce_service.frappe.session") as mock_gate_session,
			patch.object(cs, "frappe") as mock_frappe,
		):
			mock_gate_session.user = "hr.selection@homeburgers.com"
			mock_frappe.session.user = "hr.selection@homeburgers.com"
			mock_frappe.db.exists.return_value = True
			mock_frappe.db.get_value.side_effect = lambda doctype, *a, **k: (
				"DC-CAND-001" if doctype == "Datos Contratacion" else None
			)
			mock_frappe.get_doc.side_effect = lambda doctype, name=None: (
				candidato if doctype == "Candidato" else datos
			)
			result = cs.affiliation_contract_snapshot("CAND-001")

		self.assertEqual(result["blocks"]["demograficos"]["estado_civil"], "Casado")
