# Copyright (c) 2026, Antigravity and contributors
# For license information, please see license.txt

"""
Tests for slot_engine.get_available_slots.

Strategy (Batch 3 — GREEN):
- Functions are fully implemented.
- patch.object(frappe.db, ...) for Frappe v15 safety.
- Tests verify actual slot generation, exclusions, and cupo arithmetic.

REQ refs: REQ-2 (slot generation), REQ-3 (dias_bloqueados), REQ-11 (cupos),
          REQ-17 (festivos Colombia).
"""

from unittest.mock import patch
from frappe.tests.utils import FrappeTestCase
import frappe

from hubgh.hubgh.examen_medico import slot_engine


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_ips(
	horarios=None,
	dias_bloqueados=None,
	cupos_por_slot=3,
	intervalo_minutos=60,
):
	"""Build a minimal IPS dict sufficient for slot_engine."""
	if horarios is None:
		horarios = [
			{
				"dia_semana": "L",
				"hora_inicio": "08:00:00",
				"hora_fin": "12:00:00",
				"intervalo_minutos": intervalo_minutos,
				"cupos_por_slot": cupos_por_slot,
			}
		]
	return {
		"name": "IPS-TEST",
		"horarios": horarios,
		"dias_bloqueados": dias_bloqueados or [],
	}


# ---------------------------------------------------------------------------
# Test cases
# ---------------------------------------------------------------------------

class TestSlotEngine(FrappeTestCase):

	def test_generates_correct_slots_for_horario_monday_8_to_12_interval_60_cupos_3(self):
		"""REQ-2: Horario L 08:00-12:00 intervalo 60 genera exactamente 4 slots."""
		ips = _make_ips()
		# 2026-07-06 is a Monday (not a festivo)
		slots = slot_engine.get_available_slots(ips, "2026-07-06", days=1)

		self.assertEqual(len(slots), 4, f"Deben ser 4 slots, got: {[s['hora'] for s in slots]}")
		horas = [s["hora"] for s in slots]
		self.assertIn("08:00:00", horas)
		self.assertIn("09:00:00", horas)
		self.assertIn("10:00:00", horas)
		self.assertIn("11:00:00", horas)

	def test_excludes_blocked_days_from_availability(self):
		"""REQ-3: Fecha en dias_bloqueados retorna cero slots para ese día."""
		ips = _make_ips(
			dias_bloqueados=[{"fecha": "2026-07-06", "motivo": "Mantenimiento"}],
		)
		slots = slot_engine.get_available_slots(ips, "2026-07-06", days=1)
		self.assertEqual(len(slots), 0, "Día bloqueado debe retornar 0 slots")

	def test_excludes_colombia_festivos_from_availability(self):
		"""REQ-17: 2026-07-20 es festivo Colombia (Batalla de Boyacá) → cero slots."""
		# 2026-07-20 is a Monday AND a festivo — should be excluded
		ips = _make_ips()
		slots = slot_engine.get_available_slots(ips, "2026-07-20", days=1)
		self.assertEqual(len(slots), 0, "Festivo Colombia debe retornar 0 slots")

	def test_subtracts_existing_citas_from_cupos(self):
		"""REQ-11: cupos_por_slot=1, una cita Agendada → slot con disponibles=0 excluido."""
		ips = _make_ips(cupos_por_slot=1)
		existing_citas = [
			{
				"fecha_cita": "2026-07-06",
				"hora_cita": "08:00:00",
				"estado": "Agendada",
			}
		]
		slots = slot_engine.get_available_slots(
			ips, "2026-07-06", days=1, existing_citas=existing_citas
		)
		# Slot at 08:00:00 should be excluded (cupos=1, booked=1 → disponibles=0)
		horas = [s["hora"] for s in slots]
		self.assertNotIn("08:00:00", horas, "Slot lleno debe ser excluido")
		# Other slots should still be present
		self.assertIn("09:00:00", horas)

	def test_returns_empty_when_no_horario_for_requested_day(self):
		"""REQ-2: Si no hay horario para el weekday solicitado, retorna []."""
		ips = _make_ips(
			horarios=[
				{
					"dia_semana": "M",
					"hora_inicio": "08:00:00",
					"hora_fin": "10:00:00",
					"intervalo_minutos": 60,
					"cupos_por_slot": 3,
				}
			]
		)
		# 2026-07-06 is a Monday (L), but horario is for Tuesday (M)
		slots = slot_engine.get_available_slots(ips, "2026-07-06", days=1)
		self.assertEqual(len(slots), 0, "Sin horario para el día → 0 slots")
