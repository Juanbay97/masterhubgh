# Copyright (c) 2026, Antigravity and contributors
# For license information, please see license.txt

"""
email_service — Wrapper sobre frappe.sendmail para emails de examen médico.

Renderiza Email Templates de Frappe, agrega CC constantes y gestiona
adjuntos (FRSN-02 xlsx). Loguea en fallo, no relanza excepción.
"""

from __future__ import annotations

# CC siempre incluido en todos los emails a candidatos
CC_ALWAYS: list[str] = [
	"SST@homeburgers.com",
	"generalistagh1@homeburgers.com",
	"generalistagh2@homeburgers.com",
]


def send_exam_email(
	template_name: str,
	recipients: list[str],
	context: dict,
	attachments: list[dict] | None = None,
	cc: list[str] | None = None,
) -> None:
	"""
	Renderiza Email Template y llama frappe.sendmail.

	Args:
		template_name: Nombre del Email Template en Frappe.
		recipients: Lista de correos destinatarios.
		context: Variables Jinja para renderizar el template.
		attachments: Lista de adjuntos [{"fname": str, "fcontent": bytes}].
		cc: Lista adicional de CC (se combina con CC_ALWAYS).

	Note:
		Loguea en fallo mediante frappe.log_error; no relanza excepciones.
	"""
	import frappe
	from frappe.utils.jinja import render_template

	try:
		template_doc = frappe.get_doc("Email Template", template_name)
		subject = render_template(template_doc.subject or "", context)
		message = render_template(template_doc.response or template_doc.message or "", context)

		combined_cc = list(CC_ALWAYS)
		if cc:
			combined_cc = combined_cc + [c for c in cc if c not in combined_cc]

		frappe.sendmail(
			recipients=recipients,
			cc=combined_cc,
			subject=subject,
			message=message,
			attachments=attachments or [],
		)
	except Exception as exc:
		frappe.log_error(
			message=str(exc),
			title=f"send_exam_email error: {template_name}",
		)


def get_ips_email(ips: dict, candidato_ciudad: str) -> str:
	"""
	Retorna email_override si hay coincidencia de ciudad en emails_por_ciudad,
	de lo contrario retorna ips.email_notificacion.

	Args:
		ips: Documento IPS como dict con child rows emails_por_ciudad.
		candidato_ciudad: Ciudad del candidato (string nombre).

	Returns:
		Email de notificación a usar para la IPS.
	"""
	for row in ips.get("emails_por_ciudad") or []:
		ciudad = row.get("ciudad") if isinstance(row, dict) else getattr(row, "ciudad", None)
		email = row.get("email") if isinstance(row, dict) else getattr(row, "email", None)
		if ciudad == candidato_ciudad and email:
			return email

	return ips.get("email_notificacion") or ""
