from datetime import datetime, timezone
from types import SimpleNamespace

import frappe
from frappe.utils import validate_email_address

from hubgh.person_identity import (
	normalize_document,
	reconcile_person_identity,
	resolve_employee_for_user,
	resolve_user_for_employee,
)
from hubgh.hubgh.role_matrix import (
	canonicalize_roles,
	roles_have_any,
)


def get_website_user_home_page(user):
	"""Route users to role-specific app landing pages after login (no shell)."""
	if not user or user == "Guest":
		return "login"

	roles = set(frappe.get_roles(user))
	canonical_roles = canonicalize_roles(roles)

	# Candidate landing goes directly to documents tray.
	if "Candidato" in canonical_roles:
		return "app/mis_documentos_candidato"

	if "System Manager" in canonical_roles:
		return "app/hubgh-admin"

	if roles_have_any(canonical_roles, {"Gestión Humana", "GH - Bandeja General", "GH - SST", "GH - RRLL"}):
		return "app/gestion-humana"

	if roles_have_any(canonical_roles, {"Jefe_PDV"}):
		return "app/mi-punto"

	if roles_have_any(canonical_roles, {"HR Training & Wellbeing", "Formación y Bienestar", "Formacion y Bienestar"}):
		return "app/bienestar"

	if roles_have_any(canonical_roles, {"Empleado", "LMS Student", "Employee"}):
		return "app/mi-perfil"

	# Safe default fallback.
	return "app"


def ensure_candidato_documentos(candidato: str) -> int:
	"""Ensure child rows exist for all active Documento Requerido entries."""
	if not candidato:
		return 0
	logger = frappe.logger("hubgh.candidato")
	candidato_doc = frappe.get_doc("Candidato", candidato)
	required_docs = frappe.get_all(
		"Documento Requerido",
		filters={"activo": 1},
		fields=["name", "requerido"],
	)
	existing_types = {d.tipo_documento for d in (candidato_doc.documentos or []) if d.tipo_documento}
	inserted = 0
	for req in required_docs:
		if req.name in existing_types:
			continue
		candidato_doc.append("documentos", {
			"tipo_documento": req.name,
			"requerido": req.requerido,
			"estado_documento": "Pendiente",
		})
		existing_types.add(req.name)
		inserted += 1
	if inserted:
		candidato_doc.flags.ignore_mandatory = True
		candidato_doc.save(ignore_permissions=True)
	logger.info(
		"ensure_candidato_documentos:done",
		extra={
			"candidato": candidato,
			"required_count": len(required_docs),
			"existing_count": len(existing_types),
			"inserted": inserted,
		},
	)
	return inserted


def create_employee_users(default_password: str = "Empleado123*") -> int:
	report = run_canonical_person_identity_backfill(default_password=default_password, commit=True)
	return report["users_created"]


def run_manual_person_identity_reconciliation(
	*,
	snapshot_id: str,
	operator: dict | None = None,
	default_password: str = "Empleado123*",
) -> dict:
	"""Write-only wrapper for manual tray reconciliation."""
	started_at = _utc_now_iso()
	operator = dict(operator or _get_person_identity_operator_metadata())
	raw_report = run_canonical_person_identity_backfill(default_password=default_password, commit=True)
	finished_at = _utc_now_iso()
	counts = _normalize_manual_backfill_counts(raw_report)
	skipped_rows = _normalize_manual_backfill_skipped_rows(raw_report)
	return {
		"status": "completed",
		"mode": "apply",
		"snapshot_id": snapshot_id,
		"started_at": started_at,
		"finished_at": finished_at,
		"operator": operator,
		"counts": counts,
		"skipped_rows": skipped_rows,
		"traceability": {
			"write_path": "hubgh.utils.run_manual_person_identity_reconciliation",
			"canonical_helper": "hubgh.utils.run_canonical_person_identity_backfill",
			"commit": True,
			"preview_safe": False,
		},
	}


