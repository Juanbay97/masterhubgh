# Copyright (c) 2026, Antigravity and contributors
# For license information, please see license.txt

from __future__ import annotations

import frappe
from frappe.model.document import Document


class TerminacionContrato(Document):
    """
    DocType Terminacion Contrato — orquestador del proceso de terminacion de contrato.

    DocType intencionalmente anemico. Toda la logica de negocio vive en
    hubgh.hubgh.services.terminacion_service.

    Hooks registrados en hooks.py:
    - before_insert -> terminacion_service.before_insert_terminacion (snapshots)
    - on_update    -> terminacion_service.on_update_terminacion (publish People Ops Event)
    """
    pass
