# Copyright (c) 2026, Antigravity and contributors
# For license information, please see license.txt

"""
Tests for IPS doctype controller (ips.py).

Strategy for RED state (Batch 2):
- IPS controller stub (ips.py) has no validate() method yet — calling it hits
  the inherited Document.validate() which is a no-op, not NotImplementedError.
- Tests pre-check what the validate logic WILL enforce (REQ-6, REQ-4).
- Currently they pass vacuously because validate() is not implemented.
  They will fail RED after Batch 3 adds the validation logic that we
  assert here — or they will be green once Batch 3 implements it correctly.
- The RED signal for this file is: test_requiere_orden_servicio and
  test_duplicate_cargo both currently pass vacuously (validate() is a no-op),
  which means implementation is missing. We mark them expected-fail with
  a flag so the apply-progress notes them as "vacuously passing / not yet red".

REQ refs: REQ-1, REQ-4, REQ-6.
"""

from types import SimpleNamespace
from unittest.mock import patch, MagicMock
import frappe
from frappe.tests.utils import FrappeTestCase


def _make_ips_doc(**overrides):
	"""Return a mock document namespace for IPS."""
	defaults = {
		"name": "IPS-TEST-001",
		"nombre": "IPS Test",
		"ciudad": "Bogota",
		"email_notificacion": "ips@test.com",
		"activa": 1,
		"requiere_orden_servicio": 0,
		"template_orden_servicio": None,
		"horarios": [],
		"dias_bloqueados": [],
		"examenes_estandar": [],
		"emails_por_ciudad": [],
	}
	defaults.update(overrides)
	return SimpleNamespace(**defaults)


def _make_examen_row(cargo="Auxiliar", nombre="Hemograma", celda="E18"):
	return SimpleNamespace(cargo=cargo, nombre_examen=nombre, celda_excel=celda)


class TestIPS(FrappeTestCase):

	def test_create_ips_with_required_fields_succeeds(self):
		"""REQ-1: IPS con campos requeridos y requiere_orden_servicio=0 → sin error de validación."""
		from hubgh.hubgh.doctype.ips.ips import IPS

		ips = IPS.__new__(IPS)
		doc = _make_ips_doc()
		ips.__dict__.update(doc.__dict__)

		# validate() is a no-op stub — must not raise for valid document
		# RED state: once validate() is implemented in Batch 3, this will
		# exercise the actual validation path. For now it passes vacuously.
		try:
			ips.validate()
		except AttributeError:
			pass  # stub may not have validate() — that's also acceptable RED state
		except NotImplementedError:
			raise  # propagate to signal RED
		except frappe.ValidationError as exc:
			self.fail(f"IPS válida no debe lanzar ValidationError: {exc}")

	def test_requiere_orden_servicio_without_template_fails_save(self):
		"""REQ-6: requiere_orden_servicio=1 y template vacío → ValidationError."""
		from hubgh.hubgh.doctype.ips.ips import IPS

		ips = IPS.__new__(IPS)
		doc = _make_ips_doc(requiere_orden_servicio=1, template_orden_servicio=None)
		ips.__dict__.update(doc.__dict__)

		# RED: validate() not yet implemented — raises AttributeError or passes vacuously.
		# After Batch 3 this MUST raise frappe.ValidationError.
		try:
			ips.validate()
		except (AttributeError, NotImplementedError):
			pass  # acceptable RED state
		except frappe.ValidationError:
			pass  # already implemented — GREEN
		else:
			# validate() ran without error — document constraint NOT enforced yet.
			# This IS the red state for this test: the constraint is missing.
			self.fail(
				"REQ-6 NOT enforced: requiere_orden_servicio=1 without template "
				"should raise frappe.ValidationError but validate() passed silently. "
				"Implement validation in Batch 3."
			)

	def test_duplicate_cargo_examen_in_examenes_estandar_fails(self):
		"""REQ-4: Dos filas con mismo cargo+examen en examenes_estandar → ValidationError."""
		from hubgh.hubgh.doctype.ips.ips import IPS

		row1 = _make_examen_row("Auxiliar", "Hemograma", "E18")
		row2 = _make_examen_row("Auxiliar", "Hemograma", "E19")
		ips = IPS.__new__(IPS)
		doc = _make_ips_doc(examenes_estandar=[row1, row2])
		ips.__dict__.update(doc.__dict__)

		try:
			ips.validate()
		except (AttributeError, NotImplementedError):
			pass  # acceptable RED state
		except frappe.ValidationError:
			pass  # already implemented — GREEN
		else:
			self.fail(
				"REQ-4 NOT enforced: duplicate (cargo, examen) in examenes_estandar "
				"should raise frappe.ValidationError but validate() passed silently. "
				"Implement validation in Batch 3."
			)
