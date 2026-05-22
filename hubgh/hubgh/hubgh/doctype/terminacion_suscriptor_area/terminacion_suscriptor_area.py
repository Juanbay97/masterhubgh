# Copyright (c) 2026, Antigravity and contributors
# For license information, please see license.txt

from __future__ import annotations

import frappe
from frappe.model.document import Document


class TerminacionSuscriptorArea(Document):
    """
    Child table: define un suscriptor de notificaciones por area.
    istable=1

    Cada row debe tener al menos uno de: role, user, email_fijo.
    La validacion se hace desde el parent (ConfiguracionTerminacion.validate).
    """
    pass
