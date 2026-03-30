from __future__ import annotations

from datetime import datetime, timezone
from threading import Lock

import frappe

from hubgh.hubgh.people_ops_flags import resolve_operational_person_identity_manual_run_enabled
from hubgh.person_identity import get_operational_person_identity_snapshot
from hubgh.hubgh.role_matrix import canonicalize_roles, roles_have_any
from hubgh.utils import run_manual_person_identity_reconciliation


MANUAL_RECONCILIATION_CONFIRM_TEMPLATE = "MANUAL:{snapshot_id}"
MANUAL_RECONCILIATION_LOCK_KEY = "hubgh:operational_person_identity_tray:manual_reconciliation:active"
MANUAL_RECONCILIATION_LOCK_TTL_SEC = 900
TRAY_VIEW_ROLES = {"System Manager", "Gestión Humana"}
MANUAL_RECONCILIATION_EXECUTE_ROLES = {"System Manager"}
_MANUAL_RECONCILIATION_MUTEX = Lock()


@frappe.whitelist()
def get_tray_context():
	access = _get_tray_access_context()
	return {
		"page_name": "operational_person_identity_tray",
		"can_view": access["can_view"],
		"can_execute": access["can_execute"],
		"manual_run_mode": "enabled" if access["manual_run_enabled"] else "disabled",
		"manual_confirmation_template": MANUAL_RECONCILIATION_CONFIRM_TEMPLATE,
	}


@frappe.whitelist()
def get_snapshot(filters=None):
	_require_tray_view_permission()
	if isinstance(filters, str):
		filters = frappe.parse_json(filters) or {}
	return get_operational_person_identity_snapshot(filters=filters or {})


@frappe.whitelist()
def run_manual_reconciliation(snapshot_id, confirm_text):
	snapshot_id = (snapshot_id or "").strip()
	if not snapshot_id:
		frappe.throw("snapshot_id es obligatorio.")

	operator = _require_manual_reconciliation_permission()
	_expected_confirm_text = MANUAL_RECONCILIATION_CONFIRM_TEMPLATE.format(snapshot_id=snapshot_id)
	if (confirm_text or "").strip() != _expected_confirm_text:
		frappe.throw(f"Confirmacion invalida. Repite exactamente: {_expected_confirm_text}")

	run_state = {
		"snapshot_id": snapshot_id,
		"started_at": datetime.now(timezone.utc).isoformat(),
		"started_by": operator["user"],
		"operator": operator,
	}
	active_run = _claim_active_manual_reconciliation_run(run_state)
	if active_run:
		return {
			"status": "rejected_active_run",
			"lock_key": MANUAL_RECONCILIATION_LOCK_KEY,
			"active_run": active_run,
		}
	try:
		result = run_manual_person_identity_reconciliation(snapshot_id=snapshot_id, operator=operator)
		return {
			"status": result.get("status") or "completed",
			"lock_key": MANUAL_RECONCILIATION_LOCK_KEY,
			"report": result,
			"started_by": operator["user"],
			"started_at": result.get("started_at") or run_state.get("started_at"),
			"finished_at": result.get("finished_at"),
		}
	finally:
		_clear_active_manual_reconciliation_run()


def _require_manual_reconciliation_permission():
	access = _get_tray_access_context()
	if not access["has_execute_permission"]:
		frappe.throw("No autorizado para ejecutar la reconciliacion manual.", getattr(frappe, "PermissionError", None))
		raise PermissionError("No autorizado para ejecutar la reconciliacion manual.")
	if access["can_execute"]:
		return {"user": access["user"], "roles": access["roles"]}
	frappe.throw("La ejecucion manual esta deshabilitada por feature flag server-side.", getattr(frappe, "PermissionError", None))
	raise PermissionError("La ejecucion manual esta deshabilitada por feature flag server-side.")


def _require_tray_view_permission():
	access = _get_tray_access_context()
	if access["can_view"]:
		return access
	frappe.throw("No autorizado para ver la bandeja operativa de identidad persona.", getattr(frappe, "PermissionError", None))
	raise PermissionError("No autorizado para ver la bandeja operativa de identidad persona.")


def _get_tray_access_context() -> dict:
	user = getattr(getattr(frappe, "session", None), "user", None) or "Guest"
	manual_run_enabled = _is_manual_reconciliation_enabled()
	if user == "Administrator":
		return {
			"user": user,
			"roles": ["Administrator"],
			"can_view": True,
			"has_execute_permission": True,
			"manual_run_enabled": manual_run_enabled,
			"can_execute": manual_run_enabled,
		}

	roles = canonicalize_roles(frappe.get_roles(user) or [])
	canonical_roles = sorted(roles)
	has_execute_permission = roles_have_any(canonical_roles, MANUAL_RECONCILIATION_EXECUTE_ROLES)
	return {
		"user": user,
		"roles": canonical_roles,
		"can_view": roles_have_any(canonical_roles, TRAY_VIEW_ROLES),
		"has_execute_permission": has_execute_permission,
		"manual_run_enabled": manual_run_enabled,
		"can_execute": has_execute_permission and manual_run_enabled,
	}


def _is_manual_reconciliation_enabled() -> bool:
	try:
		return resolve_operational_person_identity_manual_run_enabled()
	except Exception:
		return False


def _get_active_manual_reconciliation_run():
	cache = getattr(frappe, "cache", lambda: None)()
	if not cache or not hasattr(cache, "get_value"):
		return None
	return cache.get_value(MANUAL_RECONCILIATION_LOCK_KEY)


def _claim_active_manual_reconciliation_run(run_state: dict):
	with _MANUAL_RECONCILIATION_MUTEX:
		active_run = _get_active_manual_reconciliation_run()
		if active_run:
			return active_run
		_set_active_manual_reconciliation_run(run_state)
		return None


def _set_active_manual_reconciliation_run(run_state: dict) -> None:
	cache = getattr(frappe, "cache", lambda: None)()
	if not cache or not hasattr(cache, "set_value"):
		return
	cache.set_value(
		MANUAL_RECONCILIATION_LOCK_KEY,
		run_state,
		expires_in_sec=MANUAL_RECONCILIATION_LOCK_TTL_SEC,
	)


def _clear_active_manual_reconciliation_run() -> None:
	with _MANUAL_RECONCILIATION_MUTEX:
		cache = getattr(frappe, "cache", lambda: None)()
		if not cache:
			return
		if hasattr(cache, "delete_value"):
			cache.delete_value(MANUAL_RECONCILIATION_LOCK_KEY)
		elif hasattr(cache, "set_value"):
			cache.set_value(MANUAL_RECONCILIATION_LOCK_KEY, None, expires_in_sec=1)
