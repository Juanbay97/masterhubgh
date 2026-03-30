from __future__ import annotations

import re
import unicodedata
from datetime import datetime, timezone
from dataclasses import dataclass, field

import frappe
from frappe.utils import validate_email_address


EMPLOYEE_FIELDS = ["name", "cedula", "email", "nombres", "apellidos", "pdv", "estado"]
USER_BASE_FIELDS = ["name", "email", "username", "enabled", "first_name", "last_name", "user_type"]
SNAPSHOT_CATEGORIES = (
	"employees_without_user",
	"users_without_employee",
	"conflicts",
	"pending",
	"fallback_only",
	"already_canonical",
)
SNAPSHOT_CATEGORY_PRECEDENCE = {
	"conflicts": 50,
	"pending": 40,
	"employees_without_user": 30,
	"users_without_employee": 30,
	"fallback_only": 20,
	"already_canonical": 10,
}


@dataclass
class PersonIdentity:
	employee: str | None
	user: str | None
	document: str | None
	email: str | None
	source: str
	conflict: bool = False
	fallback: bool = False
	pending: bool = False
	conflict_reason: str | None = None
	warnings: tuple[str, ...] = field(default_factory=tuple)


@dataclass
class OperationalPersonIdentityRow:
	stable_key: str
	category: str
	employee: str | None
	user: str | None
	document: str | None
	email: str | None
	source: str
	reason: str | None = None
	warnings: tuple[str, ...] = field(default_factory=tuple)
	scan_sources: tuple[str, ...] = field(default_factory=tuple)
	conflict: bool = False
	fallback: bool = False
	pending: bool = False


def normalize_document(value) -> str:
	text = (value or "").strip().upper()
	if not text:
		return ""
	text = unicodedata.normalize("NFKD", text)
	text = text.encode("ascii", "ignore").decode("ascii")
	return re.sub(r"[^A-Z0-9]", "", text)


def resolve_employee_for_user(user) -> PersonIdentity:
	user_row = _coerce_user(user)
	if not user_row:
		return PersonIdentity(None, None, normalize_document(user), _normalize_email(user), "unresolved")

	user_name = user_row.get("name")
	document = normalize_document(user_row.get("username"))
	email = _normalize_email(user_row.get("email") or user_name)
	linked_employee, link_conflict = _get_unique_employee_by_name(user_row.get("employee"))
	document_employee, document_conflict = _get_unique_employee_by_document(document)
	email_employee, email_conflict = _get_unique_employee_by_email(email)

	if link_conflict or document_conflict or email_conflict:
		return _identity_with_conflict(
			employee=linked_employee or document_employee or email_employee,
			user=user_name,
			document=document,
			email=email,
			source="employee_link" if linked_employee else ("username" if document_employee else "email_fallback"),
			reason=link_conflict or document_conflict or email_conflict,
		)

	if linked_employee:
		conflict_reason = _cross_conflict(linked_employee, document_employee, email_employee)
		return _identity(user_name, linked_employee, document, email, "employee_link", conflict_reason)

	if document_employee:
		conflict_reason = _cross_conflict(document_employee, None, email_employee)
		return _identity(user_name, document_employee, document, email, "username", conflict_reason)

	if email_employee:
		return _identity(user_name, email_employee, document, email, "email_fallback", None, fallback=True)

	return PersonIdentity(None, user_name, document or None, email or None, "unresolved")


