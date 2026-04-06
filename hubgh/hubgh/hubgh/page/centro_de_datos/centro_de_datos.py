import frappe
import csv
import re
from io import StringIO
from frappe import _
from frappe.utils import getdate, validate_email_address

from hubgh.person_identity import normalize_document, reconcile_person_identity


ALLOWED_BULK_DOCTYPES = {
	"Punto de Venta": "create_punto",
	"Ficha Empleado": "create_empleado",
	"Novedad SST": "create_novedad",
	"User": "create_user",
}

EXPECTED_CSV_COLUMNS = {
	"Punto de Venta": {"nombre_pdv"},
	"Ficha Empleado": {"cedula", "pdv"},
	"Novedad SST": {"cedula_empleado", "tipo_novedad", "fecha_inicio", "fecha_fin"},
	"User": {"email"},
}


def _stable_error(code, detail=""):
	base = {
		"unsupported_doctype": "Tipo de carga no soportado en Centro de Datos.",
		"empty_file": "El archivo está vacío o no se pudo leer.",
		"missing_columns": "El archivo no contiene las columnas esperadas para esta carga.",
	}
	message = base.get(code, "Error de carga en Centro de Datos.")
	if detail:
		return f"{message} [{code}] {detail}"
	return f"{message} [{code}]"


@frappe.whitelist()
def get_supported_doctypes():
	return sorted(ALLOWED_BULK_DOCTYPES.keys())


def _decode_csv_content(content):
	if not isinstance(content, bytes):
		return content
	try:
		return content.decode("utf-8-sig")
	except UnicodeDecodeError:
		return content.decode("latin-1")


def _detect_csv_dialect(content):
	sample = content[:4096]
	try:
		return csv.Sniffer().sniff(sample, delimiters=",;\t").delimiter
	except csv.Error:
		first_line = content.splitlines()[0] if content.splitlines() else ""
		return max([",", ";", "\t"], key=first_line.count)


def _build_csv_reader(content):
	delimiter = _detect_csv_dialect(content)
	reader = csv.DictReader(StringIO(content), delimiter=delimiter)
	reader.fieldnames = [((header or "").lstrip("\ufeff")).strip() for header in (reader.fieldnames or [])]
	return reader


def _validate_expected_columns(doctype, fieldnames):
	expected = EXPECTED_CSV_COLUMNS.get(doctype, set())
	missing = sorted(column for column in expected if column not in set(fieldnames or []))
	if not missing:
		return None
	found = ", ".join(fieldnames or []) or "ninguna"
	return _stable_error(
		"missing_columns",
		f"Faltan: {', '.join(missing)}. Encontradas: {found}.",
	)

@frappe.whitelist()
def upload_data(doctype, file_url):
	if doctype not in ALLOWED_BULK_DOCTYPES:
		return {
			"success": 0,
			"committed": 0,
			"errors": [_stable_error("unsupported_doctype", doctype)],
			"supported_doctypes": get_supported_doctypes(),
		}

	# 1. Get the file content
	file_doc = frappe.get_doc("File", {"file_url": file_url})
	content = file_doc.get_content()

	if not content:
		frappe.throw(_(_stable_error("empty_file")))

	# 2. Decode content
	content = _decode_csv_content(content)

	reader = _build_csv_reader(content)
	columns_error = _validate_expected_columns(doctype, reader.fieldnames)
	if columns_error:
		return {
			"success": 0,
			"committed": 0,
			"errors": [columns_error],
			"supported_doctypes": get_supported_doctypes(),
		}

	success_count = 0
	errors = []
	if hasattr(frappe.db, "sql"):
		frappe.db.sql("SAVEPOINT centro_de_datos_upload")

	for index, row in enumerate(reader, start=2):
		try:
			if row and list(row.keys()) == [None]:
				continue
			globals()[ALLOWED_BULK_DOCTYPES[doctype]](row)
			success_count += 1
		except Exception as e:
			errors.append({"row": index, "code": "row_validation", "message": str(e)})

	if errors:
		if hasattr(frappe.db, "sql"):
			frappe.db.sql("ROLLBACK TO SAVEPOINT centro_de_datos_upload")
		elif hasattr(frappe.db, "rollback"):
			frappe.db.rollback()
		return {
			"success": 0,
			"committed": 0,
			"errors": errors,
			"supported_doctypes": get_supported_doctypes(),
		}

	frappe.db.commit()

	return {
		"success": success_count,
		"committed": success_count,
		"errors": errors,
		"supported_doctypes": get_supported_doctypes(),
	}


