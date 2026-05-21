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
DISCIPLINARY_MANAGER_ROLES = {"System Manager", "HR Labor Relations", "GH - RRLL", "Relaciones Laborales Jefe", "Gerente GH"}


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


def _get_jefe_pdvs(user):
	"""
	Retorna la lista de PDVs para los que el user es responsable.
	Capa 1: Punto de Venta.jefe_responsable == user.
	Capa 2: Ficha Empleado del user donde tiene rol Jefe_PDV (vía pdv).
	"""
	# Capa 1: PDVs donde el user está explícitamente como jefe_responsable
	direct = frappe.get_all(
		"Punto de Venta",
		filters={"jefe_responsable": user, "activo": 1},
		pluck="name",
	)
	pdvs = set(direct or [])

	# Capa 2: PDV de la Ficha Empleado del user (por email match)
	own_pdv = _get_employee_by_user(user)
	if own_pdv and own_pdv.get("pdv"):
		pdvs.add(own_pdv.get("pdv"))

	return list(pdvs)


def get_traslado_pdv_permission_query(user=None):
	"""
	Capa 2: permission_query_conditions para 'Traslado PDV'.
	- Administrator / System Manager / GH Admin / HR Labor Relations: sin filtro.
	- Jefe_PDV: filtrado por pdv_origen IN (sus PDVs) OR pdv_destino IN (sus PDVs).
	- Empleado: filtrado por empleado = (su Ficha Empleado).
	- Otros: bloqueado (1=0).
	"""
	user = user or frappe.session.user
	if user == "Administrator":
		return ""

	roles = set(frappe.get_roles(user))

	if "System Manager" in roles:
		return ""

	if roles_have_any(roles, GH_ADMIN_ROLES) or roles_have_any(
		roles, {"HR Labor Relations", "Relaciones Laborales Jefe"}
	):
		return ""

	if roles_have_any(roles, {"Jefe_PDV", "Jefe de tienda", "Jefe de Punto"}):
		pdvs = _get_jefe_pdvs(user)
		if not pdvs:
			return "1=0"
		escaped = ", ".join(frappe.db.escape(p) for p in pdvs)
		return (
			f"(`tabTraslado PDV`.pdv_origen in ({escaped}) "
			f"OR `tabTraslado PDV`.pdv_destino in ({escaped}))"
		)

	if roles_have_any(roles, {"Empleado"}):
		emp = _get_employee_by_user(user)
		if emp and emp.get("name"):
			return f"`tabTraslado PDV`.empleado = {frappe.db.escape(emp.get('name'))}"
		return "1=0"

	return "1=0"


def traslado_pdv_has_permission(doc, user=None, ptype=None):
	"""
	Capa 3: has_permission para 'Traslado PDV'.
	Sigue el mismo patrón de capa 2 pero a nivel de documento individual.
	"""
	user = user or frappe.session.user
	if user == "Administrator":
		return True

	roles = set(frappe.get_roles(user))

	if "System Manager" in roles:
		return True

	if roles_have_any(roles, GH_ADMIN_ROLES) or roles_have_any(
		roles, {"HR Labor Relations", "Relaciones Laborales Jefe"}
	):
		return True

	if roles_have_any(roles, {"Jefe_PDV", "Jefe de tienda", "Jefe de Punto"}):
		pdvs = set(_get_jefe_pdvs(user))
		doc_origen = doc.get("pdv_origen") if hasattr(doc, "get") else getattr(doc, "pdv_origen", None)
		doc_destino = doc.get("pdv_destino") if hasattr(doc, "get") else getattr(doc, "pdv_destino", None)
		return bool(doc_origen in pdvs or doc_destino in pdvs)

	if roles_have_any(roles, {"Empleado"}):
		emp = _get_employee_by_user(user)
		if not emp:
			return False
		doc_emp = doc.get("empleado") if hasattr(doc, "get") else getattr(doc, "empleado", None)
		return doc_emp == emp.get("name")

	return False


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