def resolve_user_for_employee(employee) -> PersonIdentity:
	employee_row = _coerce_employee(employee)
	if not employee_row:
		return PersonIdentity(None, None, normalize_document(employee), None, "unresolved")

	employee_name = employee_row.get("name")
	document = normalize_document(employee_row.get("cedula"))
	email = _normalize_email(employee_row.get("email"))
	linked_user, link_conflict = _get_unique_user_by_employee(employee_name)
	document_user, document_conflict = _get_unique_user_by_document(document)
	email_user, email_conflict = _get_unique_user_by_email(email)

	if link_conflict or document_conflict or email_conflict:
		return _identity_with_conflict(
			employee=employee_name,
			user=linked_user or document_user or email_user,
			document=document,
			email=email,
			source="employee_link" if linked_user else ("username" if document_user else "email_fallback"),
			reason=link_conflict or document_conflict or email_conflict,
		)

	if linked_user:
		conflict_reason = _cross_conflict_user(linked_user, document_user, email_user)
		return _identity(linked_user, employee_name, document, email, "employee_link", conflict_reason)

	if document_user:
		conflict_reason = _cross_conflict_user(document_user, None, email_user)
		return _identity(document_user, employee_name, document, email, "username", conflict_reason)

	if email_user:
		return _identity(email_user, employee_name, document, email, "email_fallback", None, fallback=True)

	return PersonIdentity(employee_name, None, document or None, email or None, "unresolved")


def get_operational_person_identity_snapshot(filters=None) -> dict:
	normalized_filters = _normalize_snapshot_filters(filters)
	base_rows = []
	merged_rows = {}
	employees = _get_operational_employee_rows()
	users, excluded_users = _get_operational_user_rows()

	for employee_row in employees:
		row = _build_employee_snapshot_row(employee_row)
		base_rows.append(row)
		merged_rows[row.stable_key] = _merge_snapshot_rows(merged_rows.get(row.stable_key), row)

	for user_row in users:
		row = _build_user_snapshot_row(user_row)
		base_rows.append(row)
		merged_rows[row.stable_key] = _merge_snapshot_rows(merged_rows.get(row.stable_key), row)

	search_filtered_rows = _apply_snapshot_search(list(merged_rows.values()), normalized_filters)
	kpis = _build_snapshot_kpis(search_filtered_rows)
	rows_by_category = _build_snapshot_rows_by_category(search_filtered_rows, normalized_filters)

	return {
		"generated_at": _snapshot_timestamp(),
		"filters": normalized_filters,
		"kpis": kpis,
		"rows_by_category": rows_by_category,
		"traceability": {
			"employee_rows_scanned": len(employees),
			"user_rows_scanned": len(users),
			"excluded_users": excluded_users,
			"total_rows_before_dedupe": len(base_rows),
			"total_rows_after_dedupe": len(search_filtered_rows),
		},
	}