def _slugify(text, max_len=20):
	"""Genera un código normalizado desde un texto: mayúsculas, espacios a guiones."""
	slug = re.sub(r"[^A-Z0-9\-]", "", text.upper().replace(" ", "-"))
	return slug[:max_len] or "PDV"


def _log_identity_state(event, identity):
	logger = frappe.logger("hubgh.person_identity")
	payload = {
		"employee": identity.employee,
		"user": identity.user,
		"document": identity.document,
		"email": identity.email,
		"source": identity.source,
		"conflict": identity.conflict,
		"pending": identity.pending,
		"conflict_reason": identity.conflict_reason,
		"warnings": list(identity.warnings or ()),
	}
	if identity.conflict or identity.pending:
		logger.warning(event, extra=payload)
		return
	logger.info(event, extra=payload)


def _get_employee_identity_seed(employee_name):
	if not employee_name:
		return None, None
	employee_row = frappe.db.get_value("Ficha Empleado", employee_name, ["cedula", "email"], as_dict=True) or {}
	return normalize_document(employee_row.get("cedula")), (employee_row.get("email") or "").strip().lower() or None


def create_punto(row):
	nombre = (row.get("nombre_pdv") or "").strip()
	if not nombre:
		raise Exception("El campo 'nombre_pdv' es requerido.")

	if frappe.db.exists("Punto de Venta", {"nombre_pdv": nombre}):
		return  # ya existe, omitir silenciosamente

	# codigo es requerido y autoname — tomar del CSV o autogenerar desde nombre
	codigo = (row.get("codigo") or "").strip() or _slugify(nombre)

	# Si el código ya existe en otro PDV, agregamos un sufijo numérico
	base_codigo = codigo
	counter = 2
	while frappe.db.exists("Punto de Venta", {"codigo": codigo}):
		codigo = f"{base_codigo}-{counter}"
		counter += 1

	doc = frappe.new_doc("Punto de Venta")
	doc.nombre_pdv = nombre
	doc.codigo = codigo
	doc.zona = (row.get("zona") or "").strip()
	doc.ciudad = (row.get("ciudad") or "").strip()
	doc.departamento = (row.get("departamento") or "").strip()
	doc.planta_autorizada = int(row.get("planta_autorizada") or 0)
	doc.insert()


def create_empleado(row):
	cedula = (row.get("cedula") or "").strip()
	if not cedula:
		raise Exception("El campo 'cedula' es requerido.")

	if frappe.db.exists("Ficha Empleado", {"cedula": cedula}):
		return  # ya existe, omitir silenciosamente

	doc = frappe.new_doc("Ficha Empleado")
	doc.nombres = (row.get("nombres") or "").strip()
	doc.apellidos = (row.get("apellidos") or "").strip()
	doc.cedula = cedula
	doc.cargo = (row.get("cargo") or "").strip()
	doc.email = (row.get("email") or "").strip()
	doc.tipo_jornada = (row.get("tipo_jornada") or "").strip()
	doc.estado = (row.get("estado") or "Activo").strip()

	fecha_raw = (row.get("fecha_ingreso") or "").strip()
	if fecha_raw:
		doc.fecha_ingreso = getdate(fecha_raw)

	# pdv es reqd:1 — buscar por nombre exacto, fallar claro si no existe
	pdv_nombre = (row.get("pdv") or "").strip()
	if not pdv_nombre:
		raise Exception(f"Empleado {cedula}: el campo 'pdv' es requerido.")
	pdv_name = frappe.db.get_value("Punto de Venta", {"nombre_pdv": pdv_nombre}, "name")
	if not pdv_name:
		raise Exception(
			f"Empleado {cedula}: Punto de Venta '{pdv_nombre}' no encontrado. "
			"Cargá los Puntos de Venta antes de los Empleados."
		)
	doc.pdv = pdv_name

	doc.insert()
	identity = reconcile_person_identity(
		employee=doc,
		document=cedula,
		email=doc.email,
		allow_create_user=True,
		user_defaults={
			"first_name": doc.nombres or (row.get("first_name") or "").strip(),
			"last_name": doc.apellidos or (row.get("last_name") or "").strip(),
			"enabled": 1,
			"send_welcome_email": 0,
		},
		user_roles=["Empleado"],
	)
	_log_identity_state("centro_de_datos:create_empleado:identity_reconciled", identity)


