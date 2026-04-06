import frappe


def execute():
	if not frappe.db.exists("Web Form", "candidato_portal"):
		return
	doc = frappe.get_doc("Web Form", "candidato_portal")
	doc.route = "candidato-form"
	doc.login_required = 0
	doc.apply_document_permissions = 1
	doc.web_form_fields = []
	fields = [
		{
			"fieldname": "tipo_documento",
			"fieldtype": "Select",
			"label": "Tipo Documento",
			"reqd": 1,
			"options": "Cedula\nPPT\nCedula de extranjeria\nPasaporte",
		},
		{
			"fieldname": "numero_documento",
			"fieldtype": "Data",
			"label": "Número Documento",
			"reqd": 1,
		},
		{
			"fieldname": "nombres",
			"fieldtype": "Data",
			"label": "Nombres",
			"reqd": 1,
		},
		{
			"fieldname": "apellidos",
			"fieldtype": "Data",
			"label": "Apellidos",
			"reqd": 1,
		},
		{
			"fieldname": "email",
			"fieldtype": "Data",
			"label": "Email",
			"reqd": 0,
		},
		{
			"fieldname": "celular",
			"fieldtype": "Data",
			"label": "Celular",
			"reqd": 0,
		},
		{
			"fieldname": "ciudad",
			"fieldtype": "Select",
			"label": "Ciudad",
			"reqd": 1,
			"options": "Bogota\nMedellin\nCartagena",
		},
		{
			"fieldname": "localidad",
			"fieldtype": "Select",
			"label": "Localidad",
			"reqd": 0,
			"options": "Antonio Nariño\nBarrios Unidos\nBosa\nChapinero\nCiudad Bolivar\nEngativa\nFontibon\nKennedy\nLa Candelaria\nLos Martires\nPuente Aranda\nRafael Uribe Uribe\nSan Cristobal\nSanta Fe\nSuba\nSumapaz\nTeusaquillo\nTunjuelito\nUsaquen\nUsme",
			"depends_on": "eval:doc.ciudad == 'Bogota'",
		},
		{
			"fieldname": "localidad_otras",
			"fieldtype": "Data",
			"label": "Localidad/Comuna",
			"reqd": 0,
			"depends_on": "eval:doc.ciudad != 'Bogota'",
		},
		{
			"fieldname": "barrio",
			"fieldtype": "Data",
			"label": "Barrio",
			"reqd": 0,
		},
		{
			"fieldname": "direccion",
			"fieldtype": "Data",
			"label": "Dirección",
			"reqd": 1,
		},
	]
	for field in fields:
		doc.append("web_form_fields", field)
	doc.save(ignore_permissions=True)
	frappe.db.commit()