def reconcile_person_identity(
	*,
	employee=None,
	user=None,
	document: str | None = None,
	email: str | None = None,
	allow_create_user: bool = False,
	user_defaults: dict | None = None,
	user_roles: list[str] | None = None,
	default_password: str | None = None,
) -> PersonIdentity:
	logger = frappe.logger("hubgh.person_identity")
	employee_row = _coerce_employee(employee)
	user_row = _coerce_user(user)
	document = normalize_document(document or (employee_row or {}).get("cedula") or (user_row or {}).get("username"))
	email = _normalize_email(email or (employee_row or {}).get("email") or (user_row or {}).get("email") or (user_row or {}).get("name"))

	resolved_employee = resolve_employee_for_user(user_row) if user_row else None
	resolved_user = resolve_user_for_employee(employee_row) if employee_row else None

	if not employee_row:
		if resolved_employee and resolved_employee.employee:
			employee_row = _coerce_employee(resolved_employee.employee)
		elif document:
			employee_row, employee_conflict = _get_unique_employee_by_document(document)
			if employee_conflict:
				return _identity_with_conflict(None, (user_row or {}).get("name"), document, email, "username", employee_conflict)
		elif email:
			employee_row, employee_conflict = _get_unique_employee_by_email(email)
			if employee_conflict:
				return _identity_with_conflict(None, (user_row or {}).get("name"), document, email, "email_fallback", employee_conflict)

	if not user_row:
		if resolved_user and resolved_user.user:
			user_row = _coerce_user(resolved_user.user)
		elif document:
			user_name, user_conflict = _get_unique_user_by_document(document)
			if user_conflict:
				return _identity_with_conflict((employee_row or {}).get("name"), None, document, email, "username", user_conflict)
			user_row = _coerce_user(user_name)
		elif email:
			user_name, user_conflict = _get_unique_user_by_email(email)
			if user_conflict:
				return _identity_with_conflict((employee_row or {}).get("name"), None, document, email, "email_fallback", user_conflict)
			user_row = _coerce_user(user_name)

	if user_row and employee_row:
		conflict_reason = _writable_conflict(user_row, employee_row, document)
		if conflict_reason:
			identity = _identity_with_conflict(employee_row.get("name"), user_row.get("name"), document, email, "employee_link", conflict_reason)
			logger.warning("reconcile_person_identity:conflict", extra=_identity_log_payload(identity))
			return identity

	if user_row and employee_row:
		updates = {}
		if _user_has_employee_field() and not (user_row.get("employee") or "").strip():
			updates["employee"] = employee_row.get("name")
		if document and normalize_document(user_row.get("username")) != document:
			updates["username"] = document
		if updates:
			frappe.db.set_value("User", user_row.get("name"), updates, update_modified=False)
			user_row = _coerce_user(user_row.get("name"))
		if user_roles:
			_ensure_user_roles(user_row.get("name"), user_roles)
		identity = _identity(user_row.get("name"), employee_row.get("name"), document, email, "employee_link")
		logger.info("reconcile_person_identity:linked", extra=_identity_log_payload(identity))
		return identity

	if user_row:
		identity = resolve_employee_for_user(user_row.get("name"))
		logger.info("reconcile_person_identity:user_only", extra=_identity_log_payload(identity))
		return identity

	if employee_row and allow_create_user:
		if not email or not validate_email_address(email, throw=False):
			identity = PersonIdentity(
				employee_row.get("name"),
				None,
				document or None,
				email or None,
				"unresolved",
				pending=True,
				conflict_reason="invalid_or_missing_email",
				warnings=("missing_valid_email",),
			)
			logger.warning("reconcile_person_identity:pending_missing_valid_email", extra=_identity_log_payload(identity))
			return identity

		payload = {
			"doctype": "User",
			"email": email,
			"username": document or None,
			"first_name": (user_defaults or {}).get("first_name") or employee_row.get("nombres") or document or email,
			"last_name": (user_defaults or {}).get("last_name") or employee_row.get("apellidos") or "",
			"enabled": (user_defaults or {}).get("enabled", 1),
			"send_welcome_email": (user_defaults or {}).get("send_welcome_email", 0),
		}
		if _user_has_employee_field():
			payload["employee"] = employee_row.get("name")
		if (user_defaults or {}).get("user_type"):
			payload["user_type"] = user_defaults["user_type"]
		if user_roles:
			payload["roles"] = [{"role": role} for role in user_roles]
		user_doc = frappe.get_doc(payload)
		if default_password:
			user_doc.flags.no_password = False
			user_doc.flags.ignore_password_policy = True
			user_doc.new_password = default_password
		user_doc.insert(ignore_permissions=True)
		identity = _identity(user_doc.name, employee_row.get("name"), document, email, "employee_link")
		logger.info("reconcile_person_identity:user_created", extra=_identity_log_payload(identity))
		return identity

	if employee_row:
		identity = resolve_user_for_employee(employee_row.get("name"))
		logger.info("reconcile_person_identity:employee_only", extra=_identity_log_payload(identity))
		return identity

	identity = PersonIdentity(None, None, document or None, email or None, "unresolved")
	logger.info("reconcile_person_identity:unresolved", extra=_identity_log_payload(identity))
	return identity


def _normalize_snapshot_filters(filters) -> dict:
	filters = filters or {}
	category = (filters.get("category") or "").strip()
	if category and category not in SNAPSHOT_CATEGORIES:
		category = ""
	search = (filters.get("search") or filters.get("query") or "").strip().lower()
	limit = _coerce_snapshot_int(filters.get("limit"), default=50, minimum=1, maximum=500)
	offset = _coerce_snapshot_int(filters.get("offset"), default=0, minimum=0, maximum=100000)
	return {
		"category": category or None,
		"search": search or None,
		"limit": limit,
		"offset": offset,
	}


