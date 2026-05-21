# Copyright (c) 2026, Antigravity and contributors
# For license information, please see license.txt

"""
Patch idempotente: carga los 4 Email Templates de Traslado PDV.

Templates:
  - traslado_pdv_empleado_programado   (T1 — al empleado)
  - traslado_pdv_jefe_origen_programado (T2 — al jefe del PDV origen)
  - traslado_pdv_jefe_destino_programado (T3 — al jefe del PDV destino)
  - traslado_pdv_aplicado_confirmacion  (T4 — confirmación al aplicar)

Variables Jinja disponibles:
  traslado: {name, empleado, empleado_nombre, pdv_origen, pdv_destino,
             fecha_aplicacion, motivo_label, justificacion, cargo_destino}
  empleado: {nombres, apellidos, cedula, email}
  jefe_origen: {user, full_name} | None
  jefe_destino: {user, full_name} | None
  aplicado_por: str (solo T4)
"""

import frappe


TEMPLATES = [
    (
        "traslado_pdv_empleado_programado",
        "Tu traslado a {{ traslado.pdv_destino }} está programado — {{ traslado.fecha_aplicacion }}",
        """<div style="font-family:Arial,sans-serif;max-width:600px;margin:0 auto;">
  <div style="background:#111;padding:20px;text-align:center;">
    <img src="/assets/hubgh/images/logo-circular-black.png" alt="HubGH" style="height:40px;filter:invert(1);">
  </div>
  <div style="padding:32px 24px;background:#ffffff;">
    <p>Hola <strong>{{ empleado.nombres }}</strong>,</p>
    <p>Tu traslado de PDV ha sido <strong>programado</strong> exitosamente. Aquí está el detalle:</p>
    <table style="width:100%;border-collapse:collapse;margin:20px 0;">
      <tr style="background:#f3f4f6;">
        <td style="padding:10px;border:1px solid #e5e7eb;font-weight:bold;width:40%;">PDV actual (origen)</td>
        <td style="padding:10px;border:1px solid #e5e7eb;">{{ traslado.pdv_origen }}</td>
      </tr>
      <tr>
        <td style="padding:10px;border:1px solid #e5e7eb;font-weight:bold;">PDV destino</td>
        <td style="padding:10px;border:1px solid #e5e7eb;"><strong>{{ traslado.pdv_destino }}</strong></td>
      </tr>
      <tr style="background:#f3f4f6;">
        <td style="padding:10px;border:1px solid #e5e7eb;font-weight:bold;">Fecha de aplicación</td>
        <td style="padding:10px;border:1px solid #e5e7eb;"><strong>{{ traslado.fecha_aplicacion }}</strong></td>
      </tr>
      <tr>
        <td style="padding:10px;border:1px solid #e5e7eb;font-weight:bold;">Motivo</td>
        <td style="padding:10px;border:1px solid #e5e7eb;">{{ traslado.motivo_label }}</td>
      </tr>
      {% if traslado.cargo_destino %}
      <tr style="background:#f3f4f6;">
        <td style="padding:10px;border:1px solid #e5e7eb;font-weight:bold;">Cargo en destino</td>
        <td style="padding:10px;border:1px solid #e5e7eb;">{{ traslado.cargo_destino }}</td>
      </tr>
      {% endif %}
    </table>
    <p><strong>¿Qué pasa el día de aplicación?</strong></p>
    <ul>
      <li>Tu punto de venta en el sistema se actualizará automáticamente.</li>
      <li>Serás asignado/a al equipo del nuevo PDV.</li>
      <li>Tu jefe actual será notificado con anticipación para coordinar la entrega.</li>
    </ul>
    <p>Si tenés alguna duda, podés consultar con el equipo de Relaciones Laborales.</p>
  </div>
  <div style="padding:16px 24px;background:#f9fafb;text-align:center;color:#6b7280;font-size:12px;">
    <p><em>Equipo de Relaciones Laborales — HubGH</em></p>
  </div>
</div>""",
    ),
    (
        "traslado_pdv_jefe_origen_programado",
        "Salida de {{ empleado.nombres }} {{ empleado.apellidos }} desde {{ traslado.pdv_origen }} — {{ traslado.fecha_aplicacion }}",
        """<div style="font-family:Arial,sans-serif;max-width:600px;margin:0 auto;">
  <div style="background:#111;padding:20px;text-align:center;">
    <img src="/assets/hubgh/images/logo-circular-black.png" alt="HubGH" style="height:40px;filter:invert(1);">
  </div>
  <div style="padding:32px 24px;background:#ffffff;">
    <p>Estimado/a {% if jefe_origen %}{{ jefe_origen.full_name }}{% else %}Jefe/a de PDV{% endif %},</p>
    <p>Le informamos que <strong>{{ empleado.nombres }} {{ empleado.apellidos }}</strong>
    ha sido programado/a para un traslado desde su PDV.</p>
    <table style="width:100%;border-collapse:collapse;margin:20px 0;">
      <tr style="background:#f3f4f6;">
        <td style="padding:10px;border:1px solid #e5e7eb;font-weight:bold;width:40%;">Colaborador</td>
        <td style="padding:10px;border:1px solid #e5e7eb;">{{ empleado.nombres }} {{ empleado.apellidos }}</td>
      </tr>
      <tr>
        <td style="padding:10px;border:1px solid #e5e7eb;font-weight:bold;">PDV origen</td>
        <td style="padding:10px;border:1px solid #e5e7eb;">{{ traslado.pdv_origen }}</td>
      </tr>
      <tr style="background:#f3f4f6;">
        <td style="padding:10px;border:1px solid #e5e7eb;font-weight:bold;">PDV destino</td>
        <td style="padding:10px;border:1px solid #e5e7eb;">{{ traslado.pdv_destino }}</td>
      </tr>
      <tr>
        <td style="padding:10px;border:1px solid #e5e7eb;font-weight:bold;">Fecha de aplicación</td>
        <td style="padding:10px;border:1px solid #e5e7eb;"><strong>{{ traslado.fecha_aplicacion }}</strong></td>
      </tr>
      <tr style="background:#f3f4f6;">
        <td style="padding:10px;border:1px solid #e5e7eb;font-weight:bold;">Motivo</td>
        <td style="padding:10px;border:1px solid #e5e7eb;">{{ traslado.motivo_label }}</td>
      </tr>
    </table>
    <p><strong>Acción requerida:</strong> Por favor coordine con el/la colaborador/a la entrega de turno
    y cualquier documentación pendiente antes de la fecha de aplicación.</p>
    <p style="color:#6b7280;font-size:13px;">Nota: El motivo detallado del traslado es confidencial
    y no se comparte en esta notificación.</p>
  </div>
  <div style="padding:16px 24px;background:#f9fafb;text-align:center;color:#6b7280;font-size:12px;">
    <p><em>Equipo de Relaciones Laborales — HubGH</em></p>
  </div>
</div>""",
    ),
    (
        "traslado_pdv_jefe_destino_programado",
        "Llegada de {{ empleado.nombres }} {{ empleado.apellidos }} a {{ traslado.pdv_destino }} — {{ traslado.fecha_aplicacion }}",
        """<div style="font-family:Arial,sans-serif;max-width:600px;margin:0 auto;">
  <div style="background:#111;padding:20px;text-align:center;">
    <img src="/assets/hubgh/images/logo-circular-black.png" alt="HubGH" style="height:40px;filter:invert(1);">
  </div>
  <div style="padding:32px 24px;background:#ffffff;">
    <p>Estimado/a {% if jefe_destino %}{{ jefe_destino.full_name }}{% else %}Jefe/a de PDV{% endif %},</p>
    <p>Le informamos que <strong>{{ empleado.nombres }} {{ empleado.apellidos }}</strong>
    se incorporará a su PDV próximamente.</p>
    <table style="width:100%;border-collapse:collapse;margin:20px 0;">
      <tr style="background:#f3f4f6;">
        <td style="padding:10px;border:1px solid #e5e7eb;font-weight:bold;width:40%;">Colaborador</td>
        <td style="padding:10px;border:1px solid #e5e7eb;">{{ empleado.nombres }} {{ empleado.apellidos }}</td>
      </tr>
      <tr>
        <td style="padding:10px;border:1px solid #e5e7eb;font-weight:bold;">Viene desde</td>
        <td style="padding:10px;border:1px solid #e5e7eb;">{{ traslado.pdv_origen }}</td>
      </tr>
      <tr style="background:#f3f4f6;">
        <td style="padding:10px;border:1px solid #e5e7eb;font-weight:bold;">PDV destino (su PDV)</td>
        <td style="padding:10px;border:1px solid #e5e7eb;"><strong>{{ traslado.pdv_destino }}</strong></td>
      </tr>
      <tr>
        <td style="padding:10px;border:1px solid #e5e7eb;font-weight:bold;">Fecha de incorporación</td>
        <td style="padding:10px;border:1px solid #e5e7eb;"><strong>{{ traslado.fecha_aplicacion }}</strong></td>
      </tr>
      {% if traslado.cargo_destino %}
      <tr style="background:#f3f4f6;">
        <td style="padding:10px;border:1px solid #e5e7eb;font-weight:bold;">Cargo asignado</td>
        <td style="padding:10px;border:1px solid #e5e7eb;">{{ traslado.cargo_destino }}</td>
      </tr>
      {% endif %}
    </table>
    <p><strong>Acción requerida:</strong> Por favor prepare el puesto de trabajo y los accesos
    necesarios antes de la fecha de incorporación.</p>
  </div>
  <div style="padding:16px 24px;background:#f9fafb;text-align:center;color:#6b7280;font-size:12px;">
    <p><em>Equipo de Relaciones Laborales — HubGH</em></p>
  </div>
</div>""",
    ),
    (
        "traslado_pdv_aplicado_confirmacion",
        "Traslado aplicado: {{ empleado.nombres }} {{ empleado.apellidos }} ahora en {{ traslado.pdv_destino }}",
        """<div style="font-family:Arial,sans-serif;max-width:600px;margin:0 auto;">
  <div style="background:#111;padding:20px;text-align:center;">
    <img src="/assets/hubgh/images/logo-circular-black.png" alt="HubGH" style="height:40px;filter:invert(1);">
  </div>
  <div style="padding:32px 24px;background:#ffffff;">
    <div style="background:#d1fae5;border-left:4px solid #059669;padding:12px 16px;margin-bottom:24px;border-radius:4px;">
      <strong style="color:#065f46;">Traslado aplicado exitosamente</strong>
    </div>
    <p>El traslado de <strong>{{ empleado.nombres }} {{ empleado.apellidos }}</strong>
    ha sido <strong>ejecutado</strong>. El sistema ha sido actualizado.</p>
    <table style="width:100%;border-collapse:collapse;margin:20px 0;">
      <tr style="background:#f3f4f6;">
        <td style="padding:10px;border:1px solid #e5e7eb;font-weight:bold;width:40%;">Colaborador</td>
        <td style="padding:10px;border:1px solid #e5e7eb;">{{ empleado.nombres }} {{ empleado.apellidos }}</td>
      </tr>
      <tr>
        <td style="padding:10px;border:1px solid #e5e7eb;font-weight:bold;">PDV anterior</td>
        <td style="padding:10px;border:1px solid #e5e7eb;">{{ traslado.pdv_origen }}</td>
      </tr>
      <tr style="background:#f3f4f6;">
        <td style="padding:10px;border:1px solid #e5e7eb;font-weight:bold;">Nuevo PDV</td>
        <td style="padding:10px;border:1px solid #e5e7eb;"><strong>{{ traslado.pdv_destino }}</strong></td>
      </tr>
      <tr>
        <td style="padding:10px;border:1px solid #e5e7eb;font-weight:bold;">Fecha de aplicación</td>
        <td style="padding:10px;border:1px solid #e5e7eb;">{{ traslado.fecha_aplicacion }}</td>
      </tr>
      <tr style="background:#f3f4f6;">
        <td style="padding:10px;border:1px solid #e5e7eb;font-weight:bold;">Aplicado por</td>
        <td style="padding:10px;border:1px solid #e5e7eb;">{{ aplicado_por }}</td>
      </tr>
      <tr>
        <td style="padding:10px;border:1px solid #e5e7eb;font-weight:bold;">Referencia</td>
        <td style="padding:10px;border:1px solid #e5e7eb;">{{ traslado.name }}</td>
      </tr>
    </table>
    <p style="color:#6b7280;font-size:13px;">Este es un correo automático de confirmación.
    El cambio ya está reflejado en el sistema.</p>
  </div>
  <div style="padding:16px 24px;background:#f9fafb;text-align:center;color:#6b7280;font-size:12px;">
    <p><em>Equipo de Relaciones Laborales — HubGH</em></p>
  </div>
</div>""",
    ),
]


def execute():
    """Carga los 4 Email Templates de Traslado PDV. Idempotente."""
    for name, subject, body in TEMPLATES:
        if frappe.db.exists("Email Template", name):
            continue
        try:
            frappe.get_doc({
                "doctype": "Email Template",
                "name": name,
                "subject": subject,
                "response": body,
                "enabled": 1,
                "use_html": 1,
            }).insert(ignore_permissions=True)
            frappe.logger("hubgh.patches").info(f"Created Email Template: {name}")
        except Exception as exc:
            frappe.log_error(
                message=str(exc),
                title=f"create_traslado_email_templates: fallo en {name}",
            )

    frappe.db.commit()
