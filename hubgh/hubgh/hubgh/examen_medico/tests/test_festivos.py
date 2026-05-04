# Copyright (c) 2026, Antigravity and contributors
# For license information, please see license.txt

"""
Tests for festivos.is_colombia_holiday.

No live DB or Frappe required. Tests the function directly — festivos.py
has no Frappe imports; it's pure Python with optional `holidays` library.

REQ refs: REQ-17 (festivos Colombia excluidos del calendario).
"""

import sys
import types
from unittest import TestCase
from unittest.mock import patch


# festivos.py has no frappe import — safe to import directly
from hubgh.hubgh.examen_medico import festivos  # noqa: E402


class TestFestivos(TestCase):

	def test_20_julio_2026_is_festivo(self):
		"""REQ-17: 2026-07-20 (Batalla de Boyacá) debe ser festivo colombiano."""
		result = festivos.is_colombia_holiday("2026-07-20")
		self.assertTrue(result, "2026-07-20 es festivo Colombia (Batalla de Boyacá)")

	def test_random_tuesday_is_not_festivo(self):
		"""REQ-17: 2026-07-14 (martes ordinario) NO es festivo colombiano."""
		result = festivos.is_colombia_holiday("2026-07-14")
		self.assertFalse(result, "2026-07-14 no es festivo Colombia")

	def test_uses_holidays_library_when_available(self):
		"""REQ-17: Cuando la librería `holidays` está disponible, la usa."""
		# Patch sys.modules to simulate holidays library available
		fake_holidays_module = types.ModuleType("holidays")

		class FakeColombiaHolidays:
			def __contains__(self, item):
				# Return True only for 2026-07-20
				from datetime import date
				return item == date(2026, 7, 20)

		fake_holidays_module.Colombia = lambda years=None: FakeColombiaHolidays()

		with patch.dict(sys.modules, {"holidays": fake_holidays_module}):
			# Re-import to pick up the patched module path
			import importlib
			import hubgh.hubgh.examen_medico.festivos as festivos_mod
			importlib.reload(festivos_mod)
			result = festivos_mod.is_colombia_holiday("2026-07-20")

		self.assertTrue(result, "Con librería disponible: 2026-07-20 debe ser festivo")

	def test_uses_hardcoded_fallback_when_library_missing(self):
		"""REQ-17: Sin librería `holidays`, el fallback hardcodeado funciona."""
		with patch.dict(sys.modules, {"holidays": None}):
			import importlib
			import hubgh.hubgh.examen_medico.festivos as festivos_mod
			importlib.reload(festivos_mod)
			result = festivos_mod.is_colombia_holiday("2026-07-20")

		self.assertTrue(result, "Fallback hardcodeado: 2026-07-20 debe ser festivo")
