
import frappe

def setup():
    create_pdv()
    create_empleado()
    create_novedad()
    create_disciplinario()
    create_sst()
    create_feedback()
    frappe.db.commit()

def create_pdv():
    if not frappe.db.exists("DocType", "Punto de Venta"):
        doc = frappe.get_doc({
            "doctype": "DocType",
            "module": "HubGH",
            "custom": 0,
            "name": "Punto de Venta",
            "naming_rule": "Expression",
            "autoname": "format:{codigo}",
            "fields": [
                {"label": "Nombre del Punto", "fieldname": "nombre_pdv", "fieldtype": "Data", "reqd": 1, "in_list_view": 1},
                {"label": "Código", "fieldname": "codigo", "fieldtype": "Data", "reqd": 1, "unique": 1, "in_list_view": 1},
                {"label": "Ciudad", "fieldname": "ciudad", "fieldtype": "Data"},
                {"label": "Departamento", "fieldname": "departamento", "fieldtype": "Data"},
                {"label": "Zona", "fieldname": "zona", "fieldtype": "Select", "options": "Norte\nSur\nOriente\nOccidente\nCentro", "default": "Centro"},
                {"label": "Planta Autorizada", "fieldname": "planta_autorizada", "fieldtype": "Int", "default": 0},
                {"label": "Activo", "fieldname": "activo", "fieldtype": "Check", "default": 1}
            ],
            "permissions": [{"role": "System Manager", "read": 1, "write": 1, "create": 1, "delete": 1}]
        })
        doc.insert()
        print("Created DocType: Punto de Venta")

def create_empleado():
    if not frappe.db.exists("DocType", "Ficha Empleado"):
        doc = frappe.get_doc({
            "doctype": "DocType",
            "module": "HubGH",
            "custom": 0,
            "name": "Ficha Empleado",
            "naming_rule": "Expression",
            "autoname": "format:{cedula}",
            "fields": [
                {"label": "Nombres", "fieldname": "nombres", "fieldtype": "Data", "reqd": 1, "in_list_view": 1},
                {"label": "Apellidos", "fieldname": "apellidos", "fieldtype": "Data", "reqd": 1, "in_list_view": 1},
                {"label": "Cédula", "fieldname": "cedula", "fieldtype": "Data", "reqd": 1, "unique": 1, "in_list_view": 1},
                {"label": "Punto de Venta", "fieldname": "pdv", "fieldtype": "Link", "options": "Punto de Venta", "reqd": 1},
                {"label": "Cargo", "fieldname": "cargo", "fieldtype": "Data"},
                {"label": "Fecha Ingreso", "fieldname": "fecha_ingreso", "fieldtype": "Date"},
                {"label": "Estado", "fieldname": "estado", "fieldtype": "Select", "options": "Activo\nInactivo\nVacaciones\nIncapacitado\nLicencia\nSuspensión\nSeparación del Cargo\nRecomendación Médica\nEmbarazo\nRetirado", "default": "Activo"},
                {"label": "Email", "fieldname": "email", "fieldtype": "Data"}
            ],
            "title_field": "nombres",
            "permissions": [{"role": "System Manager", "read": 1, "write": 1, "create": 1, "delete": 1}]
        })
        doc.insert()
        print("Created DocType: Ficha Empleado")

def create_novedad():
    if not frappe.db.exists("DocType", "Novedad SST"):
        doc = frappe.get_doc({
            "doctype": "DocType",
            "module": "HubGH",
            "custom": 0,
            "name": "Novedad SST",
            "naming_rule": "Expression",
            "autoname": "format:NOV-{YYYY}-{#####}",
            "fields": [
                {"label": "Empleado", "fieldname": "empleado", "fieldtype": "Link", "options": "Ficha Empleado", "reqd": 1, "in_list_view": 1},
                {"label": "Tipo Novedad", "fieldname": "tipo_novedad", "fieldtype": "Select", "options": "Incapacidad\nLicencia\nVacaciones\nSuspensión\nSeparación del Cargo\nRecomendación Médica\nEmbarazo\nRetiro\nOtro", "reqd": 1, "in_list_view": 1},
                {"label": "Categoría", "fieldname": "categoria_novedad", "fieldtype": "Select", "options": "SST\nRelaciones Laborales\nBienestar\nGeneral", "default": "General"},
                {"label": "Origen DocType", "fieldname": "ref_doctype", "fieldtype": "Link", "options": "DocType"},
                {"label": "Origen Documento", "fieldname": "ref_docname", "fieldtype": "Dynamic Link", "options": "ref_doctype"},
                {"label": "Impacta estado del empleado", "fieldname": "impacta_estado", "fieldtype": "Check", "default": 1},
                {"label": "Estado destino", "fieldname": "estado_destino", "fieldtype": "Select", "options": "Vacaciones\nIncapacitado\nLicencia\nSuspensión\nSeparación del Cargo\nRecomendación Médica\nEmbarazo\nRetirado", "depends_on": "eval:doc.impacta_estado"},
                {"label": "Fecha Inicio", "fieldname": "fecha_inicio", "fieldtype": "Date", "reqd": 1},
                {"label": "Fecha Fin", "fieldname": "fecha_fin", "fieldtype": "Date"},
                {"label": "Descripción", "fieldname": "descripcion", "fieldtype": "Small Text"},
                {"label": "Estado", "fieldname": "estado", "fieldtype": "Select", "options": "Abierto\nCerrado", "default": "Abierto"}
            ],
            "permissions": [{"role": "System Manager", "read": 1, "write": 1, "create": 1, "delete": 1}]
        })
        doc.insert()
        print("Created DocType: Novedad SST")

