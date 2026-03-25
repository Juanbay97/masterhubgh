import frappe

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
	created = 0
	empleados = frappe.get_all(
		"Ficha Empleado",
		fields=["name", "email", "nombres", "apellidos"],
	)
	# bypass user creation throttle for bulk import
	frappe.flags.in_import = True
	for emp in empleados:
		email = (emp.get("email") or "").strip()
		if not email:
			continue
		if frappe.db.exists("User", email):
			continue

		if not frappe.utils.validate_email_address(email, throw=False):
			continue

		user = frappe.get_doc(
			{
				"doctype": "User",
				"email": email,
				"first_name": emp.get("nombres") or "Empleado",
				"last_name": emp.get("apellidos") or "",
				"enabled": 1,
				"send_welcome_email": 0,
			}
		)
		user.flags.no_password = False
		user.flags.ignore_password_policy = True
		user.new_password = default_password
		user.insert(ignore_permissions=True)
		user.add_roles("Empleado")
		created += 1

	frappe.flags.in_import = False
	frappe.db.commit()
	return created


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
