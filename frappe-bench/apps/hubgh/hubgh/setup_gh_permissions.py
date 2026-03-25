import frappe

from hubgh.hubgh.role_matrix import get_transitional_roles


BASE_GH_ROLES = ["Gestión Humana"]
TRIAGE_GH_ROLES = ["GH - Bandeja General", "GH - SST", "GH - RRLL"]
JEFE_ROLES = ["Jefe_PDV"]
EMPLOYEE_ROLES = ["Empleado"]
CALIDAD_ROLE = "Calidad"


def setup_permissions():
	# 1) Base roles used by historical setup and this RBAC extension.
	for role_name, desk_access in (
		("Gestión Humana", 1),
		("HR Selection", 1),
		("HR Labor Relations", 1),
		("HR SST", 1),
		("HR Training & Wellbeing", 1),
		("Jefe_PDV", 1),
		("Candidato", 0),
	):
		ensure_role(role_name, desk_access=desk_access)

	# 2) Existing page permissions for GH role (backward-compatible behavior).
	for page_name in [
		"punto_360",
		"persona_360",
		"bandeja_afiliaciones",
		"bandeja_contratacion",
		"carpeta_documental_empleado",
	]:
		ensure_page_roles(page_name, get_transitional_roles(["Gestión Humana"]))

	# 3) New page permissions required by demo modules.
	ensure_page_roles(
		"mi_perfil",
		get_transitional_roles(unique_roles(EMPLOYEE_ROLES + JEFE_ROLES + BASE_GH_ROLES + TRIAGE_GH_ROLES)),
	)
	ensure_page_roles(
		"operacion_punto_lite",
		get_transitional_roles(unique_roles(JEFE_ROLES + BASE_GH_ROLES + TRIAGE_GH_ROLES)),
	)

	# 4) Existing DocType grants (preserved).
	read_only_doctypes = [
		"Ficha Empleado",
		"Punto de Venta",
		"Caso Disciplinario",
		"Caso SST",
		"Feedback Punto",
		"Banco Siesa",
		"Entidad EPS Siesa",
		"Entidad AFP Siesa",
		"Entidad Cesantias Siesa",
		"Entidad CCF Siesa",
		"Tipo Cotizante Siesa",
		"Unidad Negocio Siesa",
		"Centro Costos Siesa",
		"Centro Trabajo Siesa",
		"Grupo Empleados Siesa",
	]
	for dt in read_only_doctypes:
		for role in get_transitional_roles(["Gestión Humana"]):
			ensure_docperm(
				dt,
				role,
				read=1,
				select=1,
				report=1,
			)

	for dt in ["Afiliacion Seguridad Social", "Contrato"]:
		for role in get_transitional_roles(["Gestión Humana"]):
			ensure_docperm(
				dt,
				role,
				read=1,
				write=1,
				create=1,
				delete=1,
				report=1,
				export=1,
				print=1,
				submit=1,
			)

	# Existing Novedad SST full access for Gestión Humana.
	for role in get_transitional_roles(["Gestión Humana"]):
		ensure_docperm(
			"Novedad SST",
			role,
			read=1,
			write=1,
			create=1,
			delete=1,
			report=1,
		)

	# 5) New DocType RBAC grants.
	setup_demo_doctype_permissions()

	frappe.db.commit()


def unique_roles(roles):
	return list(dict.fromkeys(roles))


def ensure_role(role_name, desk_access=1):
	if frappe.db.exists("Role", role_name):
		return
	frappe.get_doc(
		{
			"doctype": "Role",
			"role_name": role_name,
			"desk_access": desk_access,
			"read_only": 0,
		}
	).insert(ignore_permissions=True)
	print(f"Created Role: {role_name}")


def ensure_page_roles(page_name, roles):
	if not frappe.db.exists("Page", page_name):
		print(f"Skipped Page (not found): {page_name}")
		return

	page = frappe.get_doc("Page", page_name)
	existing_roles = {r.role for r in page.roles}
	changed = False

	for role in roles:
		if not frappe.db.exists("Role", role):
			continue
		if role not in existing_roles:
			page.append("roles", {"role": role})
			changed = True

	if changed:
		page.save(ignore_permissions=True)
		print(f"Updated Page roles: {page_name}")


def ensure_docperm(doctype, role, permlevel=0, **flags):
	if not frappe.db.exists("DocType", doctype):
		print(f"Skipped DocType (not found): {doctype}")
		return
	if not frappe.db.exists("Role", role):
		print(f"Skipped Role (not found): {role} for DocType {doctype}")
		return

	doc = frappe.get_doc("DocType", doctype)
	perm_row = None
	for row in doc.permissions:
		if row.role == role and cint_or_zero(row.permlevel) == cint_or_zero(permlevel):
			perm_row = row
			break

	if not perm_row:
		perm_row = doc.append("permissions", {"role": role, "permlevel": permlevel})

	changed = False
	for key, value in flags.items():
		if hasattr(perm_row, key) and cint_or_zero(getattr(perm_row, key)) != cint_or_zero(value):
			setattr(perm_row, key, value)
			changed = True

	if changed or doc.is_new() or not perm_row.name:
		doc.save(ignore_permissions=True)


def cint_or_zero(value):
	try:
		return int(value or 0)
	except Exception:
		return 0


def setup_demo_doctype_permissions():
	gh_manage_roles = unique_roles(BASE_GH_ROLES + TRIAGE_GH_ROLES)
	read_roles = unique_roles(EMPLOYEE_ROLES + JEFE_ROLES + gh_manage_roles)
	gh_manage_roles_transitional = get_transitional_roles(gh_manage_roles)
	read_roles_transitional = get_transitional_roles(read_roles)
	ops_read_roles_transitional = get_transitional_roles(unique_roles(EMPLOYEE_ROLES + JEFE_ROLES))

	# GH Post / GH Policy: broad read, GH manage.
	for doctype in ("GH Post", "GH Policy"):
		for role in read_roles_transitional:
			ensure_docperm(doctype, role, read=1, select=1, report=1, export=1, print=1)
		for role in gh_manage_roles_transitional:
			ensure_docperm(
				doctype,
				role,
				read=1,
				write=1,
				create=1,
				delete=1,
				report=1,
				export=1,
				print=1,
			)

	# Optional quality reporting role (only if role exists).
	if frappe.db.exists("Role", CALIDAD_ROLE):
		for doctype in ("GH Post", "GH Policy"):
			ensure_docperm(doctype, CALIDAD_ROLE, read=1, select=1, report=1, export=1, print=1)

	# GH Novedad: operation create/read, GH management.
	for role in ops_read_roles_transitional:
		ensure_docperm("GH Novedad", role, read=1, create=1, select=1, report=1)
	for role in gh_manage_roles_transitional:
		ensure_docperm(
			"GH Novedad",
			role,
			read=1,
			write=1,
			create=1,
			delete=1,
			report=1,
			export=1,
			print=1,
		)

	# Operacion Tipo Documento: GH manage, operation read.
	for role in get_transitional_roles(gh_manage_roles + ["System Manager"]):
		ensure_docperm(
			"Operacion Tipo Documento",
			role,
			read=1,
			write=1,
			create=1,
			delete=1,
			report=1,
		)
	for role in ops_read_roles_transitional:
		ensure_docperm("Operacion Tipo Documento", role, read=1, select=1, report=1)


if __name__ == "__main__":
	setup_permissions()
