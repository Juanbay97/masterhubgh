# Copyright (c) 2026, Antigravity and contributors
# For license information, please see license.txt

"""
retiro_legacy_stub — Stubs de retiro para el gap C2→C3.

Reemplaza las llamadas legacy a employee_retirement_service.
NO muta User.enabled, NO crea Payroll Liquidation Case.
Registra intentos en Ficha Empleado + alerta a RRLL vía email.

ADR-1: Módulo separado para borrado trivial en C3 (un rm + grep callsites).
"""

from __future__ import annotations

from typing import Any

import frappe
from frappe.utils import now_datetime

from hubgh.hubgh.services.email_dispatcher import dispatch_email
from hubgh.hubgh.services.notification_resolver import resolve_role_subscribers

STUB_TEMPLATE = "retiro_legacy_stub_alerta"
RRLL_ROLE = "HR Labor Relations"
FALLBACK_CONF_KEY = "retiro_legacy_stub_email_fallback"


def apply_retirement_stub(
    *,
    empleado: str,
    source_doctype: str,
    source_name: str,
    retirement_date: str | None = None,
    reason: str | None = None,
    **kwargs: Any,
) -> dict[str, Any]:
    """
    No-op intencional. Registra intento + alerta RRLL. Pendiente C3.

    1. Verifica que la Ficha Empleado existe.
    2. Setea last_retirement_attempt_at y last_retirement_attempt_source.
    3. Despacha email retiro_legacy_stub_alerta a HR Labor Relations o fallback conf.
    4. Loguea WARN via frappe.log_error.
    5. Retorna {"status": "skipped_gap", "reason": "awaiting_c3"}.

    NO modifica User.enabled, Ficha Empleado.estado ni crea Payroll Liquidation Case.
    """
    if not frappe.db.exists("Ficha Empleado", empleado):
        frappe.log_error(
            message=f"Empleado '{empleado}' no existe en Ficha Empleado. Retiro stub abortado.",
            title=f"Retiro stub: {empleado}",
        )
        return {"status": "skipped_gap", "reason": "empleado_no_encontrado"}

    _set_tracking(empleado, source_doctype, source_name)
    _notify_rrll(
        empleado=empleado,
        source_doctype=source_doctype,
        source_name=source_name,
        retirement_date=retirement_date,
        reason=reason,
        is_reverse=False,
    )
    frappe.log_error(
        message=(
            f"Retiro legacy stub invocado: {source_doctype}:{source_name} → {empleado}. "
            "Pendiente C3."
        ),
        title=f"Retiro stub: {empleado}",
    )
    return {"status": "skipped_gap", "reason": "awaiting_c3"}


def reverse_retirement_if_clear_stub(
    *,
    empleado: str,
    source_doctype: str,
    source_name: str,
    **kwargs: Any,
) -> dict[str, Any]:
    """
    No-op para reversión. Solo log + notificación + tracking.

    Setea last_retirement_attempt_source con prefijo "reverse:" para trazabilidad.
    NO restaura User.enabled ni modifica Ficha Empleado.estado.
    """
    if not frappe.db.exists("Ficha Empleado", empleado):
        frappe.log_error(
            message=f"Empleado '{empleado}' no existe. Reverse retiro stub abortado.",
            title=f"Retiro stub reverse: {empleado}",
        )
        return {"status": "skipped_gap", "reason": "empleado_no_encontrado"}

    _set_tracking(empleado, source_doctype, source_name, is_reverse=True)
    _notify_rrll(
        empleado=empleado,
        source_doctype=source_doctype,
        source_name=source_name,
        retirement_date=None,
        reason=None,
        is_reverse=True,
    )
    frappe.log_error(
        message=(
            f"Reverse retiro stub invocado: {source_doctype}:{source_name} → {empleado}."
        ),
        title=f"Retiro stub reverse: {empleado}",
    )
    return {"status": "skipped_gap", "reason": "awaiting_c3"}


def _get_fallback_emails() -> list[str]:
    """Obtiene emails de fallback desde frappe.conf. Extraído para facilitar mock en tests."""
    return list(frappe.conf.get(FALLBACK_CONF_KEY, []) or [])


def _set_tracking(
    empleado: str,
    source_doctype: str,
    source_name: str,
    *,
    is_reverse: bool = False,
) -> None:
    """Setea los 2 campos de tracking en Ficha Empleado vía frappe.db.set_value."""
    source_value = (
        f"{source_doctype}:reverse:{source_name}"
        if is_reverse
        else f"{source_doctype}:{source_name}"
    )
    frappe.db.set_value(
        "Ficha Empleado",
        empleado,
        {
            "last_retirement_attempt_at": now_datetime(),
            "last_retirement_attempt_source": source_value,
        },
        update_modified=False,
    )


def _notify_rrll(
    empleado: str,
    source_doctype: str,
    source_name: str,
    retirement_date: str | None,
    reason: str | None,
    *,
    is_reverse: bool,
) -> None:
    """Resuelve destinatarios y despacha email retiro_legacy_stub_alerta."""
    recipients = resolve_role_subscribers(RRLL_ROLE)
    if not recipients:
        recipients = _get_fallback_emails()
    if not recipients:
        frappe.log_error(
            message=(
                f"Sin destinatarios para {STUB_TEMPLATE} "
                f"({source_doctype}:{source_name})"
            ),
            title="Retiro stub: destinatarios vacíos",
        )
        return

    try:
        dispatch_email(
            STUB_TEMPLATE,
            recipients,
            {
                "empleado": empleado,
                "empleado_nombre": empleado,
                "source_doctype": source_doctype,
                "source_name": source_name,
                "retirement_date": retirement_date or "",
                "reason": reason or "",
                "is_reverse": is_reverse,
                "action": "reverse" if is_reverse else "retiro",
                "site_url": frappe.utils.get_url(),
            },
        )
    except Exception as exc:
        frappe.log_error(
            message=str(exc),
            title=f"Retiro stub: fallo dispatch email ({source_doctype}:{source_name})",
        )
