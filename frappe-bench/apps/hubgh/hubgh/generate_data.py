
import frappe
from frappe.utils import add_days, nowdate

def generate_data():
    # 1. Crear Puntos de Venta
    puntos = [
        {"codigo": "PDV001", "nombre": "Centro Mayor", "zona": "Centro", "planta": 10},
        {"codigo": "PDV002", "nombre": "Unicentro", "zona": "Norte", "planta": 8},
        {"codigo": "PDV003", "nombre": "Plaza Central", "zona": "Occidente", "planta": 12}
    ]

    for p in puntos:
        if not frappe.db.exists("Punto de Venta", p["codigo"]):
            doc = frappe.get_doc({
                "doctype": "Punto de Venta",
                "codigo": p["codigo"],
                "nombre_pdv": p["nombre"],
                "zona": p["zona"],
                "planta_autorizada": p["planta"]
            })
            doc.insert()
            print(f"Creado PDV: {p['nombre']}")

    # 2. Crear Empleados
    empleados = [
        {"cedula": "1001", "nombres": "Juan", "apellidos": "Perez", "pdv": "PDV001", "cargo": "Vendedor", "estado": "Activo"},
        {"cedula": "1002", "nombres": "Maria", "apellidos": "Gomez", "pdv": "PDV001", "cargo": "Cajero", "estado": "Activo"},
        {"cedula": "1003", "nombres": "Carlos", "apellidos": "Lopez", "pdv": "PDV001", "cargo": "Vendedor", "estado": "Incapacitado"},
        {"cedula": "1004", "nombres": "Ana", "apellidos": "Torres", "pdv": "PDV002", "cargo": "Admin", "estado": "Activo"},
        {"cedula": "1005", "nombres": "Pedro", "apellidos": "Ruiz", "pdv": "PDV001", "cargo": "Vendedor", "estado": "Activo"}
    ]

    for e in empleados:
        if not frappe.db.exists("Ficha Empleado", {"cedula": e["cedula"]}):
            doc = frappe.get_doc({
                "doctype": "Ficha Empleado",
                "cedula": e["cedula"],
                "nombres": e["nombres"],
                "apellidos": e["apellidos"],
                "pdv": e["pdv"],
                "cargo": e["cargo"],
                "estado": e["estado"],
                "fecha_ingreso": "2023-01-01"
            })
            doc.insert()
            print(f"Creado Empleado: {e['nombres']}")

    # 3. Novedades (Juan Perez - Vacaciones, Carlos Lopez - Incapacidad)
    novedades = [
         {"empleado": "1001", "tipo": "Vacaciones", "inicio": nowdate(), "fin": add_days(nowdate(), 15)},
         {"empleado": "1003", "tipo": "Incapacidad", "inicio": nowdate(), "fin": add_days(nowdate(), 5)}
    ]
    
    for n in novedades:
        empleado_name = frappe.db.get_value("Ficha Empleado", {"cedula": n["empleado"]}, "name")
        if empleado_name:
             doc = frappe.get_doc({
                "doctype": "Novedad SST",
                "empleado": empleado_name,
                "tipo_novedad": n["tipo"],
                "fecha_inicio": n["inicio"],
                "fecha_fin": n["fin"],
                "estado": "Abierto"
            })
             doc.insert()

    # 4. Caso Disciplinario (Maria Gomez)
    empleado_name = frappe.db.get_value("Ficha Empleado", {"cedula": "1002"}, "name")
    if empleado_name:
        doc = frappe.get_doc({
            "doctype": "Caso Disciplinario",
            "empleado": empleado_name,
            "fecha_incidente": add_days(nowdate(), -2),
            "tipo_falta": "Leve",
            "descripcion": "Llegada tarde reiterada",
            "estado": "Abierto"
        })
        doc.insert()

    frappe.db.commit()
