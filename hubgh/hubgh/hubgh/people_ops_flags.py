import frappe


SUPPORTED_MODES = {"off", "warn", "enforce"}


def _normalize_mode(value, fallback="warn"):
	mode = str(value or "").strip().lower()
	if mode in SUPPORTED_MODES:
		return mode
	return fallback if fallback in SUPPORTED_MODES else "warn"


def _resolve_mode(default_key, scoped_key=None, scope=None, fallback="warn"):
	config = frappe.get_site_config() or {}
	default_mode = _normalize_mode(config.get(default_key), fallback=fallback)

	if not scoped_key or not scope:
		return default_mode

	scoped_map = config.get(scoped_key) or {}
	if not isinstance(scoped_map, dict):
		return default_mode

	scoped_mode = scoped_map.get(str(scope).strip())
	return _normalize_mode(scoped_mode, fallback=default_mode)


def resolve_backbone_mode(area=None):
	return _resolve_mode(
		default_key="hubgh_people_ops_backbone_mode",
		scoped_key="hubgh_people_ops_backbone_mode_by_area",
		scope=area,
		fallback="warn",
	)


def resolve_policy_mode(surface=None):
	fallback = resolve_backbone_mode()
	return _resolve_mode(
		default_key="hubgh_people_ops_policy_mode",
		scoped_key="hubgh_people_ops_policy_mode_by_surface",
		scope=surface,
		fallback=fallback,
	)


def resolve_payroll_novedades_v1_enabled():
	"""Resolve payroll flag with explicit prod opt-in and safe dev/test fallback."""
	config = frappe.get_site_config() or {}
	if "enable_payroll_novedades_v1" in config:
		return bool(config.get("enable_payroll_novedades_v1"))

	site_name = str(getattr(frappe.local, "site", "") or "").strip().lower()
	if bool(config.get("developer_mode")):
		return True

	return site_name.endswith(".test") or site_name.startswith("test_")


def enable_payroll_novedades_v1():
	"""Enable Payroll Novedades v1 feature flag."""
	frappe.db.set_value("System Settings", None, "enable_payroll_novedades_v1", 1)
	frappe.db.commit()


def disable_payroll_novedades_v1():
	"""Disable Payroll Novedades v1 feature flag."""
	frappe.db.set_value("System Settings", None, "enable_payroll_novedades_v1", 0)
	frappe.db.commit()