def _coerce_snapshot_int(value, *, default: int, minimum: int, maximum: int) -> int:
	try:
		parsed = int(value)
	except (TypeError, ValueError):
		parsed = default
	return max(minimum, min(parsed, maximum))


def _get_operational_employee_rows():
	rows = frappe.get_all("Ficha Empleado", fields=EMPLOYEE_FIELDS)
	return [row for row in rows if _is_operational_employee_row(row)]


def _get_operational_user_rows():
	rows = frappe.get_all("User", fields=_get_user_fields())
	operational = []
	excluded = []
	for row in rows:
		if _is_operational_user_row(row):
			operational.append(row)
			continue
		excluded.append(row.get("name"))
	return operational, excluded


def _is_operational_employee_row(employee_row) -> bool:
	state = (employee_row.get("estado") or "").strip().lower()
	if not state:
		return True
	if state.startswith("inact") or "retir" in state or "desvinc" in state:
		return False
	return True


def _is_operational_user_row(user_row) -> bool:
	user_name = (user_row.get("name") or "").strip()
	if not user_name or user_name in {"Guest", "Administrator"}:
		return False
	if not user_row.get("enabled"):
		return False
	user_type = (user_row.get("user_type") or "").strip()
	if user_type and user_type != "System User":
		return False
	return True


def _build_employee_snapshot_row(employee_row) -> OperationalPersonIdentityRow:
	identity = resolve_user_for_employee(employee_row)
	reason = identity.conflict_reason
	category = "already_canonical"
	document = normalize_document(employee_row.get("cedula")) or identity.document
	email = _normalize_email(employee_row.get("email")) or identity.email
	if identity.conflict:
		category = "conflicts"
	elif identity.pending:
		category = "pending"
	elif not document:
		category = "pending"
		reason = reason or "missing_normalized_document"
	elif not identity.user and not validate_email_address(email, throw=False):
		category = "pending"
		reason = reason or "invalid_or_missing_email"
	elif identity.fallback:
		category = "fallback_only"
		reason = reason or "fallback_match_requires_review"
	elif not identity.user:
		category = "employees_without_user"
		reason = reason or "missing_user_match"
	return _build_snapshot_row(
		identity=identity,
		category=category,
		reason=reason,
		scan_source="employee",
		fallback_document=document,
		fallback_email=email,
	)


def _build_user_snapshot_row(user_row) -> OperationalPersonIdentityRow:
	identity = resolve_employee_for_user(user_row)
	reason = identity.conflict_reason
	category = "already_canonical"
	if identity.conflict:
		category = "conflicts"
	elif identity.pending:
		category = "pending"
	elif identity.fallback:
		category = "fallback_only"
		reason = reason or "fallback_match_requires_review"
	elif not identity.employee:
		category = "users_without_employee"
		reason = reason or "missing_employee_match"
	return _build_snapshot_row(
		identity=identity,
		category=category,
		reason=reason,
		scan_source="user",
		fallback_document=normalize_document(user_row.get("username")) or identity.document,
		fallback_email=_normalize_email(user_row.get("email") or user_row.get("name")) or identity.email,
	)


def _build_snapshot_row(identity, *, category: str, reason: str | None, scan_source: str, fallback_document: str | None, fallback_email: str | None):
	stable_key = _snapshot_merge_key(identity.employee, identity.user, identity.document or fallback_document, identity.email or fallback_email)
	return OperationalPersonIdentityRow(
		stable_key=stable_key,
		category=category,
		employee=identity.employee,
		user=identity.user,
		document=identity.document or fallback_document or None,
		email=identity.email or fallback_email or None,
		source=identity.source,
		reason=reason,
		warnings=tuple(identity.warnings or ()),
		scan_sources=(scan_source,),
		conflict=identity.conflict,
		fallback=identity.fallback,
		pending=identity.pending or category == "pending",
	)


