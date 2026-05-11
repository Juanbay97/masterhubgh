# Copyright (c) 2026, Antigravity and contributors
# For license information, please see license.txt

from __future__ import annotations

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import getdate


class CitacionDisciplinaria(Document):
    def validate(self):
        self._validate_minimo_5_dias_habiles()
        self._validate_ronda_unica_activa()

    def on_update(self):
        # Al cambiar estado a "Entregada" → delegar a workflow service
        if self.estado == "Entregada" and self.has_value_changed("estado"):
            from hubgh.hubgh.disciplinary_workflow_service import _mark_afectado_citado
            _mark_afectado_citado(self.afectado)

    def _validate_minimo_5_dias_habiles(self):
        """La fecha programada de descargos debe ser ≥5 días hábiles desde fecha_citacion."""
        if not self.fecha_citacion or not self.fecha_programada_descargos:
            return
        dias = _count_business_days(self.fecha_citacion, self.fecha_programada_descargos)
        if dias < 5:
            frappe.throw(
                _(
                    "La fecha programada de descargos debe ser ≥5 días hábiles después de la citación "
                    "(Art. 29 CN + RIT). Días hábiles calculados: {0}."
                ).format(dias),
                frappe.ValidationError,
            )

    def _validate_ronda_unica_activa(self):
        """No puede existir otra Citación activa de la misma ronda para el mismo afectado."""
        if not self.afectado or not self.numero_ronda:
            return
        existing = frappe.db.exists(
            "Citacion Disciplinaria",
            {
                "afectado": self.afectado,
                "numero_ronda": self.numero_ronda,
                "estado": ("not in", ("Anulada",)),
                "name": ("!=", self.name or ""),
            },
        )
        if existing:
            frappe.throw(
                _(
                    "Ya existe una Citación activa ronda {0} para este afectado: {1}."
                ).format(self.numero_ronda, existing),
                frappe.ValidationError,
            )


def _count_business_days(start_date, end_date) -> int:
    """
    Cuenta días hábiles (lunes a viernes) entre start_date y end_date.
    No incluye start_date, incluye end_date.
    Nota: no considera festivos colombianos (documented limitation, dec. LOCKED tasks #T019).
    """
    from datetime import timedelta

    start = getdate(start_date)
    end = getdate(end_date)

    if end <= start:
        return 0

    count = 0
    current = start + timedelta(days=1)
    while current <= end:
        if current.weekday() < 5:  # 0=Monday, 4=Friday
            count += 1
        current += timedelta(days=1)
    return count
