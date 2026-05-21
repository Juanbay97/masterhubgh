# Copyright (c) 2026, Antigravity and contributors
# For license information, please see license.txt

"""
traslado_service.py — Servicio core de Traslado de Empleado entre PDVs.

Arquitectura: Service-oriented (Design §0).
- Todas las mutaciones de Traslado PDV pasan por aquí.
- Los DocType controllers son anémicos (before_insert snapshot, on_update event).
- La bandeja llama a este módulo vía thin controllers (5 líneas por método).

Import path: hubgh.hubgh.services.traslado_service
"""

from __future__ import annotations

import json
import frappe
from frappe.utils import today, now_datetime, getdate

from hubgh.hubgh.services.notification_resolver import (
    resolve_jefe_pdv,
    resolve_employee_email,
)
from hubgh.hubgh.services.email_dispatcher import dispatch_email
from hubgh.hubgh.people_ops_event_publishers import publish_people_ops_event
from hubgh.user_groups import sync_all_user_groups


# ---------------------------------------------------------------------------
# Roles autorizados para gestión
# ---------------------------------------------------------------------------

ALLOWED_MANAGE_ROLES = {
    "System Manager",
    "Gestión Humana",
    "HR Labor Relations",
    "GH - RRLL",
    "Gerente GH",
}

# ---------------------------------------------------------------------------
# Hook handlers (registrados en hooks.py)
# ---------------------------------------------------------------------------

def before_insert_traslado(doc, method=None):
    """
    Hook before_insert del DocType Traslado PDV.

    Responsabilidades:
    1. Snapshot pdv_origen desde empleado.pdv (siempre sobreescribe).
    2. Snapshot cargo_origen desde empleado.cargo.
    3. Set solicitado_por = frappe.session.user.
    4. Validaciones de negocio.
    """
    emp = _get_empleado_or_throw(doc.empleado)

    # 1. Snapshot pdv_origen — siempre sobreescribe desde la fuente canónica
    doc.pdv_origen = emp.pdv

    # 2. Snapshot cargo_origen si el campo existe en el doc (futuro uso)
    # (el campo cargo_origen no está en el schema actual, se guarda si existe)
    if hasattr(doc, "cargo_origen") and emp.cargo:
        doc.cargo_origen = emp.cargo

    # 3. Solicitado_por
    doc.solicitado_por = frappe.session.user or "Administrator"

    # 4. Validaciones
    _validate_before_insert(doc, emp)


def on_update_traslado(doc, method=None):
    """
    Hook on_update del DocType Traslado PDV.

    Solo publica People Ops Event cuando el estado cambia.
    """
    before = getattr(doc, "_doc_before_save", None)
    estado_antes = getattr(before, "estado", None) if before else None
    estado_actual = doc.estado

    if estado_antes == estado_actual:
        return  # sin cambio, no publicar

    taxonomy = f"operacion.traslado_pdv.{estado_actual.lower()}"
    publish_people_ops_event({
        "persona": doc.empleado,
        "area": "operacion",
        "taxonomy": taxonomy,
        "sensitivity": "operational",
        "state": estado_actual,
        "source_doctype": "Traslado PDV",
        "source_name": doc.name,
        "refs": {
            "pdv_origen": doc.get("pdv_origen"),
            "pdv_destino": doc.get("pdv_destino"),
            "motivo": doc.get("motivo"),
            "cargo_destino": doc.get("cargo_destino"),
        },
        "occurred_on": now_datetime(),
    })


# ---------------------------------------------------------------------------
# create_traslado
# ---------------------------------------------------------------------------

