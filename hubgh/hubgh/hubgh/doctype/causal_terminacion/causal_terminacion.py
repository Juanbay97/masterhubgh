# Copyright (c) 2026, Antigravity and contributors
# For license information, please see license.txt

from __future__ import annotations

import frappe
from frappe.model.document import Document


class CausalTerminacion(Document):
    """
    Catalogo de causales de terminacion de contrato.

    Autoname: field:codigo (ej: justa_causa, renuncia).
    DocType intencionalmente anemico.
    """
    pass
