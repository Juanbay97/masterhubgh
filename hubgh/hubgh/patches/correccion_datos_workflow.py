# Copyright (c) 2026, Antigravity and contributors
# For license information, please see license.txt

"""Patch: Workflow formal para `Correccion Datos Candidato` (Batch 7).

Idempotente:
  - Crea/actualiza los Workflow States: Borrador, Pendiente Aprobación, Aplicado, Rechazado.
  - Crea los Workflow Action Masters: Aplicar, Solicitar Aprobación, Aprobar, Rechazar.
  - Crea/actualiza el Workflow `HubGH - Correccion Datos Candidato`.

Si el DocType `Correccion Datos Candidato` no existe todavía (corrida temprana),
el patch es no-op y devuelve sin error.
"""

import frappe


WORKFLOW_NAME = "HubGH - Correccion Datos Candidato"
DOCTYPE = "Correccion Datos Candidato"
STATE_FIELD = "workflow_state"


_STATES = [
	("Borrador", "0", "HR Selection", "Warning"),
	("Pendiente Aprobación", "0", "Gerente GH", "Warning"),
	("Aplicado", "1", "Gerente GH", "Success"),
	# Rechazado: terminal con docstatus=0 (no cancel formal). Frappe no permite ir
	# directo de docstatus 0 → 2 sin pasar por submit, así que modelamos el descarte
	# como estado terminal en borrador. El controller bloquea ediciones de Rechazado.
	("Rechazado", "0", "Gerente GH", "Danger"),
]

_ACTIONS = [
	"Aplicar",
	"Solicitar Aprobación",
	"Aprobar",
	"Rechazar",
]

# (from_state, action, to_state, allowed_role)
_TRANSITIONS = [
	# Pre-contrato: cualquier rol operativo aplica directo.
	("Borrador", "Aplicar", "Aplicado", "HR Selection"),
	("Borrador", "Aplicar", "Aplicado", "Gestión Humana"),
	("Borrador", "Aplicar", "Aplicado", "GH - Bandeja General"),
	("Borrador", "Aplicar", "Aplicado", "System Manager"),

	# Post-contrato: operativo solicita aprobación.
	("Borrador", "Solicitar Aprobación", "Pendiente Aprobación", "HR Selection"),
	("Borrador", "Solicitar Aprobación", "Pendiente Aprobación", "Gestión Humana"),
	("Borrador", "Solicitar Aprobación", "Pendiente Aprobación", "GH - Bandeja General"),

	# Aprobador finaliza una solicitud pendiente.
	("Pendiente Aprobación", "Aprobar", "Aplicado", "Gerente GH"),
	("Pendiente Aprobación", "Aprobar", "Aplicado", "System Manager"),

	# Rechazos (terminal docstatus 2).
	("Borrador", "Rechazar", "Rechazado", "Gerente GH"),
	("Borrador", "Rechazar", "Rechazado", "System Manager"),
	("Pendiente Aprobación", "Rechazar", "Rechazado", "Gerente GH"),
	("Pendiente Aprobación", "Rechazar", "Rechazado", "System Manager"),
]


def execute():
	if not frappe.db.exists("DocType", DOCTYPE):
		# DocType aún no migrado; nada para enlazar.
		return

	_ensure_states()
	_ensure_actions()
	_ensure_workflow()
	frappe.db.commit()


def _ensure_states():
	for state_name, _doc_status, _allow_edit, style in _STATES:
		if frappe.db.exists("Workflow State", state_name):
			doc = frappe.get_doc("Workflow State", state_name)
			if doc.style != style:
				doc.style = style
				doc.save(ignore_permissions=True)
			continue
		frappe.get_doc(
			{
				"doctype": "Workflow State",
				"workflow_state_name": state_name,
				"style": style,
			}
		).insert(ignore_permissions=True)


def _ensure_actions():
	for action in _ACTIONS:
		if frappe.db.exists("Workflow Action Master", action):
			continue
		frappe.get_doc(
			{
				"doctype": "Workflow Action Master",
				"workflow_action_name": action,
			}
		).insert(ignore_permissions=True)


def _ensure_workflow():
	if frappe.db.exists("Workflow", WORKFLOW_NAME):
		doc = frappe.get_doc("Workflow", WORKFLOW_NAME)
	else:
		doc = frappe.get_doc({"doctype": "Workflow", "workflow_name": WORKFLOW_NAME})

	doc.document_type = DOCTYPE
	doc.is_active = 1
	doc.workflow_state_field = STATE_FIELD
	doc.send_email_alert = 0

	doc.set("states", [])
	for state_name, doc_status, allow_edit, _style in _STATES:
		doc.append(
			"states",
			{
				"state": state_name,
				"doc_status": doc_status,
				"allow_edit": allow_edit,
			},
		)

	doc.set("transitions", [])
	for from_state, action, to_state, allowed in _TRANSITIONS:
		doc.append(
			"transitions",
			{
				"state": from_state,
				"action": action,
				"next_state": to_state,
				"allowed": allowed,
				"allow_self_approval": 1,
			},
		)

	if doc.is_new():
		doc.insert(ignore_permissions=True)
	else:
		doc.save(ignore_permissions=True)
