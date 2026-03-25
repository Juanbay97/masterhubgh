import frappe
from frappe import _
import unicodedata


EMPLOYEE_DOCTYPE_CANDIDATES = ("Ficha Empleado", "Employee")
EMPLOYEE_DOCTYPE_FALLBACK = "Ficha Empleado"
TIPO_JORNADA_FULL_TIME = "Tiempo Completo"
TIPO_JORNADA_PART_TIME = "Tiempo Parcial"


def normalize_tipo_jornada(value: str | None) -> str:
	text = _normalize_match_text(value)
	if not text:
		return ""

	full_time_values = {
		"tc",
		"tiempo completo",
		"tiempo completa",
		"jornada completa",
		"jornada completo",
		"completo",
		"full time",
		"full-time",
		"fulltime",
	}
	part_time_values = {
		"tp",
		"tiempo parcial",
		"jornada parcial",
		"parcial",
		"part time",
		"part-time",
		"parttime",
	}

	if text in full_time_values:
		return TIPO_JORNADA_FULL_TIME
	if text in part_time_values:
		return TIPO_JORNADA_PART_TIME
	return ""


def map_tipo_jornada_to_legacy_employment_type(value: str | None) -> str:
	canonical = normalize_tipo_jornada(value)
	if canonical == TIPO_JORNADA_FULL_TIME:
		return "Full-time"
	if canonical == TIPO_JORNADA_PART_TIME:
		return "Part-time"
	return ""


def get_employee_doctype() -> str:
	for doctype in EMPLOYEE_DOCTYPE_CANDIDATES:
		if frappe.db.exists("DocType", doctype):
			return doctype
	return EMPLOYEE_DOCTYPE_FALLBACK


def get_employee_fieldnames(doctype: str | None = None) -> set[str]:
	doctype = doctype or get_employee_doctype()
	meta = frappe.get_meta(doctype)
	return {field.fieldname for field in meta.fields}


def find_employee_by_identifier(identifier: str) -> dict[str, str | int | float] | None:
	identifier = (identifier or "").strip()
	if not identifier:
		return None

	doctype = get_employee_doctype()
	fieldnames = get_employee_fieldnames(doctype)
	fetch_fields = _get_fetch_fields(fieldnames)

	for filters in _build_candidate_filters(doctype, fieldnames, identifier):
		employee = frappe.db.get_value(doctype, filters, fetch_fields, as_dict=True)
		if employee:
			return _normalize_employee_record(doctype, employee, fieldnames)

	return None


def get_employee_record(employee_id: str) -> dict[str, str | int | float] | None:
	employee_id = (employee_id or "").strip()
	if not employee_id:
		return None

	doctype = get_employee_doctype()
	if not frappe.db.exists(doctype, employee_id):
		return find_employee_by_identifier(employee_id)

	fieldnames = get_employee_fieldnames(doctype)
	fetch_fields = _get_fetch_fields(fieldnames)
	employee = frappe.db.get_value(doctype, employee_id, fetch_fields, as_dict=True)
	if not employee:
		return None

	return _normalize_employee_record(doctype, employee, fieldnames)


