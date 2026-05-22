# Copyright (c) 2026, Antigravity and contributors
# For license information, please see license.txt

"""
examen_egreso_service.py — Servicio para Cita Examen Egreso.

ADR-3 (design §2): Cita Examen Egreso es un DocType SEPARADO de Cita Examen Medico.
No hereda, no extiende, no comparte schema.

Funciones públicas:
- crear_examen_egreso(terminacion_doc) → str (CXE name)
- marcar_realizada(cita_name) → dict
- cancelar_si_pendiente(cita_name) → dict
- process_scheduled_recordatorios() → dict (cron diario)

Import path: hubgh.hubgh.services.examen_egreso_service
"""

from __future__ import annotations

from datetime import date, timedelta

import frappe
from frappe.utils import today

from hubgh.hubgh.services.notification_resolver import resolve_employee_email
from hubgh.hubgh.services.email_dispatcher import dispatch_email


# Número de días hábiles para fecha_limite
_DIAS_HABILES_EXAMEN = 5

# Días de anticipación para recordatorio
_DIAS_RECORDATORIO = 2


# ---------------------------------------------------------------------------
# Públicas
# ---------------------------------------------------------------------------

def crear_examen_egreso(terminacion_doc) -> str:
    """
    Crea una Cita Examen Egreso para la terminación.

    Flujo:
    1. Calcula fecha_limite = today() + 5 días hábiles (Lun-Vie).
    2. Genera token único via frappe.generate_hash(length=24).
    3. Crea Cita Examen Egreso con estado='Pendiente Agendamiento'.
    4. Dispara email R4 (terminacion_iniciada_sst_empleado) al empleado.
    5. Retorna CXE.name.

    Args:
        terminacion_doc: Instancia de Terminacion Contrato.

    Returns:
        str: Nombre de la Cita Examen Egreso creada.
    """
    hoy = today()
    if isinstance(hoy, str):
        from frappe.utils import getdate
        hoy = getdate(hoy)
    fecha_limite = _dias_habiles(hoy, _DIAS_HABILES_EXAMEN)

    token = frappe.generate_hash(length=24)

    cita_doc = frappe.get_doc({
        "doctype": "Cita Examen Egreso",
        "empleado": terminacion_doc.empleado,
        "terminacion_origen": terminacion_doc.name,
        "fecha_limite": fecha_limite,
        "estado": "Pendiente Agendamiento",
        "token": token,
    })
    cita_doc.insert(ignore_permissions=True)

    # Despachar R4 al empleado
    emp_email = resolve_employee_email(terminacion_doc.empleado)
    context = {
        "empleado": terminacion_doc.empleado,
        "fecha_limite": str(fecha_limite),
        "link_agendamiento": f"/app/cita-examen-egreso/{cita_doc.name}?token={token}",
        "tc_name": terminacion_doc.name,
    }
    dispatch_email(
        template_name="terminacion_iniciada_sst_empleado",
        recipients=[emp_email] if emp_email else [],
        context=context,
    )

    return cita_doc.name


def marcar_realizada(cita_name: str) -> dict:
    """
    Marca una Cita Examen Egreso como Realizada.

    Para uso futuro de SST.

    Args:
        cita_name: Nombre de la Cita Examen Egreso.

    Returns:
        dict: {ok: bool, cita: str, estado: str}
    """
    cita = frappe.get_doc("Cita Examen Egreso", cita_name)
    cita.db_set("estado", "Realizada")
    return {"ok": True, "cita": cita_name, "estado": "Realizada"}


def cancelar_si_pendiente(cita_name: str | None) -> dict:
    """
    Cancela una Cita Examen Egreso si está en estado Pendiente Agendamiento.

    Idempotente: si la cita ya está en otro estado, no hace nada.

    Args:
        cita_name: Nombre de la Cita, o None (retorna sin hacer nada).

    Returns:
        dict: {ok: bool, cancelled: bool, reason: str}
    """
    if not cita_name:
        return {"ok": True, "cancelled": False, "reason": "no_cita"}

    if not frappe.db.exists("Cita Examen Egreso", cita_name):
        return {"ok": True, "cancelled": False, "reason": "not_found"}

    estado_actual = frappe.db.get_value("Cita Examen Egreso", cita_name, "estado")
    if estado_actual != "Pendiente Agendamiento":
        return {"ok": True, "cancelled": False, "reason": f"estado_{estado_actual}"}

    frappe.db.set_value("Cita Examen Egreso", cita_name, "estado", "No Realizada")
    return {"ok": True, "cancelled": True, "reason": "pendiente_cancelada"}


def process_scheduled_recordatorios() -> dict:
    """
    Cron diario. Para cada Cita Examen Egreso con estado='Pendiente Agendamiento'
    y fecha_limite - today() <= 2 días → envía email recordatorio.

    Best-effort: un fallo individual no aborta el batch.

    Returns:
        dict: {sent: int, failed: int, skipped: int}
    """
    hoy = today()
    if isinstance(hoy, str):
        from frappe.utils import getdate
        hoy = getdate(hoy)

    candidatos = frappe.get_all(
        "Cita Examen Egreso",
        filters={"estado": "Pendiente Agendamiento"},
        fields=["name"],
    )

    sent = 0
    failed = 0
    skipped = 0

    for row in candidatos:
        try:
            cita = frappe.get_doc("Cita Examen Egreso", row.name)
            fecha_limite = cita.fecha_limite
            if isinstance(fecha_limite, str):
                from frappe.utils import getdate
                fecha_limite = getdate(fecha_limite)

            dias_restantes = (fecha_limite - hoy).days
            if dias_restantes > _DIAS_RECORDATORIO:
                skipped += 1
                continue

            emp_email = resolve_employee_email(cita.empleado)
            context = {
                "empleado": cita.empleado,
                "fecha_limite": str(fecha_limite),
                "dias_restantes": dias_restantes,
                "link_agendamiento": f"/app/cita-examen-egreso/{cita.name}?token={cita.token or ''}",
                "cita_name": cita.name,
            }
            result = dispatch_email(
                template_name="terminacion_iniciada_sst_empleado",
                recipients=[emp_email] if emp_email else [],
                context=context,
            )
            if result.get("status") == "ok":
                sent += 1
            else:
                failed += 1
        except Exception as exc:
            failed += 1
            frappe.log_error(
                message=str(exc),
                title=f"process_scheduled_recordatorios: fallo en {row.name}",
            )

    return {"sent": sent, "failed": failed, "skipped": skipped}


def before_insert_examen_egreso(doc, method=None):
    """Hook before_insert: genera token si no está presente."""
    if not doc.token:
        doc.token = frappe.generate_hash(length=24)


# ---------------------------------------------------------------------------
# Helpers privados
# ---------------------------------------------------------------------------

def _dias_habiles(start_date: date, n: int) -> date:
    """
    Calcula la fecha resultante de sumar n días hábiles (Lun-Vie) desde start_date.

    Args:
        start_date: Fecha de inicio.
        n: Número de días hábiles a sumar.

    Returns:
        date: Fecha resultante.
    """
    current = start_date
    dias = 0
    while dias < n:
        current = current + timedelta(days=1)
        # weekday(): 0=Lunes, 4=Viernes, 5=Sábado, 6=Domingo
        if current.weekday() < 5:
            dias += 1
    return current
