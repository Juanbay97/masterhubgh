# Copyright (c) 2026, Antigravity and contributors
# For license information, please see license.txt

"""
Patch idempotente — Gap C2→C3 stub infrastructure.

Acciones:
1. Crea/upsert Email Template 'retiro_legacy_stub_alerta' con subject/body del diseño.
2. Ejecuta frappe.reload_doctype("Ficha Empleado", force=True) para sincronizar los
   2 campos tracking nuevos (last_retirement_attempt_at, last_retirement_attempt_source)
   y marcar los 8 legacy como candidatos a DROP en el siguiente migrate.

Subject: [GAP C3] Intento de retiro automático bloqueado para {{ empleado_nombre }}
"""

import frappe

TEMPLATE_NAME = "retiro_legacy_stub_alerta"

TEMPLATE_SUBJECT = "[GAP C3] Intento de retiro automático bloqueado para {{ empleado_nombre }}"

TEMPLATE_BODY = """\
<div style="font-family:Arial,sans-serif;max-width:620px;margin:0 auto;">
  <div style="background:#111;padding:20px;text-align:center;">
    <img src="/assets/hubgh/images/logo-circular-black.png" alt="HubGH"
         style="height:40px;filter:invert(1);">
  </div>
  <div style="padding:32px 24px;background:#ffffff;">
    {% if is_reverse %}
    <div style="background:#fef3c7;border-left:4px solid #d97706;padding:12px 16px;
                margin-bottom:24px;border-radius:4px;">
      <strong style="color:#92400e;">Reversión de retiro — acción manual requerida</strong>
    </div>
    <p>Hola RRLL,</p>
    <p>El sistema detectó un intento de <strong>reversión de retiro automático</strong>
    que <strong>no se ejecutó</strong> porque el flujo formal de Terminación de Contrato
    (Cambio 3) todavía no está disponible.</p>
    {% else %}
    <div style="background:#fee2e2;border-left:4px solid #dc2626;padding:12px 16px;
                margin-bottom:24px;border-radius:4px;">
      <strong style="color:#991b1b;">Retiro automático bloqueado — acción manual requerida</strong>
    </div>
    <p>Hola RRLL,</p>
    <p>El sistema detectó un intento de <strong>retiro automático</strong>
    que <strong>no se ejecutó</strong> porque el flujo formal de Terminación de Contrato
    (Cambio 3) todavía no está disponible.</p>
    {% endif %}
    <ul>
      <li><strong>Empleado:</strong>
          <a href="{{ site_url }}/app/ficha-empleado/{{ empleado }}">{{ empleado }}</a></li>
      <li><strong>Fuente:</strong> {{ source_doctype }} →
          <a href="{{ site_url }}/app/{{ source_doctype|lower|replace(' ', '-') }}/{{ source_name }}">
          {{ source_name }}</a></li>
      <li><strong>Acción intentada:</strong>
          {% if is_reverse %}Reversión de retiro{% else %}Retiro{% endif %}</li>
      {% if retirement_date %}
      <li><strong>Fecha sugerida:</strong> {{ retirement_date }}</li>
      {% endif %}
      {% if reason %}
      <li><strong>Motivo:</strong> {{ reason }}</li>
      {% endif %}
    </ul>
    {% if is_reverse %}
    <p><strong>Acción requerida:</strong> Verificar si el empleado debe ser reactivado
    manualmente en el sistema hasta que C3 esté disponible.</p>
    {% else %}
    <p><strong>Acción requerida:</strong> Deshabilitar el usuario y dar de baja la Tarjeta
    Empleado manualmente. El campo <em>Último intento de retiro</em> en la Ficha queda
    registrado para trazabilidad.</p>
    {% endif %}
    <p style="color:#6b7280;font-size:13px;">Este correo fue generado automáticamente por
    el sistema HubGH como parte del gap operacional C2→C3.</p>
    <p>— Sistema HubGH</p>
  </div>
  <div style="padding:16px 24px;background:#f9fafb;text-align:center;
              color:#6b7280;font-size:12px;">
    <p><em>Equipo de Relaciones Laborales — HubGH</em></p>
  </div>
</div>"""


def execute():
    """Crea el Email Template de stub de retiro. Idempotente."""
    _upsert_email_template()
    frappe.reload_doctype("Ficha Empleado", force=True)
    frappe.db.commit()


def _upsert_email_template():
    if frappe.db.exists("Email Template", TEMPLATE_NAME):
        doc = frappe.get_doc("Email Template", TEMPLATE_NAME)
        doc.subject = TEMPLATE_SUBJECT
        doc.response = TEMPLATE_BODY
        doc.enabled = 1
        doc.use_html = 1
        doc.save(ignore_permissions=True)
        frappe.logger("hubgh.patches").info(
            f"Updated Email Template: {TEMPLATE_NAME}"
        )
    else:
        try:
            frappe.get_doc({
                "doctype": "Email Template",
                "name": TEMPLATE_NAME,
                "subject": TEMPLATE_SUBJECT,
                "response": TEMPLATE_BODY,
                "enabled": 1,
                "use_html": 1,
            }).insert(ignore_permissions=True)
            frappe.logger("hubgh.patches").info(
                f"Created Email Template: {TEMPLATE_NAME}"
            )
        except Exception as exc:
            frappe.log_error(
                message=str(exc),
                title=f"cleanup_retiro_legacy_v1: fallo creando {TEMPLATE_NAME}",
            )
