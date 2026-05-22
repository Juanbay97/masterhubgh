# Copyright (c) 2026, Antigravity and contributors
# For license information, please see license.txt

from __future__ import annotations

import frappe
from frappe.model.document import Document


class CitaExamenEgreso(Document):
    """
    DocType Cita Examen Egreso — cita de examen medico de egreso para el proceso
    de terminacion de contrato.

    NOTA: Este DocType es INDEPENDIENTE de 'Cita Examen Medico' (ingreso).
    No hereda ni extiende ese DocType (ADR-3).

    Hooks registrados en hooks.py:
    - before_insert -> examen_egreso_service.before_insert_examen_egreso (genera token)
    """
    pass