def _snapshot_merge_key(employee: str | None, user: str | None, document: str | None, email: str | None) -> str:
	if employee:
		return f"employee:{employee}"
	if user:
		return f"user:{user}"
	if document:
		return f"document:{document}"
	if email:
		return f"email:{email}"
	return "unknown:missing_identity"


def _merge_snapshot_rows(existing: OperationalPersonIdentityRow | None, incoming: OperationalPersonIdentityRow) -> OperationalPersonIdentityRow:
	if not existing:
		return incoming
	preferred = incoming
	secondary = existing
	if SNAPSHOT_CATEGORY_PRECEDENCE[existing.category] > SNAPSHOT_CATEGORY_PRECEDENCE[incoming.category]:
		preferred = existing
		secondary = incoming
	elif SNAPSHOT_CATEGORY_PRECEDENCE[existing.category] == SNAPSHOT_CATEGORY_PRECEDENCE[incoming.category]:
		if (bool(existing.employee) + bool(existing.user)) >= (bool(incoming.employee) + bool(incoming.user)):
			preferred = existing
			secondary = incoming
	return OperationalPersonIdentityRow(
		stable_key=preferred.stable_key,
		category=preferred.category,
		employee=preferred.employee or secondary.employee,
		user=preferred.user or secondary.user,
		document=preferred.document or secondary.document,
		email=preferred.email or secondary.email,
		source=preferred.source,
		reason=preferred.reason or secondary.reason,
		warnings=tuple(dict.fromkeys((preferred.warnings or ()) + (secondary.warnings or ()))),
		scan_sources=tuple(dict.fromkeys((preferred.scan_sources or ()) + (secondary.scan_sources or ()))),
		conflict=preferred.conflict or secondary.conflict,
		fallback=preferred.fallback or secondary.fallback,
		pending=preferred.pending or secondary.pending,
	)


def _apply_snapshot_search(rows, filters):
	search = filters.get("search")
	if not search:
		return rows
	filtered = []
	for row in rows:
		haystack = " ".join(
			part
			for part in (
				row.employee,
				row.user,
				row.document,
				row.email,
				row.reason,
			)
			if part
		).lower()
		if search in haystack:
			filtered.append(row)
	return filtered


def _build_snapshot_kpis(rows) -> dict:
	counts = {category: 0 for category in SNAPSHOT_CATEGORIES}
	for row in rows:
		counts[row.category] = counts.get(row.category, 0) + 1
	counts["actionable_safe"] = counts["employees_without_user"] + counts["users_without_employee"]
	return counts


def _build_snapshot_rows_by_category(rows, filters) -> dict:
	requested_category = filters.get("category")
	limit = filters["limit"]
	offset = filters["offset"]
	result = {}
	for category in SNAPSHOT_CATEGORIES:
		if requested_category and requested_category != category:
			continue
		category_rows = [row for row in rows if row.category == category]
		page_rows = category_rows[offset: offset + limit]
		result[category] = {
			"total": len(category_rows),
			"offset": offset,
			"limit": limit,
			"has_more": offset + limit < len(category_rows),
			"rows": [_serialize_snapshot_row(row) for row in page_rows],
		}
	return result


def _serialize_snapshot_row(row: OperationalPersonIdentityRow) -> dict:
	return {
		"stable_key": row.stable_key,
		"category": row.category,
		"employee": row.employee,
		"user": row.user,
		"document": row.document,
		"email": row.email,
		"source": row.source,
		"reason": row.reason,
		"warnings": list(row.warnings or ()),
		"scan_sources": list(row.scan_sources or ()),
		"conflict": row.conflict,
		"fallback": row.fallback,
		"pending": row.pending,
	}


def _snapshot_timestamp() -> str:
	return datetime.now(timezone.utc).isoformat()


def _coerce_employee(employee):
	if not employee:
		return None
	if isinstance(employee, dict):
		return frappe._dict(employee)
	if hasattr(employee, "as_dict"):
		return frappe._dict(employee.as_dict())
	if hasattr(employee, "doctype") or hasattr(employee, "name"):
		return frappe._dict({field: getattr(employee, field, None) for field in EMPLOYEE_FIELDS})
	if frappe.db.exists("Ficha Empleado", employee):
		return frappe.db.get_value("Ficha Empleado", employee, EMPLOYEE_FIELDS, as_dict=True)
		
	return None


