# Copyright (c) 2026, Antigravity and contributors
# For license information, please see license.txt

"""
email_service — Wrapper sobre frappe.sendmail para emails de examen médico.

Renderiza Email Templates de Frappe y gestiona adjuntos (FRSN-02 xlsx).
Loguea en fallo, no relanza excepción.

Nota histórica: este wrapper antes inyectaba un CC fijo (SST + 2 generalistas)
en cada envío. Se removió esa lógica porque con Resend cada CC se factura
como un envelope SMTP separado, multiplicando los créditos consumidos por 4.
La notificación a SST/generalistas ahora se hace vía digest diario
(ver hubgh.hubgh.examen_medico.digest).
"""

from __future__ import annotations

from hubgh.hubgh.services.email_dispatcher import dispatch_email


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
		cc: CC opcional. Si None o vacío, no se envía CC.

	Note:
		Loguea en fallo mediante frappe.log_error; no relanza excepciones.
		Wrapper de compatibilidad que delega a dispatch_email.
		El contrato externo (firma + side effect void) es idéntico al original.
	"""
	dispatch_email(
		template_name=template_name,
		recipients=recipients,
		context=context,
		attachments=attachments,
		cc=cc,
	)
	# Retorna None explícitamente para mantener contrato void


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
