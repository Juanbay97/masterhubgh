# Copyright (c) 2026, Antigravity and contributors
# For license information, please see license.txt

"""
user_access_control.py — Bloqueo y restauración de acceso de usuario del empleado.

ADR-1 (ver design §2): Módulo separado para reusar en revocación manual, audit scripts
y potenciales hooks futuros.

## Frappe v15 — Session Kill (OQ-design-3 VERIFICADO)

Lectura de `frappe/core/doctype/user/user.py` línea 299:
    `clear_sessions(user=self.name, force=True)` — llamada canónica en el propio DocType User.

Frappe v15 expone `frappe.sessions.clear_sessions(user, force=True)` como el patrón
canónico. Esta función itera `tabSessions` vía QBuilder (no raw DELETE) y llama
`delete_session()` por cada SID, que maneja activity log y Redis lazy-invalidation.

Por tanto, usamos:
    frappe.db.set_value("User", user, "enabled", 0)
    clear_sessions(user, force=True)

NO se usa `frappe.db.delete("Sessions", {"user": user})` (ADR-4 menciona ese patrón como
alternativa, pero el patrón canónico Frappe v15 es `clear_sessions`).

Riesgo residual (FLAG-4 spec): Redis session cache se invalida lazy en el siguiente
check. Aceptado — documentado en ADR-4 y en este módulo.

Import path: hubgh.hubgh.hubgh.services.user_access_control
"""

from __future__ import annotations

import frappe
from frappe.sessions import clear_sessions
from frappe.utils import now_datetime

from hubgh.person_identity import resolve_user_for_employee
from hubgh.hubgh.people_ops_event_publishers import publish_people_ops_event


# ---------------------------------------------------------------------------
# Públicas
# ---------------------------------------------------------------------------

def block_user_access(
    empleado: str,
    *,
    reason: str,
    source_doctype: str,
    source_name: str,
    override_role_block: bool = False,
) -> dict:
    """
    Bloquea el acceso del empleado al sistema.

    Flujo:
    1. Resuelve identidad → User vinculado al empleado.
    2. Sin User → {"blocked": False, "reason": "no_user_account"}.
    3. User == "Administrator" → throw inmediato.
    4. User tiene rol "System Manager" sin override_role_block → throw.
    5. User.enabled ya es 0 → idempotente: {"blocked": False, "reason": "already_blocked"}.
    6. frappe.db.set_value("User", user, "enabled", 0).
    7. clear_sessions(user, force=True) — canónico Frappe v15.
    8. Publica People Ops Event rrll.acceso.bloqueado.
    9. Retorna {"blocked": True, "user": user, "reason": reason}.

    Args:
        empleado: Nombre de la Ficha Empleado.
        reason: Razón legible del bloqueo (guardada en el evento).
        source_doctype: DocType fuente que origina el bloqueo (ej. "Terminacion Contrato").
        source_name: Name del documento fuente (ej. "TC-2026-001").
        override_role_block: Si True, permite bloquear usuarios con rol System Manager.

    Returns:
        dict con keys: blocked (bool), user (str|None), reason (str).

    Raises:
        frappe.exceptions.ValidationError: Si se intenta bloquear Administrator o
            System Manager sin override.
    """
    identity = resolve_user_for_employee(empleado)
    if not identity or not identity.user:
        return {"blocked": False, "user": None, "reason": "no_user_account"}

    user = identity.user

    # Guard: nunca bloquear Administrator
    if user == "Administrator":
        frappe.throw(
            "BLOCK_ADMINISTRATOR_FORBIDDEN: No se puede bloquear el usuario Administrator.",
            frappe.ValidationError,
        )

    # Guard: System Manager requiere override explícito
    user_roles = set(frappe.get_roles(user) or [])
    if "System Manager" in user_roles and not override_role_block:
        frappe.throw(
            "BLOCK_SYSTEM_MANAGER_REQUIRES_OVERRIDE: El usuario tiene rol System Manager. "
            "Use override_role_block=True para confirmar esta acción.",
            frappe.ValidationError,
        )

    # Idempotencia — si ya está bloqueado, no re-bloquear
    current_enabled = frappe.db.get_value("User", user, "enabled")
    if not current_enabled:
        return {"blocked": False, "user": user, "reason": "already_blocked"}

    # Bloquear: deshabilitar + matar sesiones
    frappe.db.set_value("User", user, "enabled", 0)
    clear_sessions(user, force=True)

    # Publicar evento
    publish_people_ops_event({
        "persona": empleado,
        "area": "rrll",
        "taxonomy": "rrll.acceso.bloqueado",
        "sensitivity": "operational",
        "state": "bloqueado",
        "source_doctype": source_doctype,
        "source_name": source_name,
        "refs": {
            "user": user,
            "reason": reason,
            "override_role_block": override_role_block,
        },
        "occurred_on": now_datetime(),
    })

    return {"blocked": True, "user": user, "reason": reason}


def restore_user_access(
    empleado: str,
    *,
    reason: str,
    source_doctype: str,
    source_name: str,
) -> dict:
    """
    Restaura el acceso del empleado al sistema.

    Inverso de block_user_access. NO restaura sesiones — el empleado debe
    re-autenticarse.

    Flujo:
    1. Resuelve identidad → User.
    2. Sin User → {"restored": False, "reason": "no_user_account"}.
    3. frappe.db.set_value("User", user, "enabled", 1).
    4. Publica People Ops Event rrll.acceso.restaurado.
    5. Retorna {"restored": True, "user": user, "reason": reason}.

    Args:
        empleado: Nombre de la Ficha Empleado.
        reason: Razón legible de la restauración.
        source_doctype: DocType fuente (ej. "Terminacion Contrato").
        source_name: Name del documento fuente.

    Returns:
        dict con keys: restored (bool), user (str|None), reason (str).
    """
    identity = resolve_user_for_employee(empleado)
    if not identity or not identity.user:
        return {"restored": False, "user": None, "reason": "no_user_account"}

    user = identity.user

    # Habilitar
    frappe.db.set_value("User", user, "enabled", 1)

    # Publicar evento
    publish_people_ops_event({
        "persona": empleado,
        "area": "rrll",
        "taxonomy": "rrll.acceso.restaurado",
        "sensitivity": "operational",
        "state": "restaurado",
        "source_doctype": source_doctype,
        "source_name": source_name,
        "refs": {
            "user": user,
            "reason": reason,
        },
        "occurred_on": now_datetime(),
    })

    return {"restored": True, "user": user, "reason": reason}