def _coerce_user(user):
	if not user:
		return None
	if isinstance(user, dict):
		return frappe._dict(user)
	if hasattr(user, "as_dict"):
		return frappe._dict(user.as_dict())
	if hasattr(user, "doctype") or hasattr(user, "name"):
		return frappe._dict({field: getattr(user, field, None) for field in _get_user_fields()})
	if frappe.db.exists("User", user):
		return frappe.db.get_value("User", user, _get_user_fields(), as_dict=True)
	user_name = frappe.db.get_value("User", {"email": user}, "name")
	if user_name:
		return frappe.db.get_value("User", user_name, _get_user_fields(), as_dict=True)
	return None


def _get_unique_employee_by_name(employee_name):
	if not employee_name:
		return None, None
	if not frappe.db.exists("Ficha Empleado", employee_name):
		return None, "missing_employee_link"
	return frappe.db.get_value("Ficha Empleado", employee_name, EMPLOYEE_FIELDS, as_dict=True), None


def _get_unique_employee_by_document(document):
	if not document:
		return None, None
	return _get_unique_normalized_match(
		"Ficha Empleado",
		"cedula",
		document,
		EMPLOYEE_FIELDS,
		duplicate_reason="employee_duplicate_document",
	)


def _get_unique_employee_by_email(email):
	if not email:
		return None, None
	rows = frappe.get_all("Ficha Empleado", filters={"email": email}, fields=EMPLOYEE_FIELDS, limit=2)
	if len(rows) > 1:
		return None, "employee_duplicate_email"
	return (rows[0], None) if rows else (None, None)


def _get_unique_user_by_employee(employee_name):
	if not employee_name:
		return None, None
	if not _user_has_employee_field():
		return None, None
	rows = frappe.get_all("User", filters={"employee": employee_name}, fields=_get_user_fields(), limit=2)
	if len(rows) > 1:
		return None, "user_duplicate_employee_link"
	return (rows[0].get("name"), None) if rows else (None, None)


def _get_unique_user_by_document(document):
	if not document:
		return None, None
	rows, reason = _get_unique_normalized_match(
		"User",
		"username",
		document,
		["name", "username"],
		duplicate_reason="user_duplicate_document",
	)
	if reason:
		return None, reason
	user_names = [rows.get("name")] if rows else []
	legacy_name = _get_unique_user_name_match(document)
	if legacy_name and legacy_name not in user_names:
		user_names.append(legacy_name)
	user_names = list(dict.fromkeys(user_names))
	if len(user_names) > 1:
		return None, "user_duplicate_document"
	return (user_names[0], None) if user_names else (None, None)


def _get_unique_user_by_email(email):
	if not email:
		return None, None
	if frappe.db.exists("User", email):
		return email, None
	rows = frappe.get_all("User", filters={"email": email}, fields=["name"], limit=2)
	user_names = [row.get("name") for row in rows if row.get("name")]
	user_names = list(dict.fromkeys(user_names))
	if len(user_names) > 1:
		return None, "user_duplicate_email"
	return (user_names[0], None) if user_names else (None, None)


def _cross_conflict(primary_employee, document_employee, email_employee):
	primary_name = (primary_employee or {}).get("name")
	if document_employee and document_employee.get("name") != primary_name:
		return "document_vs_employee_link_conflict"
	if email_employee and email_employee.get("name") != primary_name:
		return "document_vs_email_conflict"
	return None


def _cross_conflict_user(primary_user, document_user, email_user):
	if document_user and document_user != primary_user:
		return "document_vs_employee_link_conflict"
	if email_user and email_user != primary_user:
		return "document_vs_email_conflict"
	return None


def _writable_conflict(user_row, employee_row, document):
	if _user_has_employee_field() and (user_row.get("employee") or "").strip() and user_row.get("employee") != employee_row.get("name"):
		return "employee_link_conflict"
	current_username = normalize_document(user_row.get("username"))
	if current_username and document and current_username != document:
		return "username_conflict"
	return None


