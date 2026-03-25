import frappe


def execute():
	_seed_cargos()
	_seed_documentos_requeridos()


def _seed_cargos():
	items = [
		{"codigo": "ADMIN", "nombre": "Administrativo", "activo": 1},
		{"codigo": "AUX_COC", "nombre": "Auxiliar de cocina", "activo": 1},
	]
	for item in items:
		if not frappe.db.exists("Cargo", item["codigo"]):
			frappe.get_doc({
				"doctype": "Cargo",
				"codigo": item["codigo"],
				"nombre": item["nombre"],
				"activo": item["activo"],
			}).insert(ignore_permissions=True)


def _seed_documentos_requeridos():
	items = [
		{
			"codigo": "DOC_HV",
			"nombre": "Hoja de vida actualizada.",
			"descripcion": "Hoja de vida actualizada.",
		},
		{
			"codigo": "DOC_ID",
			"nombre": "Fotocopia del documento de identidad al 150%.",
			"descripcion": "Fotocopia del documento de identidad al 150%.",
		},
		{
			"codigo": "DOC_BANCO",
			"nombre": "Certificación bancaria (No mayor a 30 días).",
			"descripcion": "En caso de no tener cuenta bancaria, favor escribir por medio de WhatsApp para poder remitir la Carta de apertura de cuenta bancaria con Bancolombia.",
		},
		{
			"codigo": "DOC_MANIP",
			"nombre": "Carnet manipulación de alimentos.",
			"descripcion": "En caso de no tener el curso favor realizarlo en el menor tiempo posible y adjuntar certificado.",
		},
		{
			"codigo": "DOC_EPS",
			"nombre": "Certificado de EPS (Salud).",
			"descripcion": "No mayor a 30 días. https://www.adres.gov.co/consulte-su-eps",
		},
		{
			"codigo": "DOC_PENSION",
			"nombre": "Certificado de fondo de pensiones.",
			"descripcion": "No mayor a 30 días.",
		},
		{
			"codigo": "DOC_CESANTIAS",
			"nombre": "Certificado de fondo de cesantías.",
			"descripcion": "No mayor a 30 días.",
		},
		{
			"codigo": "DOC_ESTUDIOS",
			"nombre": "Certificados de estudios y/o actas de grado Bachiller y posteriores.",
			"descripcion": "Certificados de estudios y/o actas de grado Bachiller y posteriores.",
		},
		{
			"codigo": "DOC_REFERENCIAS",
			"nombre": "2 cartas de referencias personales.",
			"descripcion": "Deben estar firmadas en físico o digital.",
		},
	]
	for item in items:
		if not frappe.db.exists("Documento Requerido", item["codigo"]):
			frappe.get_doc({
				"doctype": "Documento Requerido",
				"codigo": item["codigo"],
				"nombre": item["nombre"],
				"descripcion": item["descripcion"],
				"requerido": 1,
				"activo": 1,
			}).insert(ignore_permissions=True)