def create_traslado(
    empleado: str,
    pdv_destino: str,
    fecha_aplicacion: str,
    motivo: str,
    justificacion: str,
    cargo_destino: str | None = None,
) -> str:
    """
    Crea un Traslado PDV en estado 'Programado' y dispara T1+T2+T3.

    Returns: nombre del doc creado.
    Raises: frappe.ValidationError con token de error en el mensaje.
    """
    # --- Validaciones previas al insert ---
    emp = _get_empleado_or_throw(empleado)

    if emp.estado != "Activo":
        frappe.throw(
            "EMPLEADO_NO_ACTIVO: No se puede crear traslado para un empleado que no está Activo.",
            frappe.ValidationError,
        )

    if not frappe.db.exists("Punto de Venta", pdv_destino):
        frappe.throw(
            f"PDV_DESTINO_INVALIDO: El PDV destino '{pdv_destino}' no existe.",
            frappe.ValidationError,
        )

    if emp.pdv == pdv_destino:
        frappe.throw(
            "PDV_DESTINO_IGUAL_ORIGEN: El PDV destino debe ser distinto al PDV origen.",
            frappe.ValidationError,
        )

    if not justificacion or len(str(justificacion).strip()) < 20:
        frappe.throw(
            "JUSTIFICACION_CORTA: La justificación debe tener al menos 20 caracteres.",
            frappe.ValidationError,
        )

    # Validar que no exista otro Programado para el mismo empleado
    duplicado = frappe.db.exists(
        "Traslado PDV",
        {"empleado": empleado, "estado": "Programado"},
    )
    if duplicado:
        frappe.throw(
            "TRASLADO_DUPLICADO: El empleado ya tiene un traslado Programado pendiente.",
            frappe.ValidationError,
        )

    # Validar motivo
    motivo_doc = _get_motivo_or_throw(motivo)

    # Validar cargo_destino si motivo lo requiere
    if motivo_doc.requiere_cambio_cargo and not cargo_destino:
        frappe.throw(
            "CARGO_DESTINO_REQUERIDO: Este motivo requiere especificar el cargo destino.",
            frappe.ValidationError,
        )

    # --- Crear el doc (before_insert hará snapshot y re-validará) ---
    nuevo = frappe.get_doc({
        "doctype": "Traslado PDV",
        "empleado": empleado,
        "pdv_destino": pdv_destino,
        "fecha_aplicacion": fecha_aplicacion,
        "motivo": motivo,
        "justificacion": justificacion,
        "cargo_destino": cargo_destino,
        "estado": "Programado",
    })
    nuevo.insert(ignore_permissions=True)

    # --- Notificaciones T1+T2+T3 ---
    notif_results = _dispatch_notifications(nuevo, fase="programado")

    # Persistir payload
    nuevo.db_set(
        "payload_notificaciones",
        json.dumps(notif_results, ensure_ascii=False, default=str),
        update_modified=False,
    )

    return nuevo.name


# ---------------------------------------------------------------------------
# apply_traslado
# ---------------------------------------------------------------------------

def apply_traslado(traslado_name: str) -> dict:
    """
    Aplica un traslado: muta Ficha Empleado.pdv (+ cargo si aplica),
    re-sincroniza user_groups, marca Aplicado, dispara T4, publica event.

    Idempotente: si estado != 'Programado' → retorna {"status":"skipped","reason":"<estado>"}.
    Returns: {"status":"applied"|"skipped", "name":str, "reason":str|None}
    """
    doc = frappe.get_doc("Traslado PDV", traslado_name)

    if doc.estado != "Programado":
        return {"status": "skipped", "name": traslado_name, "reason": doc.estado}

    # Validar que fecha_aplicacion <= hoy
    if getdate(doc.fecha_aplicacion) > getdate(today()):
        frappe.throw(
            "FECHA_NO_ALCANZADA: El traslado no puede aplicarse antes de su fecha programada.",
            frappe.ValidationError,
        )

    # Savepoint para atomicidad
    frappe.db.savepoint("apply_traslado")
    try:
        # Mutar Ficha Empleado.pdv
        frappe.db.set_value("Ficha Empleado", doc.empleado, "pdv", doc.pdv_destino)

        # Mutar cargo si aplica (Ficha Empleado.cargo es Data → asignar name del Cargo)
        if doc.get("cargo_destino"):
            frappe.db.set_value("Ficha Empleado", doc.empleado, "cargo", doc.cargo_destino)

        # Marcar Aplicado
        aplicado_por = frappe.session.user or "Administrator"
        doc.estado = "Aplicado"
        doc.aplicado_en = now_datetime()
        doc.aplicado_por = aplicado_por
        doc.save(ignore_permissions=True)

        # Sincronizar user groups
        sync_all_user_groups()

        # Notificación T4
        notif_results = _dispatch_notifications(doc, fase="aplicado")
        # El People Ops Event se publica vía on_update_traslado hook (fires en doc.save)

    except frappe.ValidationError:
        frappe.db.rollback(save_point="apply_traslado")
        raise
    except Exception:
        frappe.db.rollback(save_point="apply_traslado")
        raise

    return {"status": "applied", "name": traslado_name, "reason": None}


# ---------------------------------------------------------------------------
# cancel_traslado
# ---------------------------------------------------------------------------

