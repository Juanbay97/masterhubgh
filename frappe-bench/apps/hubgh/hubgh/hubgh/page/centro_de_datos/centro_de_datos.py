import frappe
import csv
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

def create_punto(row):
    if not frappe.db.exists("Punto de Venta", {"nombre_pdv": row["nombre_pdv"]}):
        doc = frappe.new_doc("Punto de Venta")
        doc.nombre_pdv = row["nombre_pdv"]
        doc.zona = row["zona"]
        doc.planta_autorizada = int(row["planta_autorizada"])
        doc.insert()

def create_empleado(row):
    # Check duplicate by Cedula
    if not frappe.db.exists("Ficha Empleado", {"cedula": row["cedula"]}):
        doc = frappe.new_doc("Ficha Empleado")
        doc.nombres = row["nombres"]
        doc.apellidos = row["apellidos"]
        doc.cedula = row["cedula"]
        doc.cargo = row["cargo"]
        doc.email = row["email"]
        doc.fecha_ingreso = getdate(row["fecha_ingreso"])
        
        # Link PDV by name
        pdv_name = frappe.db.get_value("Punto de Venta", {"nombre_pdv": row["pdv (nombre)"]}, "name")
        if pdv_name:
            doc.pdv = pdv_name
            
        doc.insert()

def create_novedad(row):
    # Find Employee by Cedula
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
    email = row["email"]
    if not frappe.db.exists("User", email):
        user = frappe.new_doc("User")
        user.email = email
        user.first_name = row["first_name"]
        user.enabled = 1
        user.send_welcome_email = 0
        user.insert(ignore_permissions=True)
        
        # Add Role
        role = row["role_profile_name"]
        if role and frappe.db.exists("Role", role):
            user.add_roles(role)

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
