# Copyright (c) 2026, Antigravity and contributors
# For license information, please see license.txt

from __future__ import annotations

import frappe
from frappe.model.document import Document


class TrasladoPDV(Document):
	"""
	DocType Traslado PDV — registro de un traslado programado o aplicado entre PDVs.

	El DocType es intencionalmente anémico. Toda la lógica de negocio vive en
	hubgh.hubgh.services.traslado_service.

	Hooks reales:
	- before_insert → traslado_service.before_insert_traslado (snapshot pdv_origen)
	- on_update    → traslado_service.on_update_traslado (publish People Ops Event)
	"""
	pass
