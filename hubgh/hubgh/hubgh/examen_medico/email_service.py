# Copyright (c) 2026, Antigravity and contributors
# For license information, please see license.txt

"""
email_service — Wrapper sobre frappe.sendmail para emails de examen médico.

Renderiza Email Templates de Frappe, agrega CC configurables y gestiona
adjuntos (FRSN-02 xlsx). Loguea en fallo, no relanza excepción.
"""

from __future__ import annotations

# Fallback: si la config no existe / está vacía, usar estos emails.
# Mantener sincronizado con la siembra del patch
# (setup_examen_medico_multisede._ensure_configuracion_examen_medico).
CC_FALLBACK: list[str] = [
	"SST@homeburgers.com",
	"generalistagh1@homeburgers.com",
	"generalistagh2@homeburgers.com",
]


def _load_cc_always() -> list[str]:
	"""
	Lee los emails CC desde el Single 'Configuracion Examen Medico Autogestionado'.

	Returns:
		Lista de emails activos. Si el doctype no existe aún o la tabla está
		vacía, retorna CC_FALLBACK.

	Note:
		Se llama por cada envío para que cambios en UI apliquen al instante,
		sin reiniciar el servicio. El costo es despreciable (una sola query
		al Single).
	"""
	import frappe

	try:
		config = frappe.get_cached_doc("Configuracion Examen Medico Autogestionado")
		emails: list[str] = []
		for row in config.get("cc_emails") or []:
			activo = row.get("activo") if isinstance(row, dict) else getattr(row, "activo", 1)
			email = row.get("email") if isinstance(row, dict) else getattr(row, "email", None)
			if activo and email:
				email = str(email).strip()
				if email and email not in emails:
					emails.append(email)
		if emails:
			return emails
	except Exception:
		# Doctype puede no existir aún (antes de la primera migración con el patch)
		# o la fila Single puede no haberse creado. Caemos al fallback silenciosamente.
		pass

	return list(CC_FALLBACK)


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
		cc: Lista adicional de CC (se combina con los de la configuración).

	Note:
		Loguea en fallo mediante frappe.log_error; no relanza excepciones.
	"""
	import frappe
	from frappe.utils.jinja import render_template

	try:
		template_doc = frappe.get_doc("Email Template", template_name)
		subject = render_template(template_doc.subject or "", context)
		message = render_template(template_doc.response or template_doc.message or "", context)

		combined_cc = _load_cc_always()
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
