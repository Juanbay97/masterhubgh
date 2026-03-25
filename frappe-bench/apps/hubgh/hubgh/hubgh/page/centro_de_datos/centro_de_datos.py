import frappe
import csv
import re
from frappe import _
from frappe.utils import getdate


ALLOWED_BULK_DOCTYPES = {
	"Punto de Venta": "create_punto",
	"Ficha Empleado": "create_empleado",
	"Novedad SST": "create_novedad",
	"User": "create_user",
}


def _stable_error(code, detail=""):
	base = {
		"unsupported_doctype": "Tipo de carga no soportado en Centro de Datos.",
		"empty_file": "El archivo está vacío o no se pudo leer.",
	}
	message = base.get(code, "Error de carga en Centro de Datos.")
	if detail:
		return f"{message} [{code}] {detail}"
	return f"{message} [{code}]"


@frappe.whitelist()
def get_supported_doctypes():
	return sorted(ALLOWED_BULK_DOCTYPES.keys())

@frappe.whitelist()
def upload_data(doctype, file_url):
	if doctype not in ALLOWED_BULK_DOCTYPES:
		return {
			"success": 0,
			"errors": [_stable_error("unsupported_doctype", doctype)],
			"supported_doctypes": get_supported_doctypes(),
		}

	# 1. Get the file content
	file_doc = frappe.get_doc("File", {"file_url": file_url})
	content = file_doc.get_content()

	if not content:
		frappe.throw(_(_stable_error("empty_file")))

	# 2. Decode content
	if isinstance(content, bytes):
		try:
			content = content.decode("utf-8")
		except UnicodeDecodeError:
			content = content.decode("latin-1")

	reader = csv.DictReader(content.splitlines())

	success_count = 0
	errors = []

	for row in reader:
		try:
			if row and list(row.keys()) == [None]:
				continue
			globals()[ALLOWED_BULK_DOCTYPES[doctype]](row)
			success_count += 1
		except Exception as e:
			errors.append(f"Error en fila {row}: {str(e)}")

	frappe.db.commit()

	return {
		"success": success_count,
		"errors": errors,
		"supported_doctypes": get_supported_doctypes(),
	}


def _slugify(text, max_len=20):
	"""Genera un código normalizado desde un texto: mayúsculas, espacios a guiones."""
	slug = re.sub(r"[^A-Z0-9\-]", "", text.upper().replace(" ", "-"))
	return slug[:max_len] or "PDV"


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

	if frappe.db.exists("User", email):
		return  # ya existe, omitir silenciosamente

	user = frappe.new_doc("User")
	user.email = email
	user.first_name = (row.get("first_name") or "").strip()
	user.last_name = (row.get("last_name") or "").strip()
	user.enabled = 1
	user.send_welcome_email = 0
	user.insert(ignore_permissions=True)

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
