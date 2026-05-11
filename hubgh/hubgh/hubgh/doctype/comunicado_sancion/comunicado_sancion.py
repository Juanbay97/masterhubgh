# Copyright (c) 2026, Antigravity and contributors
# For license information, please see license.txt

from __future__ import annotations

import frappe
from frappe import _
from frappe.model.document import Document


class ComunicadoSancion(Document):
    def validate(self):
        self._validate_articulos_rit_required()

    def _validate_articulos_rit_required(self):
        """Artículos RIT requeridos cuando tipo ≠ Recordatorio de Funciones."""
        tipo = (self.tipo_comunicado or "").strip()
        if tipo == "Recordatorio de Funciones":
            return
        if not self.articulos_rit_citados or len(self.articulos_rit_citados) == 0:
            frappe.throw(
                _(
                    "El comunicado de tipo '{0}' requiere al menos un artículo RIT citado."
                ).format(tipo),
                frappe.ValidationError,
            )
