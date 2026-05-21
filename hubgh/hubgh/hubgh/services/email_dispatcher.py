# Copyright (c) 2026, Antigravity and contributors
# For license information, please see license.txt

"""
email_dispatcher — Wrapper genérico sobre frappe.sendmail.

Renderiza Email Templates de Frappe y dispara frappe.sendmail.
Reusable por cualquier dominio de la app (examen médico, traslados, terminación, etc).
Loguea en fallo, no relanza excepciones.

ADR-1: Se extrae en Cambio 1 para ser compartido por traslado_service y examen_medico.
       Cambio 3 (terminación) también lo consumirá.
"""

from __future__ import annotations


def dispatch_email(
	template_name: str,
	recipients: list[str],
	context: dict,
	attachments: list[dict] | None = None,
	cc: list[str] | None = None,
) -> dict:
	"""
	Renderiza un Email Template Frappe y dispara frappe.sendmail.

	Args:
		template_name: Nombre del Email Template en Frappe.
		recipients: Lista de correos destinatarios. Strings vacíos son filtrados.
		context: Variables Jinja para renderizar subject y body del template.
		attachments: Lista de adjuntos [{"fname": str, "fcontent": bytes}].
		cc: CC opcional.

	Returns:
		dict con keys:
			- status: "ok" | "error" | "skipped"
			- template: nombre del template usado
			- recipients: lista de destinatarios efectivos
			- error: mensaje de error (str) o None

	Note:
		- Loguea en fallo via frappe.log_error; no relanza.
		- Si recipients vacío o todos None → status="skipped", no se envía.
		- cc opcional.
	"""
	import frappe
	from frappe.utils.jinja import render_template

	# Filtrar recipients vacíos o None
	valid_recipients = [r for r in (recipients or []) if r]
	if not valid_recipients:
		return {
			"status": "skipped",
			"template": template_name,
			"recipients": [],
			"error": None,
		}

	try:
		template_doc = frappe.get_doc("Email Template", template_name)
		subject = render_template(template_doc.subject or "", context)
		# response tiene precedencia sobre message (convención Frappe)
		body_source = template_doc.response or template_doc.message or ""
		message = render_template(body_source, context)

		frappe.sendmail(
			recipients=valid_recipients,
			cc=cc or [],
			subject=subject,
			message=message,
			attachments=attachments or [],
		)
		return {
			"status": "ok",
			"template": template_name,
			"recipients": valid_recipients,
			"error": None,
		}
	except Exception as exc:
		frappe.log_error(
			message=str(exc),
			title=f"dispatch_email error: {template_name}",
		)
		return {
			"status": "error",
			"template": template_name,
			"recipients": valid_recipients,
			"error": str(exc),
		}