def get_payroll_employee_context(employee_id: str) -> dict[str, str | int | float | list[str] | None]:
	employee = get_employee_record(employee_id)
	tipo_jornada = employee.get("tipo_jornada") if employee else ""
	tipo_jornada_source = "ficha_empleado" if tipo_jornada else ""
	context = {
		"employee": employee,
		"employee_id": employee.get("name") if employee else (employee_id or "").strip(),
		"employee_name": employee.get("employee_name") if employee else "",
		"employee_doctype": employee.get("doctype") if employee else get_employee_doctype(),
		"document_number": employee.get("document_number") if employee else "",
		"branch": employee.get("branch") if employee else "",
		"salary": employee.get("ctc") if employee else 0,
		"employment_type": employee.get("employment_type") if employee else "",
		"tipo_jornada": tipo_jornada,
		"tipo_jornada_source": tipo_jornada_source,
		"tipo_jornada_canonical": tipo_jornada,
		"tipo_jornada_fallback": "",
		"company": employee.get("company") if employee else "",
		"department": employee.get("department") if employee else "",
		"email": employee.get("email") if employee else "",
		"contract_name": None,
		"contract_status": None,
		"contract_type": None,
		"monthly_hours": 220,
		"missing_config": [],
	}

	contract = get_active_contract(context["employee_id"] or employee_id, employee=employee)
	if contract:
		contract_tipo_jornada = normalize_tipo_jornada(contract.get("tipo_jornada"))
		resolved_tipo_jornada = context["tipo_jornada"] or contract_tipo_jornada or ""
		resolved_tipo_jornada_source = context["tipo_jornada_source"] or (
			"contrato_fallback" if contract_tipo_jornada else ""
		)
		context.update(
			{
				"contract_name": contract.get("name"),
				"contract_status": contract.get("estado_contrato") or contract.get("docstatus"),
				"contract_type": contract.get("tipo_contrato") or None,
				"salary": contract.get("salario") or context["salary"] or 0,
				"tipo_jornada": resolved_tipo_jornada,
				"tipo_jornada_source": resolved_tipo_jornada_source,
				"tipo_jornada_fallback": contract_tipo_jornada,
				"branch": contract.get("pdv_destino") or context["branch"] or "",
				"department": contract.get("cargo") or context["department"] or "",
				"monthly_hours": contract.get("horas_trabajadas_mes") or 220,
			}
		)

	context["employment_type"] = (
		map_tipo_jornada_to_legacy_employment_type(context.get("tipo_jornada"))
		or context.get("employment_type")
		or ""
	)

	missing_config = []
	if not context["employee_id"]:
		missing_config.append("ficha_empleado")
	if not context["document_number"]:
		missing_config.append("document_number")
	if not context["branch"]:
		missing_config.append("pdv")
	if not context["contract_name"]:
		missing_config.append("contrato")
	if not context["salary"]:
		missing_config.append("salary")
	if not context["monthly_hours"]:
		missing_config.append("monthly_hours")

	context["missing_config"] = missing_config
	return context


def get_active_contract(
	employee_id: str, employee: dict[str, str | int | float] | None = None
) -> dict[str, str] | None:
	employee_id = (employee_id or "").strip()
	if not frappe.db.exists("DocType", "Contrato"):
		return None

	employee = employee or get_employee_record(employee_id)
	filters = []
	if employee and employee.get("name"):
		filters.append({"empleado": employee.get("name")})
	if employee and employee.get("document_number"):
		filters.append({"numero_documento": employee.get("document_number")})
	if employee_id:
		filters.append({"empleado": employee_id})

	seen = set()
	for base_filters in filters:
		key = tuple(sorted(base_filters.items()))
		if key in seen:
			continue
		seen.add(key)
		contract = frappe.db.get_value(
			"Contrato",
			{
				**base_filters,
				"docstatus": ["<", 2],
				"estado_contrato": ["in", ["Activo", "Pendiente"]],
			},
			[
				"name",
				"estado_contrato",
				"salario",
				"tipo_contrato",
				"tipo_jornada",
				"pdv_destino",
				"cargo",
				"horas_trabajadas_mes",
				"fecha_ingreso",
				"fecha_fin_contrato",
				"numero_documento",
			],
			as_dict=True,
			order_by="fecha_ingreso desc, modified desc",
		)
		if contract:
			return contract

	return frappe.db.get_value(
		"Contrato",
		{
			"docstatus": ["<", 2],
			"empleado": employee.get("name") if employee else employee_id,
		},
		[
			"name",
			"estado_contrato",
			"salario",
			"tipo_contrato",
			"tipo_jornada",
			"pdv_destino",
			"cargo",
			"horas_trabajadas_mes",
			"fecha_ingreso",
			"fecha_fin_contrato",
			"numero_documento",
		],
		as_dict=True,
		order_by="fecha_ingreso desc, modified desc",
	)