def _get_user_fields() -> list[str]:
	fields = list(USER_BASE_FIELDS)
	if _user_has_employee_field():
		fields.insert(3, "employee")
	return fields


def _user_has_employee_field() -> bool:
	get_meta = getattr(frappe, "get_meta", None)
	if not callable(get_meta):
		return True
	try:
		meta = get_meta("User")
		get_valid_columns = getattr(meta, "get_valid_columns", None)
		if callable(get_valid_columns):
			return "employee" in set(get_valid_columns() or [])
		fields = getattr(meta, "fields", None) or []
		return any(getattr(field, "fieldname", None) == "employee" for field in fields)
	except Exception:
		return True


def _identity(user_name, employee_row, document, email, source, conflict_reason=None, fallback=False):
	employee_name = employee_row.get("name") if isinstance(employee_row, dict) else employee_row
	warnings = []
	if fallback:
		warnings.append("email_fallback")
	if conflict_reason:
		warnings.append(conflict_reason)
	identity = PersonIdentity(
		employee_name,
		user_name,
		document or None,
		email or None,
		source,
		conflict=bool(conflict_reason),
		fallback=fallback,
		conflict_reason=conflict_reason,
		warnings=tuple(warnings),
	)
	_log_identity_event(identity)
	return identity


def _identity_with_conflict(employee, user, document, email, source, reason):
	identity = PersonIdentity(
		employee.get("name") if isinstance(employee, dict) else employee,
		user.get("name") if isinstance(user, dict) else user,
		document or None,
		email or None,
		source,
		conflict=True,
		conflict_reason=reason,
		warnings=(reason,),
	)
	_log_identity_event(identity)
	return identity


def _get_unique_normalized_match(doctype, fieldname, normalized_value, fields, duplicate_reason):
	rows = frappe.get_all(doctype, filters={fieldname: normalized_value}, fields=fields, limit=2)
	if len(rows) > 1:
		return None, duplicate_reason
	if len(rows) == 1:
		return rows[0], None

	rows = frappe.get_all(doctype, filters=[[fieldname, "!=", ""]], fields=fields)
	matches = [row for row in rows if normalize_document(row.get(fieldname)) == normalized_value]
	if len(matches) > 1:
		return None, duplicate_reason
	return (matches[0], None) if matches else (None, None)


def _get_unique_user_name_match(document):
	if frappe.db.exists("User", document):
		return document

	rows = frappe.get_all("User", filters=[["name", "!=", ""]], fields=["name"])
	matches = [row.get("name") for row in rows if normalize_document(row.get("name")) == document]
	if len(matches) > 1:
		return None
	return matches[0] if matches else None


def _normalize_email(value):
	return (value or "").strip().lower()


def _ensure_user_roles(user_name, user_roles):
	if not user_name or not user_roles:
		return
	user_doc = frappe.get_doc("User", user_name)
	existing = {row.role if hasattr(row, "role") else row.get("role") for row in (user_doc.roles or [])}
	missing = [role for role in user_roles if role not in existing]
	if not missing:
		return
	for role in missing:
		user_doc.append("roles", {"role": role})
	user_doc.save(ignore_permissions=True)


def _identity_log_payload(identity: PersonIdentity):
	return {
		"employee": identity.employee,
		"user": identity.user,
		"document": identity.document,
		"email": identity.email,
		"source": identity.source,
		"conflict": identity.conflict,
		"conflict_reason": identity.conflict_reason,
		"fallback": identity.fallback,
		"pending": identity.pending,
		"warnings": list(identity.warnings or ()),
	}


def _log_identity_event(identity: PersonIdentity):
	logger = frappe.logger("hubgh.person_identity")
	payload = _identity_log_payload(identity)
	if identity.conflict:
		logger.warning("person_identity:conflict", extra=payload)
		return
	if identity.fallback:
		logger.warning("person_identity:email_fallback", extra=payload)
