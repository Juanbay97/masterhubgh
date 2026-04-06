"""
Patch: sync_seleccion_workspace
Fuerza la re-sincronización del workspace "Selección" desde su JSON fixture.

Contexto: existían dos archivos con name="Selección" en el repo
  - workspace/seleccion/seleccion.json  (alias de compatibilidad, is_hidden=1)
  - workspace/selección/selección.json  (el real, con shortcuts operativos)

Frappe hizo upsert del alias primero, dejando el workspace con contenido
vacío y is_hidden=1. Este patch elimina el registro de DB para que migrate
lo recree correctamente desde selección.json.
"""

import frappe

from hubgh.hubgh.selection_document_types import sync_selection_workspace_shortcut


def execute():
	if not frappe.db.exists("Workspace", "Selección"):
		return  # No existe, migrate lo creará desde el JSON

	ws = frappe.get_doc("Workspace", "Selección")

	# Si el workspace ya tiene shortcuts correctos (migración previa ok), salir
	if ws.shortcuts and len(ws.shortcuts) > 0:
		# Asegurarse que esté visible y con el contenido correcto
		if ws.is_hidden:
			ws.is_hidden = 0
			ws.save(ignore_permissions=True)
		sync_selection_workspace_shortcut()
		frappe.db.commit()
		return

	# El workspace tiene el contenido del alias (sin shortcuts) — eliminarlo
	# para que migrate lo recree desde selección.json
	frappe.delete_doc("Workspace", "Selección", force=True, ignore_permissions=True)
	frappe.db.commit()
