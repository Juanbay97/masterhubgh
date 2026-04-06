import frappe

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
DISCIPLINARY_MANAGER_ROLES = {"System Manager", "HR Labor Relations", "GH - RRLL", "Gerente GH"}


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
	if user_has_any_role(user, "HR Selection") or user_has_any_role(user, "HR Labor Relations"):
		return ""
	return f"`tabCandidato`.user = {frappe.db.escape(user)}"


def candidato_has_permission(doc, user=None):
	user = user or frappe.session.user
	if user == "Administrator":
		return True
	if user_has_any_role(user, "HR Selection") or user_has_any_role(user, "HR Labor Relations"):
		return True
	return doc.user == user


def get_person_document_permission_query(user=None):
	user = user or frappe.session.user
	if user == "Administrator":
		return ""
	if user_has_any_role(user, "HR Labor Relations"):
		return ""

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


def person_document_has_permission(doc, user=None):
	return can_user_read_person_document(doc, user=user)


def _is_hr(user):
	return (
		user == "Administrator"
		or user_has_any_role(user, "HR Labor Relations")
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


def caso_disciplinario_has_permission(doc, user=None):
	user = user or frappe.session.user
	if user == "Administrator":
		return True
	return user_has_any_role(user, *DISCIPLINARY_MANAGER_ROLES)


def _get_employee_by_user(user):
	identity = resolve_employee_for_user(user)
	if not identity.employee:
		return None
	return frappe.db.get_value("Ficha Empleado", identity.employee, ["name", "pdv"], as_dict=True)
