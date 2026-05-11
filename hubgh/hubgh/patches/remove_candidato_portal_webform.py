"""Elimina el Web Form `candidato_portal` y su ruta `/candidato-form`.

Era un web form viejo en `hubgh/hubgh/hubgh/web_form/candidato_portal/` que
nadie usa — los candidatos entran por la página custom `/candidato`
(hubgh/hubgh/www/candidato.html). Mantenerlo confundía y desviaba el
debugging del flujo de onboarding real.

Este patch borra el doc Web Form de la BD si existe. Los archivos del
web form ya están eliminados del repo en el mismo commit.
"""

import frappe


def execute():
	if frappe.db.exists("Web Form", "candidato_portal"):
		frappe.delete_doc("Web Form", "candidato_portal", force=1, ignore_permissions=True)
		frappe.db.commit()
