import frappe

from hubgh.hubgh.candidate_states import candidate_status_filter_values
from hubgh.person_identity import resolve_employee_for_user
from hubgh.hubgh.document_service import can_user_read_person_document
from hubgh.hubgh.people_ops_policy import (
	DIMENSION_ROLE_MATRIX,
	evaluate_dimension_access,
	get_user_dimension_access as _policy_get_user_dimension_access,
	user_can_access_dimension as _policy_user_can_access_dimension,
)
from hubgh.hubgh.role_matrix import (
	GH_ADMIN_CANONICAL_ROLES,
	OPS_POINT_CANONICAL_ROLES,
	roles_have_any,
	user_has_any_role,
)


GH_ADMIN_ROLES = GH_ADMIN_CANONICAL_ROLES
OPS_POINT_ROLES = OPS_POINT_CANONICAL_ROLES

# REQ-10-04: "Gerente GH" has direct read access to individual docs (design §6)
# but does NOT receive permission_query_conditions access (cannot list/search the DocType).
# DISCIPLINARY_MANAGER_ROLES: used by permission_query_conditions — RRLL roles only.
# DISCIPLINARY_READ_ROLES: used by has_permission for ptype=="read" — includes Gerente GH.
DISCIPLINARY_MANAGER_ROLES = {"System Manager", "HR Labor Relations", "GH - RRLL", "Relaciones Laborales Jefe"}
DISCIPLINARY_READ_ROLES = DISCIPLINARY_MANAGER_ROLES | {"Gerente GH"}


def _user_has_employee_documental_access(user):
	return user in {"Administrator"} or user_has_any_role(user, "System Manager", "Relaciones Laborales Jefe")


def _employee_documental_query():
	admitted_states = ", ".join(
		frappe.db.escape(value)
		for value in candidate_status_filter_values("En afiliación", "Listo para contratar", "Contratado")
	)
	return (
		"(`tabPerson Document`.person_type = 'Empleado' "
		"or exists("
		"select 1 from `tabCandidato` cand "
		"where cand.name = `tabPerson Document`.person "
		f"and cand.estado_proceso in ({admitted_states})"
		"))"
	)


def get_user_dimension_access(user=None):
	return _policy_get_user_dimension_access(user=user)


def user_can_access_dimension(dimension, user=None):
	return _policy_user_can_access_dimension(dimension, user=user)


def evaluate_dimension_permission(dimension, user=None, surface=None, context=None):
	return evaluate_dimension_access(dimension, user=user, surface=surface, context=context)


def get_candidato_permission_query(user=None):
	user = user or frappe.session.user
	if user == "Administrator":
		return ""
	if user_has_any_role(user, "HR Selection") or user_has_any_role(user, "HR Labor Relations", "Relaciones Laborales Jefe"):
		return ""
	return f"`tabCandidato`.user = {frappe.db.escape(user)}"


def candidato_has_permission(doc, user=None):
	user = user or frappe.session.user
	if user == "Administrator":
		return True
	if user_has_any_role(user, "HR Selection") or user_has_any_role(user, "HR Labor Relations", "Relaciones Laborales Jefe"):
		return True
	return doc.user == user


def get_person_document_permission_query(user=None):
	user = user or frappe.session.user
	if user == "Administrator":
		return ""
	if _user_has_employee_documental_access(user):
		return _employee_documental_query()
	if user_has_any_role(user, "HR Labor Relations", "Relaciones Laborales Jefe"):
		return "`tabPerson Document`.person_type = 'Candidato'"

	roles = frappe.get_roles(user)
	roles_escaped = ", ".join(frappe.db.escape(r) for r in roles)
	user_escaped = frappe.db.escape(user)
	roles_clause = roles_escaped or "''"

	return (
		"exists("
		"select 1 from `tabDocument Access` da "
		"where da.parent = `tabPerson Document`.name "
		f"and ((da.user = {user_escaped} and ifnull(da.can_view,0)=1) "
		f"or (da.role in ({roles_clause}) and ifnull(da.can_view,0)=1))"
		")"
	)


def _can_write_employee_document_record(doc, user=None):
	user = user or frappe.session.user
	if user == "Administrator":
		return True
	return user_has_any_role(user, "Relaciones Laborales Jefe")


def person_document_has_permission(doc, user=None, permission_type="read"):
	permission_type = str(permission_type or "read").lower()
	if permission_type in {"write", "create", "delete", "submit", "cancel", "amend"}:
		person_type = str(getattr(doc, "person_type", "") or (doc.get("person_type") if hasattr(doc, "get") else "")).strip()
		if person_type == "Empleado":
			return _can_write_employee_document_record(doc, user=user)
		candidate = getattr(doc, "person", None) or (doc.get("person") if hasattr(doc, "get") else None)
		if person_type == "Candidato" and candidate:
			status = frappe.db.get_value("Candidato", candidate, "estado_proceso")
			if str(status or "").strip() in {"En afiliación", "En Afiliación", "Afiliacion", "En Proceso de Contratación", "Listo para contratar", "Listo para Contratar", "Contratado"}:
				return _can_write_employee_document_record(doc, user=user)
	return can_user_read_person_document(doc, user=user)