def run_canonical_person_identity_backfill(default_password: str = "Empleado123*", commit: bool = True) -> dict:
	logger = frappe.logger("hubgh.person_identity")
	report = {
		"employees_scanned": 0,
		"users_created": 0,
		"links_completed": 0,
		"already_canonical": 0,
		"conflicts": [],
		"pending": [],
		"fallback_only": [],
	}
	empleados = frappe.get_all(
		"Ficha Empleado",
		fields=["name", "cedula", "email", "nombres", "apellidos"],
	)
	flags = getattr(frappe, "flags", None)
	if flags is None:
		flags = SimpleNamespace()
		frappe.flags = flags
	previous_in_import = getattr(flags, "in_import", False)
	flags.in_import = True
	try:
		for emp in empleados:
			report["employees_scanned"] += 1
			before = resolve_user_for_employee(emp)
			document = normalize_document(emp.get("cedula"))
			email = (emp.get("email") or "").strip().lower() or None

			if before.conflict:
				report["conflicts"].append(_backfill_report_row(emp, before, phase="precheck"))
				continue

			if not document:
				identity = before if before.pending else before.__class__(
					emp.get("name"),
					before.user,
					None,
					email,
					before.source if before.user else "unresolved",
					pending=True,
					conflict_reason="missing_normalized_document",
					warnings=tuple(before.warnings or ()) + ("missing_normalized_document",),
				)
				report["pending"].append(_backfill_report_row(emp, identity, phase="precheck"))
				continue

			if before.fallback:
				reverse_identity = resolve_employee_for_user(before.user)
				if reverse_identity.conflict or reverse_identity.employee != emp.get("name"):
					report["fallback_only"].append(
						_backfill_report_row(
							emp,
							before,
							reason=reverse_identity.conflict_reason or "fallback_not_one_to_one",
							phase="precheck",
						)
					)
					continue

			if not before.user and not validate_email_address(email, throw=False):
				identity = before.__class__(
					emp.get("name"),
					None,
					document,
					email,
					"unresolved",
					pending=True,
					conflict_reason="invalid_or_missing_email",
					warnings=tuple(before.warnings or ()) + ("missing_valid_email",),
				)
				report["pending"].append(_backfill_report_row(emp, identity, phase="precheck"))
				continue

			after = reconcile_person_identity(
				employee=emp,
				document=document,
				email=email,
				allow_create_user=not bool(before.user),
				user_defaults={
					"first_name": emp.get("nombres") or "Empleado",
					"last_name": emp.get("apellidos") or "",
					"enabled": 1,
					"send_welcome_email": 0,
				},
				user_roles=["Empleado"],
				default_password=default_password,
			)

			if after.conflict:
				report["conflicts"].append(_backfill_report_row(emp, after, phase="reconcile"))
				continue
			if after.pending:
				report["pending"].append(_backfill_report_row(emp, after, phase="reconcile"))
				continue
			if after.fallback or not after.user:
				report["fallback_only"].append(_backfill_report_row(emp, after, phase="reconcile"))
				continue

			if not before.user and after.user:
				report["users_created"] += 1
				continue

			if before.user and (
				before.user != after.user or before.source != "employee_link" or before.document != after.document
			):
				report["links_completed"] += 1
				continue

			report["already_canonical"] += 1
	finally:
		flags.in_import = previous_in_import

	if commit:
		frappe.db.commit()
	logger.info("backfill_canonical_person_identity_by_document:done", extra=report)
	return report


def _backfill_report_row(employee_row, identity, reason=None, phase="precheck"):
	return {
		"employee": employee_row.get("name"),
		"user": identity.user,
		"document": identity.document or normalize_document(employee_row.get("cedula")),
		"email": identity.email or (employee_row.get("email") or "").strip().lower() or None,
		"source": identity.source,
		"reason": reason or identity.conflict_reason,
		"phase": phase,
		"warnings": list(identity.warnings or ()),
	}


def _get_person_identity_operator_metadata() -> dict:
	user = getattr(getattr(frappe, "session", None), "user", None) or "Guest"
	roles = canonicalize_roles(frappe.get_roles(user) or []) if user not in {None, "Guest"} else set()
	return {
		"user": user,
		"roles": sorted(roles),
	}


def _normalize_manual_backfill_counts(report: dict) -> dict:
	conflicts = len(report.get("conflicts") or [])
	pending = len(report.get("pending") or [])
	fallback_only = len(report.get("fallback_only") or [])
	return {
		"employees_scanned": int(report.get("employees_scanned") or 0),
		"users_created": int(report.get("users_created") or 0),
		"links_completed": int(report.get("links_completed") or 0),
		"already_canonical": int(report.get("already_canonical") or 0),
		"conflicts": conflicts,
		"pending": pending,
		"fallback_only": fallback_only,
		"skipped_rows": conflicts + pending + fallback_only,
		"mutations_applied": int(report.get("users_created") or 0) + int(report.get("links_completed") or 0),
	}


def _normalize_manual_backfill_skipped_rows(report: dict) -> list[dict]:
	skipped_rows = []
	for category, rows in (
		("conflict", report.get("conflicts") or []),
		("pending", report.get("pending") or []),
		("fallback_only", report.get("fallback_only") or []),
	):
		for row in rows:
			skipped_rows.append({
				"category": category,
				"employee": row.get("employee"),
				"user": row.get("user"),
				"document": row.get("document"),
				"email": row.get("email"),
				"source": row.get("source"),
				"reason": row.get("reason"),
				"phase": row.get("phase"),
				"warnings": list(row.get("warnings") or []),
			})
	return skipped_rows


def _utc_now_iso() -> str:
	return datetime.now(timezone.utc).isoformat()


def backfill_candidato_documentos(candidato: str | None = None) -> int:
	"""Populate documentos child rows for candidatos missing them."""
	logger = frappe.logger("hubgh.candidato")
	logger.info("backfill_candidato_documentos:start", extra={"candidato": candidato})
	required_docs = frappe.get_all(
		"Documento Requerido",
		filters={"activo": 1},
		fields=["name", "requerido"],
	)
	logger.info(
		"backfill_candidato_documentos:required_docs",
		extra={
			"count": len(required_docs),
			"docs": [d.name for d in required_docs],
		},
	)
	updated = 0
	filters = {"name": candidato} if candidato else None
	for row in frappe.get_all("Candidato", filters=filters, fields=["name"]):
		doc = frappe.get_doc("Candidato", row.name)
		logger.info(
			"backfill_candidato_documentos:candidato_state",
			extra={
				"candidato": row.name,
				"existing_documentos": len(doc.documentos or []),
			},
		)
		inserted = ensure_candidato_documentos(row.name)
		if inserted == 0:
			continue
		logger.info(
			"backfill_candidato_documentos:after_save",
			extra={
				"candidato": row.name,
				"saved_documentos": len(frappe.get_doc("Candidato", row.name).documentos or []),
				"inserted": inserted,
			},
		)
		updated += 1
	logger.info("backfill_candidato_documentos:done", extra={"updated": updated})
	return updated
