# Copyright (c) 2026, Antigravity and contributors
# For license information, please see license.txt

"""
Patch idempotente: carga los 11 Email Templates de Terminacion Contrato.

Templates:
  R1 - terminacion_iniciada_sistemas
  R2 - terminacion_iniciada_rrll_dotacion
  R3 - terminacion_iniciada_operacion
  R4 - terminacion_examen_egreso_empleado
  R5 - terminacion_iniciada_compensacion
  R6 - terminacion_iniciada_jefe_pdv
  R7 - terminacion_carta_empleado
  R8 - terminacion_cerrada_rrll
  R9 - terminacion_recordatorio_subproceso
  C1 - carta_terminacion_justa_causa (plantilla PDF)
  C2 - carta_terminacion_periodo_prueba (plantilla PDF)

Variables Jinja disponibles por template — documentadas en cada entrada.
"""

import frappe


TEMPLATES = [
    # -----------------------------------------------------------------------
    # R1 — Sistemas: bloqueo credenciales
    # Context: empleado{nombres,apellidos,cedula}, terminacion{name,pdv_al_terminar,
    #          fecha_ultimo_dia,fecha_terminacion_efectiva,link_tc}
    # -----------------------------------------------------------------------
    (
        "terminacion_iniciada_sistemas",
        "Terminación iniciada — Bloqueo credenciales: {{ empleado.nombres }} {{ empleado.apellidos }}",
        """<div style="font-family:Arial,sans-serif;max-width:600px;margin:0 auto;">
  <div style="background:#111;padding:20px;text-align:center;">
    <img src="/assets/hubgh/images/logo-circular-black.png" alt="HubGH" style="height:40px;filter:invert(1);">
  </div>
  <div style="padding:32px 24px;background:#ffffff;">
    <div style="background:#fee2e2;border-left:4px solid #dc2626;padding:12px 16px;margin-bottom:24px;border-radius:4px;">
      <strong style="color:#991b1b;">Acción requerida: Revocar credenciales del sistema</strong>
    </div>
    <p>Equipo de Sistemas,</p>
    <p>Se ha iniciado el proceso de terminación de contrato para el/la siguiente colaborador/a.
    Por favor procedan con la revocación inmediata de todos los accesos al sistema.</p>
    <table style="width:100%;border-collapse:collapse;margin:20px 0;">
      <tr style="background:#f3f4f6;">
        <td style="padding:10px;border:1px solid #e5e7eb;font-weight:bold;width:40%;">Colaborador</td>
        <td style="padding:10px;border:1px solid #e5e7eb;">{{ empleado.nombres }} {{ empleado.apellidos }}</td>
      </tr>
      <tr>
        <td style="padding:10px;border:1px solid #e5e7eb;font-weight:bold;">Cédula</td>
        <td style="padding:10px;border:1px solid #e5e7eb;">{{ empleado.cedula }}</td>
      </tr>
      <tr style="background:#f3f4f6;">
        <td style="padding:10px;border:1px solid #e5e7eb;font-weight:bold;">PDV al terminar</td>
        <td style="padding:10px;border:1px solid #e5e7eb;">{{ terminacion.pdv_al_terminar }}</td>
      </tr>
      <tr>
        <td style="padding:10px;border:1px solid #e5e7eb;font-weight:bold;">Último día laborado</td>
        <td style="padding:10px;border:1px solid #e5e7eb;"><strong>{{ terminacion.fecha_ultimo_dia }}</strong></td>
      </tr>
      <tr style="background:#f3f4f6;">
        <td style="padding:10px;border:1px solid #e5e7eb;font-weight:bold;">Fecha terminación efectiva</td>
        <td style="padding:10px;border:1px solid #e5e7eb;"><strong>{{ terminacion.fecha_terminacion_efectiva }}</strong></td>
      </tr>
      <tr>
        <td style="padding:10px;border:1px solid #e5e7eb;font-weight:bold;">Referencia TC</td>
        <td style="padding:10px;border:1px solid #e5e7eb;"><a href="{{ terminacion.link_tc }}">{{ terminacion.name }}</a></td>
      </tr>
    </table>
    <p><strong>Acciones requeridas:</strong></p>
    <ul>
      <li>Deshabilitar cuenta de usuario en el sistema (el bloqueo digital ya fue ejecutado automáticamente)</li>
      <li>Revocar acceso a herramientas de terceros (correo corporativo, plataformas externas)</li>
      <li>Confirmar baja del colaborador en sistemas de nómina electrónica</li>
      <li>Archivar o reasignar datos en sistemas internos según protocolo de retiro</li>
    </ul>
    <p style="color:#6b7280;font-size:13px;">Este correo es una notificación automática. El bloqueo de acceso digital ya fue ejecutado por el sistema.</p>
  </div>
  <div style="padding:16px 24px;background:#f9fafb;text-align:center;color:#6b7280;font-size:12px;">
    <p><em>Equipo de Relaciones Laborales — HubGH</em></p>
  </div>
</div>""",
    ),
    # -----------------------------------------------------------------------
    # R2 — RRLL Dotacion: devolucion dotacion
    # Context: empleado{nombres,apellidos}, terminacion{pdv_al_terminar,link_tc}
    # -----------------------------------------------------------------------
    (
        "terminacion_iniciada_rrll_dotacion",
        "Terminación iniciada — Devolución dotación: {{ empleado.nombres }} {{ empleado.apellidos }}",
        """<div style="font-family:Arial,sans-serif;max-width:600px;margin:0 auto;">
  <div style="background:#111;padding:20px;text-align:center;">
    <img src="/assets/hubgh/images/logo-circular-black.png" alt="HubGH" style="height:40px;filter:invert(1);">
  </div>
  <div style="padding:32px 24px;background:#ffffff;">
    <p>Equipo de RRLL / Dotación,</p>
    <p>Se ha iniciado el proceso de terminación de contrato. Por favor coordinen la devolución de dotación y elementos de trabajo.</p>
    <table style="width:100%;border-collapse:collapse;margin:20px 0;">
      <tr style="background:#f3f4f6;">
        <td style="padding:10px;border:1px solid #e5e7eb;font-weight:bold;width:40%;">Colaborador</td>
        <td style="padding:10px;border:1px solid #e5e7eb;">{{ empleado.nombres }} {{ empleado.apellidos }}</td>
      </tr>
      <tr>
        <td style="padding:10px;border:1px solid #e5e7eb;font-weight:bold;">PDV al terminar</td>
        <td style="padding:10px;border:1px solid #e5e7eb;">{{ terminacion.pdv_al_terminar }}</td>
      </tr>
      <tr style="background:#f3f4f6;">
        <td style="padding:10px;border:1px solid #e5e7eb;font-weight:bold;">Último día laborado</td>
        <td style="padding:10px;border:1px solid #e5e7eb;"><strong>{{ terminacion.fecha_ultimo_dia }}</strong></td>
      </tr>
    </table>
    <p><strong>Acciones requeridas:</strong></p>
    <ul>
      <li>Verificar inventario de dotación asignada al colaborador</li>
      <li>Coordinar devolución de uniformes, EPP y elementos de trabajo antes del último día</li>
      <li>Registrar estado de devolución en el sistema de dotación</li>
    </ul>
    <p><a href="{{ terminacion.link_tc }}">Ver proceso de terminación</a></p>
  </div>
  <div style="padding:16px 24px;background:#f9fafb;text-align:center;color:#6b7280;font-size:12px;">
    <p><em>Equipo de Relaciones Laborales — HubGH</em></p>
  </div>
</div>""",
    ),
    # -----------------------------------------------------------------------
    # R3 — Operacion: desactivar Clonk
    # Context: empleado{nombres,apellidos,cedula}, terminacion{link_tc}
    # -----------------------------------------------------------------------
    (
        "terminacion_iniciada_operacion",
        "Terminación iniciada — Desactivar Clonk: {{ empleado.nombres }} {{ empleado.apellidos }}",
        """<div style="font-family:Arial,sans-serif;max-width:600px;margin:0 auto;">
  <div style="background:#111;padding:20px;text-align:center;">
    <img src="/assets/hubgh/images/logo-circular-black.png" alt="HubGH" style="height:40px;filter:invert(1);">
  </div>
  <div style="padding:32px 24px;background:#ffffff;">
    <p>Equipo de Operaciones,</p>
    <p>Se ha iniciado el proceso de terminación de contrato. Por favor procedan con la desactivación en el sistema de control de marcas (Clonk).</p>
    <table style="width:100%;border-collapse:collapse;margin:20px 0;">
      <tr style="background:#f3f4f6;">
        <td style="padding:10px;border:1px solid #e5e7eb;font-weight:bold;width:40%;">Colaborador</td>
        <td style="padding:10px;border:1px solid #e5e7eb;">{{ empleado.nombres }} {{ empleado.apellidos }}</td>
      </tr>
      <tr>
        <td style="padding:10px;border:1px solid #e5e7eb;font-weight:bold;">Cédula (identificador Clonk)</td>
        <td style="padding:10px;border:1px solid #e5e7eb;"><strong>{{ empleado.cedula }}</strong></td>
      </tr>
      <tr style="background:#f3f4f6;">
        <td style="padding:10px;border:1px solid #e5e7eb;font-weight:bold;">PDV al terminar</td>
        <td style="padding:10px;border:1px solid #e5e7eb;">{{ terminacion.pdv_al_terminar }}</td>
      </tr>
      <tr>
        <td style="padding:10px;border:1px solid #e5e7eb;font-weight:bold;">Último día laborado</td>
        <td style="padding:10px;border:1px solid #e5e7eb;"><strong>{{ terminacion.fecha_ultimo_dia }}</strong></td>
      </tr>
    </table>
    <p><strong>Acción requerida:</strong> Desactivar marcas del colaborador en Clonk con cédula <strong>{{ empleado.cedula }}</strong> a partir del último día laborado.</p>
    <p><a href="{{ terminacion.link_tc }}">Ver proceso de terminación</a></p>
  </div>
  <div style="padding:16px 24px;background:#f9fafb;text-align:center;color:#6b7280;font-size:12px;">
    <p><em>Equipo de Relaciones Laborales — HubGH</em></p>
  </div>
</div>""",
    ),
    # -----------------------------------------------------------------------
    # R4 — Empleado: instructivo examen de egreso (5 dias habiles)
    # Context: empleado{nombres}, fecha_limite, link_agendamiento
    # -----------------------------------------------------------------------
    (
        "terminacion_examen_egreso_empleado",
        "Examen médico de egreso — {{ empleado.nombres }} {{ empleado.apellidos }}",
        """<div style="font-family:Arial,sans-serif;max-width:600px;margin:0 auto;">
  <div style="background:#111;padding:20px;text-align:center;">
    <img src="/assets/hubgh/images/logo-circular-black.png" alt="HubGH" style="height:40px;filter:invert(1);">
  </div>
  <div style="padding:32px 24px;background:#ffffff;">
    <p>Hola <strong>{{ empleado.nombres }}</strong>,</p>
    <p>Como parte del proceso de terminación de tu contrato, estás en obligación de realizarte el <strong>examen médico de egreso</strong> antes de tu último día laborado.</p>
    <div style="background:#fef9c3;border-left:4px solid #ca8a04;padding:12px 16px;margin:24px 0;border-radius:4px;">
      <strong style="color:#713f12;">Fecha límite: {{ fecha_limite }}</strong><br>
      <span style="color:#713f12;font-size:13px;">Tienes 5 días hábiles para agendar y realizarte el examen.</span>
    </div>
    <p><strong>¿Cómo agendar?</strong></p>
    <ol>
      <li>Hacé clic en el botón de abajo</li>
      <li>Seleccioná la fecha y hora disponible en la IPS</li>
      <li>Confirmá tu cita — recibirás un correo de confirmación</li>
    </ol>
    <p style="text-align:center;margin:32px 0;">
      <a href="{{ link_agendamiento }}" style="background:#1d4ed8;color:#fff;padding:14px 32px;border-radius:8px;text-decoration:none;font-weight:600;display:inline-block;">Agendar mi examen médico de egreso</a>
    </p>
    <p style="color:#6b7280;font-size:13px;">Si tenés alguna duda, comunicate con el equipo de SST: <a href="mailto:SST@homeburgers.com">SST@homeburgers.com</a></p>
    <p style="color:#6b7280;font-size:13px;">Este es un requisito legal. No realizarlo puede generar consecuencias administrativas.</p>
  </div>
  <div style="padding:16px 24px;background:#f9fafb;text-align:center;color:#6b7280;font-size:12px;">
    <p><em>Equipo de SST / Relaciones Laborales — HubGH</em></p>
  </div>
</div>""",
    ),
    # -----------------------------------------------------------------------
    # R5 — Compensacion: liquidacion pendiente
    # Context: empleado{nombres,apellidos}, terminacion{fecha_ultimo_dia,
    #          fecha_terminacion_efectiva,link_tc}
    # -----------------------------------------------------------------------
    (
        "terminacion_iniciada_compensacion",
        "Terminación iniciada — Liquidación pendiente: {{ empleado.nombres }} {{ empleado.apellidos }}",
        """<div style="font-family:Arial,sans-serif;max-width:600px;margin:0 auto;">
  <div style="background:#111;padding:20px;text-align:center;">
    <img src="/assets/hubgh/images/logo-circular-black.png" alt="HubGH" style="height:40px;filter:invert(1);">
  </div>
  <div style="padding:32px 24px;background:#ffffff;">
    <p>Equipo de Compensación y Beneficios,</p>
    <p>Se ha iniciado el proceso de terminación de contrato. Por favor procedan con el cálculo y gestión de la liquidación correspondiente.</p>
    <table style="width:100%;border-collapse:collapse;margin:20px 0;">
      <tr style="background:#f3f4f6;">
        <td style="padding:10px;border:1px solid #e5e7eb;font-weight:bold;width:40%;">Colaborador</td>
        <td style="padding:10px;border:1px solid #e5e7eb;">{{ empleado.nombres }} {{ empleado.apellidos }}</td>
      </tr>
      <tr>
        <td style="padding:10px;border:1px solid #e5e7eb;font-weight:bold;">Último día laborado</td>
        <td style="padding:10px;border:1px solid #e5e7eb;"><strong>{{ terminacion.fecha_ultimo_dia }}</strong></td>
      </tr>
      <tr style="background:#f3f4f6;">
        <td style="padding:10px;border:1px solid #e5e7eb;font-weight:bold;">Fecha terminación efectiva</td>
        <td style="padding:10px;border:1px solid #e5e7eb;"><strong>{{ terminacion.fecha_terminacion_efectiva }}</strong></td>
      </tr>
      <tr>
        <td style="padding:10px;border:1px solid #e5e7eb;font-weight:bold;">PDV al terminar</td>
        <td style="padding:10px;border:1px solid #e5e7eb;">{{ terminacion.pdv_al_terminar }}</td>
      </tr>
    </table>
    <p><strong>Acciones requeridas:</strong></p>
    <ul>
      <li>Calcular liquidación definitiva (vacaciones, primas, cesantías)</li>
      <li>Verificar descuentos pendientes (libranzas, préstamos internos)</li>
      <li>Preparar colilla de liquidación para firma</li>
      <li>Notificar fecha de pago al colaborador</li>
    </ul>
    <p><a href="{{ terminacion.link_tc }}">Ver proceso de terminación</a></p>
  </div>
  <div style="padding:16px 24px;background:#f9fafb;text-align:center;color:#6b7280;font-size:12px;">
    <p><em>Equipo de Relaciones Laborales — HubGH</em></p>
  </div>
</div>""",
    ),
    # -----------------------------------------------------------------------
    # R6 — Jefe PDV: notificacion de terminacion en su PDV
    # Context: empleado{nombres,apellidos}, terminacion{fecha_ultimo_dia,link_tc}
    # -----------------------------------------------------------------------
    (
        "terminacion_iniciada_jefe_pdv",
        "Terminación en tu PDV — {{ empleado.nombres }} {{ empleado.apellidos }}",
        """<div style="font-family:Arial,sans-serif;max-width:600px;margin:0 auto;">
  <div style="background:#111;padding:20px;text-align:center;">
    <img src="/assets/hubgh/images/logo-circular-black.png" alt="HubGH" style="height:40px;filter:invert(1);">
  </div>
  <div style="padding:32px 24px;background:#ffffff;">
    <p>Estimado/a Jefe/a de PDV,</p>
    <p>Le informamos que se ha iniciado el proceso de terminación de contrato para un colaborador de su punto de venta.</p>
    <table style="width:100%;border-collapse:collapse;margin:20px 0;">
      <tr style="background:#f3f4f6;">
        <td style="padding:10px;border:1px solid #e5e7eb;font-weight:bold;width:40%;">Colaborador</td>
        <td style="padding:10px;border:1px solid #e5e7eb;">{{ empleado.nombres }} {{ empleado.apellidos }}</td>
      </tr>
      <tr>
        <td style="padding:10px;border:1px solid #e5e7eb;font-weight:bold;">Último día laborado</td>
        <td style="padding:10px;border:1px solid #e5e7eb;"><strong>{{ terminacion.fecha_ultimo_dia }}</strong></td>
      </tr>
    </table>
    <p><strong>Acciones requeridas:</strong></p>
    <ul>
      <li>Garantizar la entrega del turno y documentación antes del último día</li>
      <li>Coordinar con RRHH cualquier novedad operativa relacionada con la salida</li>
      <li>Marcar el subproceso de su área como completado en el sistema una vez gestionado</li>
    </ul>
    <p style="color:#6b7280;font-size:13px;">El detalle del motivo de la terminación es confidencial y no se comparte en esta notificación.</p>
    <p><a href="{{ terminacion.link_tc }}">Ver proceso de terminación</a></p>
  </div>
  <div style="padding:16px 24px;background:#f9fafb;text-align:center;color:#6b7280;font-size:12px;">
    <p><em>Equipo de Relaciones Laborales — HubGH</em></p>
  </div>
</div>""",
    ),
    # -----------------------------------------------------------------------
    # R7 — Empleado: comunicacion oficial + carta adjunta (si aplica)
    # Context: empleado{nombres,apellidos}, terminacion{causal_nombre,
    #          fecha_terminacion_efectiva}, carta_terminacion_url (puede ser None)
    # -----------------------------------------------------------------------
    (
        "terminacion_carta_empleado",
        "Comunicación oficial de terminación — {{ empleado.nombres }} {{ empleado.apellidos }}",
        """<div style="font-family:Arial,sans-serif;max-width:600px;margin:0 auto;">
  <div style="background:#111;padding:20px;text-align:center;">
    <img src="/assets/hubgh/images/logo-circular-black.png" alt="HubGH" style="height:40px;filter:invert(1);">
  </div>
  <div style="padding:32px 24px;background:#ffffff;">
    <p>Estimado/a <strong>{{ empleado.nombres }} {{ empleado.apellidos }}</strong>,</p>
    <p>Le comunicamos que la empresa ha tomado la decisión de dar por terminado su contrato de trabajo, con base en la siguiente causal:</p>
    <div style="background:#f3f4f6;padding:16px;border-radius:4px;margin:20px 0;">
      <strong>Causal:</strong> {{ terminacion.causal_nombre }}<br>
      <strong>Fecha de terminación efectiva:</strong> {{ terminacion.fecha_terminacion_efectiva }}
    </div>
    {% if carta_terminacion_url %}
    <p>Adjunto encontrará la carta formal de terminación. Por favor revísela con atención.</p>
    <p style="text-align:center;margin:24px 0;">
      <a href="{{ carta_terminacion_url }}" style="background:#1d4ed8;color:#fff;padding:12px 28px;border-radius:8px;text-decoration:none;font-weight:600;display:inline-block;">Descargar carta de terminación</a>
    </p>
    {% endif %}
    <p>Le recordamos que tiene derecho a:</p>
    <ul>
      <li>Recibir la liquidación de prestaciones sociales</li>
      <li>Realizarse el examen médico de egreso (ver correo aparte del equipo SST)</li>
      <li>Solicitar la certificación laboral por el tiempo trabajado</li>
    </ul>
    <p>Para cualquier inquietud, puede contactarse con el equipo de Relaciones Laborales.</p>
  </div>
  <div style="padding:16px 24px;background:#f9fafb;text-align:center;color:#6b7280;font-size:12px;">
    <p><em>Equipo de Relaciones Laborales — HubGH</em></p>
  </div>
</div>""",
    ),
    # -----------------------------------------------------------------------
    # R8 — RRLL: confirmacion de cierre del proceso
    # Context: empleado{nombres,apellidos}, terminacion{causal_nombre,resumen_cierre},
    #          subprocesos_resumen
    # -----------------------------------------------------------------------
    (
        "terminacion_cerrada_rrll",
        "Terminación cerrada — {{ empleado.nombres }} {{ empleado.apellidos }}",
        """<div style="font-family:Arial,sans-serif;max-width:600px;margin:0 auto;">
  <div style="background:#111;padding:20px;text-align:center;">
    <img src="/assets/hubgh/images/logo-circular-black.png" alt="HubGH" style="height:40px;filter:invert(1);">
  </div>
  <div style="padding:32px 24px;background:#ffffff;">
    <div style="background:#d1fae5;border-left:4px solid #059669;padding:12px 16px;margin-bottom:24px;border-radius:4px;">
      <strong style="color:#065f46;">Proceso de terminación cerrado exitosamente</strong>
    </div>
    <p>El proceso de terminación de contrato para <strong>{{ empleado.nombres }} {{ empleado.apellidos }}</strong> ha sido cerrado.</p>
    <table style="width:100%;border-collapse:collapse;margin:20px 0;">
      <tr style="background:#f3f4f6;">
        <td style="padding:10px;border:1px solid #e5e7eb;font-weight:bold;width:40%;">Colaborador</td>
        <td style="padding:10px;border:1px solid #e5e7eb;">{{ empleado.nombres }} {{ empleado.apellidos }}</td>
      </tr>
      <tr>
        <td style="padding:10px;border:1px solid #e5e7eb;font-weight:bold;">Causal</td>
        <td style="padding:10px;border:1px solid #e5e7eb;">{{ terminacion.causal_nombre }}</td>
      </tr>
      <tr style="background:#f3f4f6;">
        <td style="padding:10px;border:1px solid #e5e7eb;font-weight:bold;">Resumen de cierre</td>
        <td style="padding:10px;border:1px solid #e5e7eb;">{{ terminacion.resumen_cierre }}</td>
      </tr>
      {% if subprocesos_resumen %}
      <tr>
        <td style="padding:10px;border:1px solid #e5e7eb;font-weight:bold;">Estado subprocesos</td>
        <td style="padding:10px;border:1px solid #e5e7eb;">{{ subprocesos_resumen }}</td>
      </tr>
      {% endif %}
    </table>
    <p style="color:#6b7280;font-size:13px;">Este correo es una confirmación automática del cierre del proceso en el sistema.</p>
  </div>
  <div style="padding:16px 24px;background:#f9fafb;text-align:center;color:#6b7280;font-size:12px;">
    <p><em>Equipo de Relaciones Laborales — HubGH</em></p>
  </div>
</div>""",
    ),
    # -----------------------------------------------------------------------
    # R9 — Recordatorio: subproceso pendiente (cron diario)
    # Context: empleado{nombres,apellidos}, area, area_nombre, fecha_limite_subproceso,
    #          terminacion{link_tc}
    # -----------------------------------------------------------------------
    (
        "terminacion_recordatorio_subproceso",
        "Recordatorio: subproceso pendiente {{ area_nombre }} — {{ empleado.nombres }} {{ empleado.apellidos }}",
        """<div style="font-family:Arial,sans-serif;max-width:600px;margin:0 auto;">
  <div style="background:#111;padding:20px;text-align:center;">
    <img src="/assets/hubgh/images/logo-circular-black.png" alt="HubGH" style="height:40px;filter:invert(1);">
  </div>
  <div style="padding:32px 24px;background:#ffffff;">
    <div style="background:#fef3c7;border-left:4px solid #d97706;padding:12px 16px;margin-bottom:24px;border-radius:4px;">
      <strong style="color:#92400e;">Recordatorio automático: acción pendiente</strong>
    </div>
    <p>Equipo de <strong>{{ area_nombre }}</strong>,</p>
    <p>El subproceso de terminación asignado a su área aún está pendiente de completar.</p>
    <table style="width:100%;border-collapse:collapse;margin:20px 0;">
      <tr style="background:#f3f4f6;">
        <td style="padding:10px;border:1px solid #e5e7eb;font-weight:bold;width:40%;">Colaborador</td>
        <td style="padding:10px;border:1px solid #e5e7eb;">{{ empleado.nombres }} {{ empleado.apellidos }}</td>
      </tr>
      <tr>
        <td style="padding:10px;border:1px solid #e5e7eb;font-weight:bold;">Área responsable</td>
        <td style="padding:10px;border:1px solid #e5e7eb;">{{ area_nombre }}</td>
      </tr>
      <tr style="background:#f3f4f6;">
        <td style="padding:10px;border:1px solid #e5e7eb;font-weight:bold;">Fecha límite</td>
        <td style="padding:10px;border:1px solid #e5e7eb;"><strong>{{ fecha_limite_subproceso }}</strong></td>
      </tr>
    </table>
    <p>Por favor ingrese al sistema y marque el subproceso como completado una vez realizada la gestión.</p>
    <p><a href="{{ terminacion.link_tc }}">Acceder al proceso de terminación</a></p>
    <p style="color:#6b7280;font-size:13px;">Este recordatorio es automático y se envía diariamente hasta que el subproceso sea marcado como completado.</p>
  </div>
  <div style="padding:16px 24px;background:#f9fafb;text-align:center;color:#6b7280;font-size:12px;">
    <p><em>Equipo de Relaciones Laborales — HubGH</em></p>
  </div>
</div>""",
    ),
    # -----------------------------------------------------------------------
    # Carta C1 — Justa causa (HTML formal para renderizar a PDF)
    # Context: empleado{nombres,apellidos,cedula,cargo}, terminacion{fecha_terminacion_efectiva,
    #          cargo_al_terminar}, causal_descripcion, justificacion
    # -----------------------------------------------------------------------
    (
        "carta_terminacion_justa_causa",
        "Carta de terminación con justa causa — {{ empleado.nombres }} {{ empleado.apellidos }}",
        """<!DOCTYPE html>
<html lang="es">
<head>
  <meta charset="UTF-8">
  <style>
    body { font-family: Arial, sans-serif; font-size: 12pt; color: #111; margin: 0; padding: 0; }
    .page { padding: 60px 72px; max-width: 720px; margin: 0 auto; }
    .header { text-align: right; margin-bottom: 48px; }
    .header-logo { height: 48px; }
    .fecha { text-align: right; color: #444; margin-bottom: 32px; }
    h2 { text-align: center; font-size: 14pt; margin-bottom: 32px; text-transform: uppercase; letter-spacing: 0.04em; }
    .datos-empleado { margin-bottom: 24px; }
    .datos-empleado table { width: 100%; border-collapse: collapse; }
    .datos-empleado td { padding: 6px 12px; border: 1px solid #ddd; font-size: 11pt; }
    .datos-empleado td:first-child { font-weight: bold; background: #f9fafb; width: 40%; }
    p { line-height: 1.7; margin-bottom: 16px; text-align: justify; }
    .firma { margin-top: 80px; }
    .firma-linea { border-top: 1px solid #111; width: 260px; margin-top: 64px; }
    .firma-nombre { font-weight: bold; margin-top: 8px; }
    .firma-cargo { color: #555; font-size: 10pt; }
    .pie { margin-top: 64px; padding-top: 16px; border-top: 1px solid #e5e7eb; text-align: center; color: #6b7280; font-size: 9pt; }
  </style>
</head>
<body>
<div class="page">
  <div class="header">
    <img src="/assets/hubgh/images/logo-circular-black.png" alt="HubGH" class="header-logo">
  </div>
  <div class="fecha">{{ terminacion.fecha_terminacion_efectiva }}</div>
  <h2>Comunicado de Terminación de Contrato con Justa Causa</h2>
  <div class="datos-empleado">
    <table>
      <tr><td>Nombre completo</td><td>{{ empleado.nombres }} {{ empleado.apellidos }}</td></tr>
      <tr><td>Cédula de ciudadanía</td><td>{{ empleado.cedula }}</td></tr>
      <tr><td>Cargo desempeñado</td><td>{{ terminacion.cargo_al_terminar }}</td></tr>
      <tr><td>Fecha de terminación efectiva</td><td>{{ terminacion.fecha_terminacion_efectiva }}</td></tr>
    </table>
  </div>
  <p>Por medio de la presente comunicación, le informamos que la empresa ha tomado la decisión de dar por terminado
  su contrato de trabajo con justa causa, de conformidad con lo establecido en el literal <strong>a)</strong> del
  Artículo 62 del Código Sustantivo del Trabajo, y demás normas concordantes.</p>
  <p><strong>Hechos que motivan la terminación:</strong></p>
  <p>{{ causal_descripcion }}</p>
  <p>{{ justificacion }}</p>
  <p>En virtud de lo anterior, la empresa ejerció su facultad disciplinaria y tomó la decisión de prescindir de sus servicios.
  Hacemos constar que se han seguido los procedimientos establecidos en el Reglamento Interno de Trabajo y en la legislación laboral colombiana vigente.</p>
  <p>La presente notificación se realiza en cumplimiento del Artículo 62 del Código Sustantivo del Trabajo.
  La liquidación de prestaciones sociales será cancelada dentro de los términos legales establecidos.</p>
  <div class="firma">
    <p>Atentamente,</p>
    <div class="firma-linea"></div>
    <p class="firma-nombre">Gerencia de Gestión Humana</p>
    <p class="firma-cargo">Comidas Varpel S.A.S.</p>
  </div>
  <div class="pie">
    <p>Comidas Varpel S.A.S. &mdash; NIT: XXX.XXX.XXX-X &mdash; Bogotá, Colombia</p>
    <p>Este documento es de carácter confidencial y tiene efectos legales.</p>
  </div>
</div>
</body>
</html>""",
    ),
    # -----------------------------------------------------------------------
    # Carta C2 — Periodo de prueba
    # Context: empleado{nombres,apellidos,cedula}, terminacion{fecha_terminacion_efectiva,
    #          cargo_al_terminar}, contrato_fecha_inicio
    # -----------------------------------------------------------------------
    (
        "carta_terminacion_periodo_prueba",
        "Carta de terminación en periodo de prueba — {{ empleado.nombres }} {{ empleado.apellidos }}",
        """<!DOCTYPE html>
<html lang="es">
<head>
  <meta charset="UTF-8">
  <style>
    body { font-family: Arial, sans-serif; font-size: 12pt; color: #111; margin: 0; padding: 0; }
    .page { padding: 60px 72px; max-width: 720px; margin: 0 auto; }
    .header { text-align: right; margin-bottom: 48px; }
    .header-logo { height: 48px; }
    .fecha { text-align: right; color: #444; margin-bottom: 32px; }
    h2 { text-align: center; font-size: 14pt; margin-bottom: 32px; text-transform: uppercase; letter-spacing: 0.04em; }
    .datos-empleado { margin-bottom: 24px; }
    .datos-empleado table { width: 100%; border-collapse: collapse; }
    .datos-empleado td { padding: 6px 12px; border: 1px solid #ddd; font-size: 11pt; }
    .datos-empleado td:first-child { font-weight: bold; background: #f9fafb; width: 40%; }
    p { line-height: 1.7; margin-bottom: 16px; text-align: justify; }
    .firma { margin-top: 80px; }
    .firma-linea { border-top: 1px solid #111; width: 260px; margin-top: 64px; }
    .firma-nombre { font-weight: bold; margin-top: 8px; }
    .firma-cargo { color: #555; font-size: 10pt; }
    .pie { margin-top: 64px; padding-top: 16px; border-top: 1px solid #e5e7eb; text-align: center; color: #6b7280; font-size: 9pt; }
  </style>
</head>
<body>
<div class="page">
  <div class="header">
    <img src="/assets/hubgh/images/logo-circular-black.png" alt="HubGH" class="header-logo">
  </div>
  <div class="fecha">{{ terminacion.fecha_terminacion_efectiva }}</div>
  <h2>Comunicado de Terminación de Contrato Durante Periodo de Prueba</h2>
  <div class="datos-empleado">
    <table>
      <tr><td>Nombre completo</td><td>{{ empleado.nombres }} {{ empleado.apellidos }}</td></tr>
      <tr><td>Cédula de ciudadanía</td><td>{{ empleado.cedula }}</td></tr>
      <tr><td>Cargo desempeñado</td><td>{{ terminacion.cargo_al_terminar }}</td></tr>
      <tr><td>Fecha de inicio del contrato</td><td>{{ contrato_fecha_inicio }}</td></tr>
      <tr><td>Fecha de terminación efectiva</td><td>{{ terminacion.fecha_terminacion_efectiva }}</td></tr>
    </table>
  </div>
  <p>Por medio de la presente comunicación, le informamos que la empresa ha tomado la decisión de dar por terminado
  su contrato de trabajo durante el periodo de prueba, haciendo uso de la facultad conferida por el
  Artículo 78 del Código Sustantivo del Trabajo colombiano.</p>
  <p>El periodo de prueba tiene como finalidad que las partes evalúen las condiciones de la relación laboral.
  Habiendo concluido dicha evaluación, la empresa ha determinado que no continuará con la vinculación.</p>
  <p>La liquidación de las prestaciones sociales proporcionales al tiempo laborado será cancelada
  dentro de los términos legales establecidos.</p>
  <p>Agradecemos su disposición durante el tiempo trabajado en nuestra organización.</p>
  <div class="firma">
    <p>Atentamente,</p>
    <div class="firma-linea"></div>
    <p class="firma-nombre">Gerencia de Gestión Humana</p>
    <p class="firma-cargo">Comidas Varpel S.A.S.</p>
  </div>
  <div class="pie">
    <p>Comidas Varpel S.A.S. &mdash; NIT: XXX.XXX.XXX-X &mdash; Bogotá, Colombia</p>
    <p>Este documento es de carácter confidencial y tiene efectos legales.</p>
  </div>
</div>
</body>
</html>""",
    ),
]


def execute():
    """Carga los 11 Email Templates de Terminacion Contrato. Idempotente."""
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
                title=f"create_terminacion_email_templates: fallo en {name}",
            )

    frappe.db.commit()