def _is_hr(user):
	return (
		user == "Administrator"
		or user_has_any_role(user, "HR Labor Relations")
		or user_has_any_role(user, "Relaciones Laborales Jefe")
		or user_has_any_role(user, "HR Selection")
	)


def get_affiliation_permission_query(user=None):
	user = user or frappe.session.user
	if _is_hr(user):
		return ""
	return "1=0"


def affiliation_has_permission(doc, user=None):
	user = user or frappe.session.user
	return _is_hr(user)


def get_contrato_permission_query(user=None):
	user = user or frappe.session.user
	if _is_hr(user):
		return ""
	return "1=0"


def contrato_has_permission(doc, user=None):
	user = user or frappe.session.user
	return _is_hr(user)


def get_datos_contratacion_permission_query(user=None):
	user = user or frappe.session.user
	if _is_hr(user):
		return ""
	return "1=0"


def datos_contratacion_has_permission(doc, user=None):
	user = user or frappe.session.user
	return _is_hr(user)


def get_gh_novedad_permission_query(user=None):
	user = user or frappe.session.user
	roles = set(frappe.get_roles(user))

	if user == "Administrator" or roles_have_any(roles, GH_ADMIN_ROLES):
		return ""

	if not roles_have_any(roles, OPS_POINT_ROLES):
		return "1=0"

	emp = _get_employee_by_user(user)
	if not emp:
		return "1=0"

	if roles_have_any(roles, {"Empleado"}) and emp.get("name"):
		persona = frappe.db.escape(emp.get("name"))
		return f"`tabGH Novedad`.persona = {persona}"

	pdv = emp.get("pdv")
	if not pdv:
		return "1=0"

	pdv_escaped = frappe.db.escape(pdv)
	return f"`tabGH Novedad`.punto = {pdv_escaped}"


def gh_novedad_has_permission(doc, user=None):
	user = user or frappe.session.user
	roles = set(frappe.get_roles(user))

	if user == "Administrator" or roles_have_any(roles, GH_ADMIN_ROLES):
		return True

	if not roles_have_any(roles, OPS_POINT_ROLES):
		return False

	emp = _get_employee_by_user(user)
	if not emp:
		return False

	if roles_have_any(roles, {"Empleado"}):
		return doc.persona == emp.get("name")

	return bool(emp.get("pdv") and doc.punto == emp.get("pdv"))


def get_caso_disciplinario_permission_query(user=None):
	user = user or frappe.session.user
	if user == "Administrator" or user_has_any_role(user, *DISCIPLINARY_MANAGER_ROLES):
		return ""
	return "1=0"


def caso_disciplinario_has_permission(doc, user=None, ptype="read"):
	user = user or frappe.session.user
	if user == "Administrator":
		return True
	# REQ-10-04: read access includes Gerente GH; write/manage requires RRLL roles only.
	if str(ptype or "read").lower() == "read":
		return user_has_any_role(user, *DISCIPLINARY_READ_ROLES)
	return user_has_any_role(user, *DISCIPLINARY_MANAGER_ROLES)


# ---------------------------------------------------------------------------
# Disciplinary sub-document permissions (T046-T047)
# All follow the same rule: only DISCIPLINARY_MANAGER_ROLES can access.
# ---------------------------------------------------------------------------


def _disciplinary_subdoc_permission_query(user=None):
	"""Shared query for all disciplinary sub-documents."""
	user = user or frappe.session.user
	if user == "Administrator" or user_has_any_role(user, *DISCIPLINARY_MANAGER_ROLES):
		return ""
	return "1=0"


def _disciplinary_subdoc_has_permission(doc, user=None):
	"""Shared has_permission for all disciplinary sub-documents."""
	user = user or frappe.session.user
	if user == "Administrator":
		return True
	return user_has_any_role(user, *DISCIPLINARY_MANAGER_ROLES)


def get_afectado_disciplinario_permission_query(user=None):
	return _disciplinary_subdoc_permission_query(user=user)


def afectado_disciplinario_has_permission(doc, user=None):
	return _disciplinary_subdoc_has_permission(doc, user=user)


def get_citacion_disciplinaria_permission_query(user=None):
	return _disciplinary_subdoc_permission_query(user=user)


def citacion_disciplinaria_has_permission(doc, user=None):
	return _disciplinary_subdoc_has_permission(doc, user=user)


def get_acta_descargos_permission_query(user=None):
	return _disciplinary_subdoc_permission_query(user=user)


def acta_descargos_has_permission(doc, user=None):
	return _disciplinary_subdoc_has_permission(doc, user=user)


def get_comunicado_sancion_permission_query(user=None):
	return _disciplinary_subdoc_permission_query(user=user)


def comunicado_sancion_has_permission(doc, user=None):
	return _disciplinary_subdoc_has_permission(doc, user=user)


def get_evidencia_disciplinaria_permission_query(user=None):
	return _disciplinary_subdoc_permission_query(user=user)


def evidencia_disciplinaria_has_permission(doc, user=None):
	return _disciplinary_subdoc_has_permission(doc, user=user)


def _get_employee_by_user(user):
	identity = resolve_employee_for_user(user)
	if not identity.employee:
		return None
	return frappe.db.get_value("Ficha Empleado", identity.employee, ["name", "pdv"], as_dict=True)