def build_employee_parametrization_message(
	context: dict[str, str | int | float | list[str] | None],
	required_fields: list[str] | tuple[str, ...] | None = None,
) -> str | None:
	missing_config = context.get("missing_config")
	missing_config = missing_config if isinstance(missing_config, list) else []
	required_fields = list(required_fields or missing_config)
	missing = [field for field in required_fields if field in missing_config]
	if not missing:
		return None

	labels = {
		"ficha_empleado": _("la Ficha Empleado"),
		"document_number": _("el numero de documento en la Ficha Empleado"),
		"pdv": _("el PDV en la Ficha Empleado o el Contrato"),
		"contrato": _("un Contrato activo o pendiente"),
		"salary": _("el salario en el Contrato"),
		"monthly_hours": _("las horas trabajadas mes en el Contrato"),
	}
	parts = [labels.get(field, field) for field in missing]
	if len(parts) == 1:
		missing_text = parts[0]
		verb = _("Falta")
	else:
		missing_text = ", ".join(parts[:-1]) + _(" y ") + parts[-1]
		verb = _("Faltan")

	identifier = context.get("employee_name") or context.get("document_number") or context.get("employee_id") or _("la persona")
	return _("{verb} {missing_text} para continuar con nomina de {identifier}.").format(
		verb=verb,
		missing_text=missing_text,
		identifier=identifier,
	)


def _build_candidate_filters(doctype: str, fieldnames: set[str], identifier: str) -> list[dict[str, str]]:
	filters = [{"name": identifier}]

	if doctype == "Employee":
		for fieldname in ["employee", "custom_document_number"]:
			if fieldname in fieldnames:
				filters.append({fieldname: identifier})
	else:
		for fieldname in ["cedula", "numero_documento", "custom_document_number"]:
			if fieldname in fieldnames:
				filters.append({fieldname: identifier})

	unique_filters = []
	seen = set()
	for item in filters:
		key = tuple(item.items())
		if key in seen:
			continue
		seen.add(key)
		unique_filters.append(item)

	return unique_filters


def _get_fetch_fields(fieldnames: set[str]) -> list[str]:
	ordered_fields = [
		"name",
		"employee_name",
		"nombres",
		"apellidos",
		"employee",
		"custom_document_number",
		"cedula",
		"numero_documento",
		"branch",
		"pdv",
		"cargo",
		"tipo_jornada",
		"ctc",
		"employment_type",
		"company",
		"department",
		"personal_email",
		"email",
	]
	return [field for field in ordered_fields if field == "name" or field in fieldnames]


def _normalize_employee_record(
	doctype: str, employee: dict[str, str], fieldnames: set[str]
) -> dict[str, str | int | float]:
	full_name = employee.get("employee_name")
	if not full_name:
		full_name = " ".join(
			part for part in [employee.get("nombres"), employee.get("apellidos")] if part
		).strip()

	document_number = next(
		(
			employee.get(fieldname)
			for fieldname in ["custom_document_number", "cedula", "numero_documento", "employee"]
			if fieldname in fieldnames and employee.get(fieldname)
		),
		None,
	)

	branch = employee.get("branch") or employee.get("pdv") or ""
	contact_email = employee.get("personal_email") or employee.get("email") or ""
	tipo_jornada = normalize_tipo_jornada(employee.get("tipo_jornada") or employee.get("employment_type"))
	employment_type = map_tipo_jornada_to_legacy_employment_type(tipo_jornada) or employee.get("employment_type") or ""

	return {
		"doctype": doctype,
		"name": employee.get("name") or "",
		"employee_name": full_name or employee.get("name") or "",
		"document_number": document_number or employee.get("name") or "",
		"branch": branch,
		"ctc": employee.get("ctc") or 0,
		"employment_type": employment_type,
		"tipo_jornada": tipo_jornada,
		"company": employee.get("company") or "",
		"department": employee.get("department") or employee.get("cargo") or "",
		"email": contact_email,
	}


def _normalize_match_text(value: str | None) -> str:
	text = unicodedata.normalize("NFKD", str(value or ""))
	text = "".join(char for char in text if not unicodedata.combining(char))
	return " ".join(text.replace("_", " ").replace("-", " ").lower().split())