def cancel_traslado(traslado_name: str, motivo: str) -> dict:
    """
    Anula un traslado Programado.

    - Idempotente: si ya está Anulado → retorna {"status":"skipped"}.
    - Si está Aplicado → throw TRASLADO_APLICADO_NO_CANCELABLE.
    - Requiere motivo no vacío.
    Returns: {"status":"cancelled"|"skipped", "name":str, "reason":str|None}
    """
    if not motivo or not str(motivo).strip():
        frappe.throw(
            "MOTIVO_ANULACION_REQUERIDO: La justificación de anulación es obligatoria.",
            frappe.ValidationError,
        )

    doc = frappe.get_doc("Traslado PDV", traslado_name)

    if doc.estado == "Anulado":
        return {"status": "skipped", "name": traslado_name, "reason": "already_anulado"}

    if doc.estado == "Aplicado":
        frappe.throw(
            "TRASLADO_APLICADO_NO_CANCELABLE: Un traslado ya aplicado no puede anularse.",
            frappe.ValidationError,
        )

    doc.estado = "Anulado"
    doc.anulado_en = now_datetime()
    doc.anulado_por = frappe.session.user or "Administrator"
    doc.motivo_anulacion = motivo
    doc.save(ignore_permissions=True)
    # El People Ops Event se publica vía on_update_traslado hook (fires en doc.save)

    return {"status": "cancelled", "name": traslado_name, "reason": None}


# ---------------------------------------------------------------------------
# process_scheduled_traslados — cron entry
# ---------------------------------------------------------------------------

def process_scheduled_traslados() -> dict:
    """
    Cron diario. Itera Traslado PDV con estado='Programado' y fecha_aplicacion <= today().
    Best-effort: un fallo individual no aborta el batch.

    Returns: {"processed": N, "failed": M, "skipped": K, "errors": [...]}
    """
    logger = frappe.logger("hubgh.traslado")

    candidatos = frappe.get_all(
        "Traslado PDV",
        filters={
            "estado": "Programado",
            "fecha_aplicacion": ["<=", today()],
        },
        pluck="name",
    )

    processed = 0
    failed = 0
    skipped = 0
    errors = []

    for name in candidatos:
        try:
            result = apply_traslado(name)
            if result["status"] == "applied":
                processed += 1
                logger.info(
                    "traslado_applied",
                    extra={"traslado": name, "status": "applied"},
                )
            else:
                skipped += 1
                logger.info(
                    "traslado_skipped",
                    extra={"traslado": name, "reason": result.get("reason")},
                )
        except Exception as exc:
            failed += 1
            error_msg = str(exc)
            errors.append({"traslado": name, "error": error_msg})
            frappe.log_error(
                message=error_msg,
                title=f"process_scheduled_traslados: fallo en {name}",
            )
            logger.error(
                "traslado_failed",
                extra={"traslado": name, "error": error_msg},
            )

    return {
        "processed": processed,
        "failed": failed,
        "skipped": skipped,
        "errors": errors,
    }


# ---------------------------------------------------------------------------
# get_flow_context — para bandeja JS y permisos de UI
# ---------------------------------------------------------------------------

def get_flow_context(user: str) -> dict:
    """
    Retorna contexto del flujo para el usuario dado.
    Usado por la bandeja y controladores thin.
    """
    if not user:
        return {"user": user, "can_manage": False}

    if user == "Administrator":
        return {"user": user, "can_manage": True}

    user_roles = set(frappe.get_roles(user) or [])
    can_manage = bool(user_roles & ALLOWED_MANAGE_ROLES)
    return {"user": user, "can_manage": can_manage}


# ---------------------------------------------------------------------------
# get_tray — lista paginable para la bandeja
# ---------------------------------------------------------------------------

def get_tray(filters: dict | None = None) -> list:
    """
    Retorna lista de Traslado PDV para la bandeja.
    Los filtros de capa 2 (permission_query_conditions) se aplican automáticamente.
    """
    filters = filters or {}
    return frappe.get_all(
        "Traslado PDV",
        filters=filters,
        fields=[
            "name", "empleado", "empleado_nombre",
            "pdv_origen", "pdv_destino",
            "fecha_aplicacion", "estado", "motivo",
            "solicitado_por", "aplicado_en", "modified",
        ],
        order_by="fecha_aplicacion desc",
        limit=100,
    )


# ---------------------------------------------------------------------------
# Helpers privados
# ---------------------------------------------------------------------------

def _get_empleado_or_throw(empleado: str):
    """Obtiene Ficha Empleado o lanza si no existe."""
    emp = frappe.db.get_value(
        "Ficha Empleado",
        empleado,
        ["name", "pdv", "cargo", "estado", "email"],
        as_dict=True,
    )
    if not emp:
        frappe.throw(
            f"EMPLEADO_NO_ENCONTRADO: No se encontró la Ficha Empleado '{empleado}'.",
            frappe.ValidationError,
        )
    return emp