def create_disciplinario():
    if not frappe.db.exists("DocType", "Caso Disciplinario"):
        doc = frappe.get_doc({
            "doctype": "DocType",
            "module": "HubGH",
            "custom": 0,
            "name": "Caso Disciplinario",
            "naming_rule": "Expression",
            "autoname": "format:DIS-{YYYY}-{#####}",
            "fields": [
                {"label": "Empleado", "fieldname": "empleado", "fieldtype": "Link", "options": "Ficha Empleado", "reqd": 1, "in_list_view": 1},
                {"label": "Fecha Incidente", "fieldname": "fecha_incidente", "fieldtype": "Date", "reqd": 1},
                {"label": "Tipo Falta", "fieldname": "tipo_falta", "fieldtype": "Select", "options": "Leve\nGrave\nGravísima"},
                {"label": "Descripción", "fieldname": "descripcion", "fieldtype": "Text Editor"},
                {"label": "Estado", "fieldname": "estado", "fieldtype": "Select", "options": "Abierto\nEn Proceso\nCerrado", "default": "Abierto"}
            ],
            "permissions": [{"role": "System Manager", "read": 1, "write": 1, "create": 1, "delete": 1}]
        })
        doc.insert()
        print("Created DocType: Caso Disciplinario")

def create_sst():
    if not frappe.db.exists("DocType", "Caso SST"):
        doc = frappe.get_doc({
            "doctype": "DocType",
            "module": "HubGH",
            "custom": 0,
            "name": "Caso SST",
            "naming_rule": "Expression",
            "autoname": "format:SST-{YYYY}-{#####}",
            "fields": [
                {"label": "Punto de Venta", "fieldname": "pdv", "fieldtype": "Link", "options": "Punto de Venta", "reqd": 1},
                {"label": "Empleado (Opcional)", "fieldname": "empleado", "fieldtype": "Link", "options": "Ficha Empleado"},
                {"label": "Fecha Evento", "fieldname": "fecha_evento", "fieldtype": "Date", "reqd": 1},
                {"label": "Tipo Evento", "fieldname": "tipo_evento", "fieldtype": "Select", "options": "Accidente\nIncidente\nEnfermedad Laboral\nCondición Insegura"},
                {"label": "Severidad", "fieldname": "severidad", "fieldtype": "Select", "options": "Baja\nMedia\nAlta"},
                {"label": "Descripción", "fieldname": "descripcion", "fieldtype": "Text Editor"},
                {"label": "Estado", "fieldname": "estado", "fieldtype": "Select", "options": "Abierto\nCerrado", "default": "Abierto"}
            ],
            "permissions": [{"role": "System Manager", "read": 1, "write": 1, "create": 1, "delete": 1}]
        })
        doc.insert()
        print("Created DocType: Caso SST")

def create_feedback():
    if not frappe.db.exists("DocType", "Feedback Punto"):
        doc = frappe.get_doc({
            "doctype": "DocType",
            "module": "HubGH",
            "custom": 0,
            "name": "Feedback Punto",
            "naming_rule": "Expression",
            "autoname": "format:FB-{YYYY}-{#####}",
            "fields": [
                {"label": "Punto de Venta", "fieldname": "pdv", "fieldtype": "Link", "options": "Punto de Venta", "reqd": 1},
                {"label": "Fecha", "fieldname": "fecha", "fieldtype": "Date", "default": "Today"},
                {"label": "Tipo Feedback", "fieldname": "tipo", "fieldtype": "Select", "options": "Clima\nInfraestructura\nDotación\nOtro"},
                {"label": "Comentarios", "fieldname": "comentarios", "fieldtype": "Text Editor"},
                {"label": "Acción Requerida", "fieldname": "accion_requerida", "fieldtype": "Check", "default": 0}
            ],
            "permissions": [{"role": "System Manager", "read": 1, "write": 1, "create": 1, "delete": 1}]
        })
        doc.insert()
        print("Created DocType: Feedback Punto")