def create_novedad(row):
	emp_name = frappe.db.get_value("Ficha Empleado", {"cedula": row["cedula_empleado"]}, "name")
	if not emp_name:
		raise Exception(f"Empleado con cédula {row['cedula_empleado']} no encontrado.")

	doc = frappe.new_doc("Novedad SST")
	doc.empleado = emp_name
	doc.tipo_novedad = row["tipo_novedad"]
	doc.fecha_inicio = getdate(row["fecha_inicio"])
	doc.fecha_fin = getdate(row["fecha_fin"])
	doc.descripcion = row.get("descripcion", "")
	doc.insert()


def create_user(row):
	email = (row.get("email") or "").strip()
	if not email:
		raise Exception("El campo 'email' es requerido.")

	document = normalize_document((row.get("cedula") or row.get("numero_documento") or row.get("username") or "").strip())
	identity = reconcile_person_identity(document=document, email=email)
	if identity.conflict:
		_log_identity_state("centro_de_datos:create_user:identity_conflict", identity)
		raise Exception(f"Conflicto canónico detectado para user {email}: {identity.conflict_reason}")

	if identity.employee and not document:
		document, _employee_email = _get_employee_identity_seed(identity.employee)

	if identity.user:
		user = frappe.get_doc("User", identity.user)
	else:
		if identity.employee:
			identity = reconcile_person_identity(
				employee=identity.employee,
				document=document,
				email=email,
				allow_create_user=True,
				user_defaults={
					"first_name": (row.get("first_name") or "").strip(),
					"last_name": (row.get("last_name") or "").strip(),
					"enabled": 1,
					"send_welcome_email": 0,
				},
			)
			if identity.conflict:
				_log_identity_state("centro_de_datos:create_user:identity_conflict", identity)
				raise Exception(f"Conflicto canónico detectado para user {email}: {identity.conflict_reason}")
			if identity.pending:
				_log_identity_state("centro_de_datos:create_user:identity_pending", identity)
				raise Exception(f"Estado pendiente canónico para user {email}: {identity.conflict_reason}")
			if identity.user:
				user = frappe.get_doc("User", identity.user)
			else:
				user = None
		else:
			user = None

	if not user:
		if not validate_email_address(email, throw=False):
			if not identity.pending:
				identity = identity.__class__(
					identity.employee,
					identity.user,
					identity.document,
					email,
					identity.source,
					conflict=identity.conflict,
					fallback=identity.fallback,
					pending=True,
					conflict_reason=identity.conflict_reason or "invalid_or_missing_email",
					warnings=tuple(identity.warnings or ()) + ("missing_valid_email",),
				)
			_log_identity_state("centro_de_datos:create_user:identity_pending", identity)
			raise Exception(f"No se puede crear User sin email válido: {email}")

		if frappe.db.exists("User", email):
			return

		user = frappe.new_doc("User")
		user.email = email
		user.username = document or None
		user.employee = identity.employee or None
		user.first_name = (row.get("first_name") or "").strip()
		user.last_name = (row.get("last_name") or "").strip()
		user.enabled = 1
		user.send_welcome_email = 0
		user.insert(ignore_permissions=True)

		if document:
			identity = reconcile_person_identity(user=user, document=document, email=email)
			if identity.conflict:
				_log_identity_state("centro_de_datos:create_user:identity_conflict", identity)
				raise Exception(f"Conflicto canónico detectado para user {email}: {identity.conflict_reason}")
			_log_identity_state("centro_de_datos:create_user:identity_reconciled", identity)

	# rol: nombre canónico del Role (ej: "Gestión Humana", "HR SST", "System Manager")
	rol = (row.get("rol") or "").strip()
	if rol and frappe.db.exists("Role", rol):
		user.add_roles(rol)


def create_comentario_bienestar(row):
	"""Legacy helper kept only for technical compatibility; not used in active flow."""
	emp_name = frappe.db.get_value("Ficha Empleado", {"cedula": row["cedula_empleado"]}, "name")
	if not emp_name:
		raise Exception(f"Empleado con cédula {row['cedula_empleado']} no encontrado.")

	doc = frappe.new_doc("Comentario Bienestar")
	doc.empleado = emp_name
	if row.get("fecha"):
		doc.fecha = getdate(row["fecha"])
	doc.tipo = row.get("tipo", "")
	doc.comentario = row.get("comentario", "")
	doc.insert()