def _get_motivo_or_throw(motivo: str):
    """Obtiene Motivo Traslado activo o lanza MOTIVO_INVALIDO."""
    m = frappe.db.get_value(
        "Motivo Traslado",
        motivo,
        ["name", "requiere_cambio_cargo", "activo"],
        as_dict=True,
    )
    if not m or not m.activo:
        frappe.throw(
            f"MOTIVO_INVALIDO: El motivo '{motivo}' no existe o no está activo.",
            frappe.ValidationError,
        )
    return m


def _validate_before_insert(doc, emp):
    """
    Validaciones de negocio llamadas desde before_insert.
    Separadas para poder testear hook y service por separado.
    """
    if emp.estado != "Activo":
        frappe.throw(
            "EMPLEADO_NO_ACTIVO: No se puede crear traslado para un empleado que no está Activo.",
            frappe.ValidationError,
        )

    if doc.pdv_destino == doc.pdv_origen:
        frappe.throw(
            "PDV_DESTINO_IGUAL_ORIGEN: El PDV destino debe ser distinto al PDV origen.",
            frappe.ValidationError,
        )

    if not doc.justificacion or len(str(doc.justificacion).strip()) < 20:
        frappe.throw(
            "JUSTIFICACION_CORTA: La justificación debe tener al menos 20 caracteres.",
            frappe.ValidationError,
        )

    duplicado = frappe.db.exists(
        "Traslado PDV",
        {"empleado": doc.empleado, "estado": "Programado"},
    )
    if duplicado:
        frappe.throw(
            "TRASLADO_DUPLICADO: El empleado ya tiene un traslado Programado pendiente.",
            frappe.ValidationError,
        )


def _dispatch_notifications(doc, fase: str) -> list[dict]:
    """
    Despacha notificaciones email según la fase del traslado.

    fase='programado' → T1 (empleado), T2 (jefe origen), T3 (jefe destino)
    fase='aplicado'   → T4 (empleado + ambos jefes)

    Cada envío fallido o sin destinatario se registra pero NO aborta.
    Returns: lista de resultados de dispatch_email.
    """
    results = []

    # Resolver destinatarios
    emp_email = resolve_employee_email(doc.empleado)
    jefe_origen = resolve_jefe_pdv(doc.get("pdv_origen"))
    jefe_destino = resolve_jefe_pdv(doc.get("pdv_destino"))

    emp_doc = frappe.db.get_value(
        "Ficha Empleado",
        doc.empleado,
        ["nombres", "apellidos", "cedula", "email"],
        as_dict=True,
    ) or {}

    # Resolver label legible del motivo (SUGGESTION-1)
    motivo_code = doc.get("motivo")
    motivo_label = (
        frappe.db.get_value("Motivo Traslado", motivo_code, "label")
        if motivo_code
        else None
    )
    # Fallback al código si no hay registro en Motivo Traslado
    motivo_label = motivo_label or motivo_code

    context = {
        "traslado": {
            "name": doc.name,
            "empleado": doc.empleado,
            "empleado_nombre": doc.get("empleado_nombre") or emp_doc.get("nombres", ""),
            "pdv_origen": doc.get("pdv_origen"),
            "pdv_destino": doc.get("pdv_destino"),
            "fecha_aplicacion": str(doc.get("fecha_aplicacion") or ""),
            "motivo": motivo_code,
            "motivo_label": motivo_label,
            "justificacion": doc.get("justificacion"),
            "cargo_destino": doc.get("cargo_destino"),
        },
        "empleado": emp_doc,
        "jefe_origen": {"user": jefe_origen} if jefe_origen else None,
        "jefe_destino": {"user": jefe_destino} if jefe_destino else None,
    }

    if fase == "programado":
        # T1 al empleado
        results.append(dispatch_email(
            template_name="traslado_pdv_empleado_programado",
            recipients=[emp_email] if emp_email else [],
            context=context,
        ))
        # T2 al jefe origen
        results.append(dispatch_email(
            template_name="traslado_pdv_jefe_origen_programado",
            recipients=[jefe_origen] if jefe_origen else [],
            context=context,
        ))
        # T3 al jefe destino
        results.append(dispatch_email(
            template_name="traslado_pdv_jefe_destino_programado",
            recipients=[jefe_destino] if jefe_destino else [],
            context=context,
        ))

    elif fase == "aplicado":
        # T4 a empleado + ambos jefes (dispatcher dedupe por recipients únicos)
        all_recipients = list({
            r for r in [emp_email, jefe_origen, jefe_destino] if r
        })
        context["aplicado_por"] = doc.get("aplicado_por") or "Administrator"
        results.append(dispatch_email(
            template_name="traslado_pdv_aplicado_confirmacion",
            recipients=all_recipients,
            context=context,
        ))

    return results
