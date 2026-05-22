# Copyright (c) 2026, Antigravity and contributors
# For license information, please see license.txt

from __future__ import annotations

import frappe
from frappe.model.document import Document


class ConfiguracionTerminacion(Document):
    """
    Single DocType: configuracion global del proceso de terminacion de contrato.

    issingle=1. Solo existe un registro: name="Configuracion Terminacion".
    La tabla suscriptores_por_area define quien recibe notificaciones por area.

    Validacion: cada row de suscriptores_por_area debe tener al menos uno de:
    role, user o email_fijo.
    """

    def validate(self):
        for row in self.suscriptores_por_area or []:
            if not any([row.get("role"), row.get("user"), row.get("email_fijo")]):
                frappe.throw(
                    f"La fila de area '{row.get('area')}' debe tener al menos un "
                    "destinatario (role, user o email_fijo)."
                )
