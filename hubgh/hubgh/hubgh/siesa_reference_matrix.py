import frappe


REFERENCE_MATRIX_VERSION = "2026.04"


CODE_PAD_BY_DOCTYPE = {
	"Grupo Empleados Siesa": 3,
	"Centro Trabajo Siesa": 3,
	"Centro Costos Siesa": 6,
	"Cargo": 3,
	"Nivel Educativo Siesa": 2,
}


OFFICIAL_SIESA_CATALOGS = {
	"Tipo Cotizante Siesa": [
		("01", "DEPENDIENTE"),
		("12", "APRENDIZ ETAPA LECTIVA"),
		("19", "APRENDIZ ETAPA PRODUCTIVA"),
	],
	"Entidad CCF Siesa": [
		("001", "CCF Bogotá"),
		("002", "CCF Medellín"),
	],
	"Unidad Negocio Siesa": [
		("100", "HAMBURGUESAS"),
		("200", "POSTRES"),
		("999", "ADMINISTRATIVO"),
	],
	"Grupo Empleados Siesa": [
		("001", "Personal Administrativo"),
		("002", "Personal Operativo"),
		("003", "Personal Salario Integral"),
		("004", "Aprendices Sena"),
	],
	"Centro Costos Siesa": [
		("110101", "SOCIOS ACCIONISTAS"),
		("110102", "RECURSOS HUMANOS"),
		("110103", "ADMINISTRATIVA"),
		("110104", "SISTEMAS"),
		("110105", "CONTABILIDAD"),
		("110106", "MERCADEO"),
		("220101", "PRODUCCION"),
		("220102", "OPERACION"),
		("220103", "CALIDAD"),
		("220104", "MANTENIMIENTO"),
		("220105", "ADMON PTO VTA"),
		("220106", "EVENTOS"),
	],
	"Centro Trabajo Siesa": [
		("001", "Nivel Riesgo 1 (0,522%)"),
		("002", "Nivel Riesgo 2 (1,044%)"),
		("003", "Nivel Riesgo 3 (2,436%)"),
		("004", "Nivel Riesgo 4 (4,35%)"),
		("005", "Nivel Riesgo 5 (6,96%)"),
	],
	"Nivel Educativo Siesa": [
		("01", "PREESCOLAR"),
		("02", "BÁSICA PRIMARIA"),
		("03", "BÁSICA SECUNDARIA"),
		("04", "MEDIA"),
		("05", "TÉCNICO LABORAL"),
		("06", "FORMACIÓN TÉCNICA PROFESIONAL"),
		("07", "TECNOLÓGICA"),
		("08", "UNIVERSITARIA"),
		("09", "ESPECIALIZACIÓN"),
		("10", "MAESTRÍA"),
		("11", "DOCTORADO"),
		("12", "SIN DEFINIR"),
		("13", "OTROS"),
	],
}


SOCIAL_SECURITY_REFERENCE_CATALOGS = {
	"Entidad EPS Siesa": [
		("210101", "EPS SURA"),
		("210102", "NUEVA EPS"),
		("210103", "EPS SANITAS"),
		("210104", "SALUD TOTAL EPS"),
		("210105", "COMPENSAR EPS"),
		("210106", "FAMISANAR EPS"),
		("210107", "COOSALUD EPS"),
		("210108", "ALIANSALUD EPS"),
	],
	"Entidad AFP Siesa": [
		("230301", "COLPENSIONES"),
		("230302", "PORVENIR"),
		("230303", "PROTECCIÓN"),
		("230304", "COLFONDOS"),
		("230305", "SKANDIA"),
	],
	"Entidad Cesantias Siesa": [
		("240301", "PORVENIR CESANTÍAS"),
		("240302", "PROTECCIÓN CESANTÍAS"),
		("240303", "COLFONDOS CESANTÍAS"),
		("240304", "SKANDIA CESANTÍAS"),
		("240305", "FONDO NACIONAL DEL AHORRO"),
	],
}


OFFICIAL_BANCO_BANCOLOMBIA_CODES = [
	("BANCAMIA S.A", "1059"),
	("BANCO AGRARIO", "1040"),
	("BANCO AV VILLAS", "6013677"),
	("BANCO BTG PACTUAL", "1805"),
	("BANCO CAJA SOCIAL BCSC SA", "5600829"),
	("BANCO CONTACTAR S.A.", "1819"),
	("BANCO COOPERATIVO COOPCENTRAL", "1066"),
	("BANCO CREDIFINANCIERA SA.", "1558"),
	("BANCO DAVIVIENDA SA", "5895142"),
	("BANCO DE BOGOTA", "5600010"),
	("BANCO DE OCCIDENTE", "5600230"),
	("BANCO FALABELLA S.A.", "1062"),
	("BANCO FINANDINA S.A.", "1063"),
	("BANCO GNB SUDAMERIS", "5600120"),
	("BANCO J.P. MORGAN COLOMBIA S.A", "1071"),
	("BANCO MUNDO MUJER", "1047"),
	("BANCO PICHINCHA", "1060"),
	("BANCO POPULAR", "5600023"),
	("BANCO SANTANDER DE NEGOCIOS CO", "1065"),
	("BANCO SERFINANZA S.A", "1069"),
	("BANCO UNION S.A", "1303"),
	("BANCO W S.A", "1053"),
	("BANCOLDEX S.A.", "1031"),
	("BANCOLOMBIA", "5600078"),
	("BANCOOMEVA", "1061"),
	("BBVA COLOMBIA", "5600133"),
	("BOLD CF", "1808"),
	("CITIBANK", "5600094"),
	("COINK", "1812"),
	("COLTEFINANCIERA S.A", "1370"),
	("CONFIAR COOPERATIVA FINANCIERA", "1292"),
	("COOPERATIVA FINANCIERA DE ANTI", "1283"),
	("COOTRAFA COOPERATIVA FINANCIER", "1289"),
	("DAVIPLATA", "1551"),
	("DING TECNIPAGOS SA", "1802"),
	("FINANCIERA JURISCOOP S.A. COMP", "1121"),
	("GLOBAL66", "1814"),
	("IRIS", "1637"),
	("ITAU", "5600146"),
	("ITAU antes Corpbanca", "5600065"),
	("JFK COOPERATIVA FINANCIERA", "1286"),
	("LULO BANK S.A.", "1070"),
	("MIBANCO S.A.", "1067"),
	("MOVII", "1801"),
	("NEQUI", "1507"),
	("NU", "1809"),
	("PIBANK", "1560"),
	("POWWI", "1803"),
	("RAPPIPAY", "1811"),
	("RIA MONEY TRANSFER COLOMBIA S.", "1817"),
	("SCOTIABANK COLPATRIA S.A", "5600191"),
	("Ualá", "1804"),
]


OFFICIAL_CARGOS = [
	("001", "GERENTE ADMINISTRATIVO"), ("002", "GERENTE OPERATIVO"), ("003", "GERENTE DE MERCADEO"),
	("050", "JEFE RECURSOS HUMANOS"), ("100", "COORDINADOR OPERACIONES"), ("101", "COORDINADOR DE CALIDAD"),
	("102", "COORDINADOR DE MANTENIMIENTO"), ("103", "COORDINADOR DE SISTEMAS"), ("150", "CHEF DE INNOVACION"),
	("200", "ADMINISTRADOR CENTRO PRODUCCION"), ("201", "ADMINISTRADOR PUNTO VENTA"), ("250", "AUXILIAR DE MERCADEO"),
	("251", "ASISTENTE ADMINISTRADOR PUNTO DE VENTA"), ("252", "ASISTENTE DE PRODUCCION"),
	("253", "ASISTENTE JUNIOR ADMON PUNTO VENTA"), ("254", "ASISTENTE ADMINISTRATIVA"), ("255", "ASISTENTE CALIDAD"),
	("256", "ASISTENTE CONTABLE"), ("257", "ASISTENTE DE NOMINA"), ("258", "ASISTENTE DE GESTIÓN HUMANA"),
	("259", "ASISTENTE SALUD Y SEGURIDAD EN EL TRABAJO"), ("300", "AUXILIAR CONTABLE"),
	("353", "SERVICIOS GENERALES ADMINISTRACION"), ("400", "APRENDIZ SENA PRODUCTIVO"),
	("401", "PRACTICANTE UNIVERSITARIO"), ("354", "DESPOSTADOR"), ("249", "ANALISTA DE SISTEMAS"),
	("355", "SERVICIOS GENERALES OPERATIVOS"), ("356", "DIRECTOR DE INNOVACION"), ("260", "PROFESIONAL SST"),
	("105", "COORDINADORA DE COSTOS"), ("004", "PIZZERO"), ("104", "ANALISTA DE SERVICIO AL CLIENTE"),
	("261", "DIRECTOR CONTABLE"), ("402", "APRENDIZ SENA LECTIVO"), ("262", "ANALISTA CONTABLE"),
	("263", "ASISTENTE DE PRODUCCIÓN Y MERCADEO"), ("301", "AUXILIAR RECURSOS HUMANOS"),
	("302", "AUXILIAR DE CALIDAD"), ("203", "JEFE DE PLANTA"), ("106", "SUPERVISOR DE PRODUCCION"),
	("264", "JUDICANTE"), ("107", "COORDINADOR DE MERCADEO"), ("005", "DIRECTORA DE GESTION HUMANA"),
	("108", "LIDER DE NOMINA"), ("109", "LIDER DE SELECCIÓN"), ("110", "LIDER DE FORMACION Y CAPACITACION"),
	("265", "ANALISTA DE PRODUCCIÓN Y MERCADEO"), ("111", "COORDINADOR ADMINISTRATIVO"),
	("112", "ARQUITECTO (A)"), ("113", "LIDER ADMINISTRACIÓN DE PERSONAL"), ("303", "AUXILIAR DE NOMINA"),
	("114", "LIDER DE SST"), ("304", "AUXILIAR DE GESTIÓN HUMANA"), ("305", "AUXILIAR DE COSTOS"),
	("306", "AUXILIAR SERVICIO AL CLIENTE"), ("307", "AUXILIAR ADMINISTRATIVO"), ("308", "AUXILIAR DE SELECCIÓN"),
	("360", "CAJERA"), ("309", "AUXILIAR DE ARCHIVO"), ("266", "ANALISTA DE GESTION HUMANA"),
	("248", "ASISTENTE CALIDAD PLANTA DE HELADOS"), ("267", "ANALISTA ADMINISTRATIVO"),
	("204", "PROFESIONAL CONTABLE"), ("006", "GERENTE DE GESTION HUMANA"),
	("007", "DIRECTORA DE PRODUCCION Y CALIDAD"), ("008", "DIRECTOR DE OPERACIONES"),
	("049", "COORDINADOR ADMINISTRACION DE PERSONAL"), ("048", "COORDINADOR DE BIENESTAR"),
	("268", "ANALISTA DE BIENESTAR Y FORMACION"), ("361", "AUXILIAR PRODUCCION ADMINISTRATIVO"),
	("310", "AUXILIAR DE INGENIERIA"), ("115", "ESPECIALISTA DE RECLUTAMIENTO Y SELECCIÓN"),
	("116", "ESPECIALISTA DE SEGURIDAD Y SALUD EN EL TRABAJO"), ("362", "AUXILIAR DE SISTEMAS"),
	("269", "ANALISTA NOMINA SR"), ("270", "ASISTENTE CONTABLE SR"), ("271", "ASISTENTE CONTABLE JR"),
	("272", "ANALISTA CONTABLE JR"), ("273", "GENERALISTA DE GESTION HUMANA"), ("117", "LIDER DE PUNTO"),
	("403", "STEWARD"), ("404", "TECNICO MANTENIMIENTO"), ("405", "INGENIERO DE MANTENIMIENTO"),
	("406", "ANALISTA DE COMPRAS"), ("407", "COORDINADOR DE IMPLEMENTACIÓN ESTRATÉGICA Y GESTIÓN DE DATOS"),
	("408", "ASISTENTE CALIDAD PLANTA"), ("409", "GERENTE DE MERCADEO Y SERVICIO AL CLIENTE"),
	("410", "ANALISTA CALIDAD"), ("311", "AUXILIAR DE COSTOS"), ("312", "AUXILIAR DE NOMINA"),
	("411", "COORDINADORA AUDIOVISUAL"), ("412", "COORDINADORA DE ESTRATEGIA"), ("413", "DIRECTOR DE EXPANSION"),
	("414", "ASISTENTE ADMINISTRACION DE PERSONAL"), ("416", "AUXILIAR DE COCINA PUNTO DE VENTA"),
	("417", "AUXILIAR DE PRODUCCIÓN"),
]


def normalize_code_for_doctype(doctype, raw_code):
	value = str(raw_code or "").strip()
	if not value:
		return ""
	if value.isdigit():
		width = CODE_PAD_BY_DOCTYPE.get(doctype)
		if width:
			return value.zfill(width)
	return value


def _upsert_reference_row(doctype, code, description):
	code = normalize_code_for_doctype(doctype, code)
	description = str(description or "").strip()
	if not code or not description:
		return None

	name = frappe.db.get_value(doctype, {"code": code}, "name")
	if not name:
		name = frappe.db.get_value(doctype, {"description": description}, "name")

	if name:
		doc = frappe.get_doc(doctype, name)
		changed = False
		if str(doc.get("code") or "") != code:
			doc.code = code
			changed = True
		if str(doc.get("description") or "") != description:
			doc.description = description
			changed = True
		if int(doc.get("enabled") or 0) != 1:
			doc.enabled = 1
			changed = True
		if changed:
			doc.save(ignore_permissions=True)
		return doc.name

	doc = frappe.get_doc({"doctype": doctype, "code": code, "description": description, "enabled": 1})
	doc.insert(ignore_permissions=True)
	return doc.name


def ensure_reference_catalog(doctype):
	rows = OFFICIAL_SIESA_CATALOGS.get(doctype) or []
	for code, description in rows:
		_upsert_reference_row(doctype, code, description)


def ensure_social_security_reference_catalogs():
	for doctype, rows in SOCIAL_SECURITY_REFERENCE_CATALOGS.items():
		for code, description in rows:
			_upsert_reference_row(doctype, code, description)


def ensure_official_ccf_catalog(strict_disable_others=True):
	"""Normaliza catálogo CCF a códigos oficiales y opcionalmente deshabilita el resto."""
	doctype = "Entidad CCF Siesa"
	ensure_reference_catalog(doctype)

	if not strict_disable_others:
		return

	official_codes = {code for code, _ in OFFICIAL_SIESA_CATALOGS.get(doctype, [])}
	rows = frappe.get_all(doctype, fields=["name", "code", "enabled"])
	for row in rows:
		code = str(row.get("code") or "").strip()
		if code in official_codes:
			continue
		if int(row.get("enabled") or 0) == 1:
			frappe.db.set_value(doctype, row["name"], "enabled", 0, update_modified=False)


def _normalize_text(value):
	return " ".join(str(value or "").strip().lower().split())


def _repoint_to_official_catalog(doctype, references, fallback_code):
	rows = frappe.get_all(doctype, fields=["name", "code", "description", "enabled"])
	official_codes = {code for code, _ in OFFICIAL_SIESA_CATALOGS.get(doctype, [])}

	by_name = {str(r.get("name") or ""): r for r in rows}
	by_name_official = {
		str(r.get("name") or ""): r
		for r in rows
		if str(r.get("code") or "") in official_codes
	}
	by_code = {str(r.get("code") or ""): r for r in rows if str(r.get("code") or "") in official_codes}
	by_desc = {
		_normalize_text(r.get("description")): r
		for r in rows
		if str(r.get("code") or "") in official_codes and str(r.get("description") or "").strip()
	}
	fallback = by_code.get(str(fallback_code))

	for ref_doctype, ref_field in references:
		if not frappe.db.exists("DocType", ref_doctype):
			continue
		for ref in frappe.get_all(ref_doctype, fields=["name", ref_field], filters={ref_field: ["!=", ""]}):
			current_value = str(ref.get(ref_field) or "").strip()
			if not current_value:
				continue

			target = by_name_official.get(current_value) or by_code.get(current_value) or by_desc.get(_normalize_text(current_value))
			if not target and current_value in by_name:
				legacy = by_name[current_value]
				legacy_code = str(legacy.get("code") or "").strip()
				legacy_desc = _normalize_text(legacy.get("description"))
				target = by_code.get(legacy_code) or by_desc.get(legacy_desc)
			if not target:
				target = fallback

			if target and target.get("name") and target.get("name") != current_value:
				frappe.db.set_value(ref_doctype, ref.get("name"), ref_field, target.get("name"), update_modified=False)


def ensure_official_unidad_negocio_catalog(strict_disable_others=True):
	doctype = "Unidad Negocio Siesa"
	ensure_reference_catalog(doctype)
	_repoint_to_official_catalog(
		doctype,
		[
			("Contrato", "unidad_negocio_siesa"),
			("Datos Contratacion", "unidad_negocio_siesa"),
		],
		fallback_code="999",
	)

	if not strict_disable_others:
		return

	official_codes = {code for code, _ in OFFICIAL_SIESA_CATALOGS.get(doctype, [])}
	for row in frappe.get_all(doctype, fields=["name", "code", "enabled"]):
		code = str(row.get("code") or "").strip()
		if code not in official_codes and int(row.get("enabled") or 0) == 1:
			frappe.db.set_value(doctype, row["name"], "enabled", 0, update_modified=False)


def ensure_official_centro_trabajo_catalog(strict_disable_others=True):
	doctype = "Centro Trabajo Siesa"
	ensure_reference_catalog(doctype)
	_repoint_to_official_catalog(
		doctype,
		[
			("Contrato", "centro_trabajo_siesa"),
			("Datos Contratacion", "centro_trabajo_siesa"),
		],
		fallback_code="001",
	)

	if not strict_disable_others:
		return

	official_codes = {code for code, _ in OFFICIAL_SIESA_CATALOGS.get(doctype, [])}
	for row in frappe.get_all(doctype, fields=["name", "code", "enabled"]):
		code = str(row.get("code") or "").strip()
		if code not in official_codes and int(row.get("enabled") or 0) == 1:
			frappe.db.set_value(doctype, row["name"], "enabled", 0, update_modified=False)


def ensure_official_nivel_educativo_catalog(strict_disable_others=True):
	doctype = "Nivel Educativo Siesa"
	ensure_reference_catalog(doctype)
	_repoint_to_official_catalog(
		doctype,
		[
			("Candidato", "nivel_educativo_siesa"),
			("Datos Contratacion", "nivel_educativo_siesa"),
		],
		fallback_code="12",
	)

	if not strict_disable_others:
		return

	official_codes = {code for code, _ in OFFICIAL_SIESA_CATALOGS.get(doctype, [])}
	for row in frappe.get_all(doctype, fields=["name", "code", "enabled"]):
		code = str(row.get("code") or "").strip()
		if code not in official_codes and int(row.get("enabled") or 0) == 1:
			frappe.db.set_value(doctype, row["name"], "enabled", 0, update_modified=False)


def ensure_banco_reference_catalog():
	for bank_name, bank_code in OFFICIAL_BANCO_BANCOLOMBIA_CODES:
		code = str(bank_code or "").strip()
		last_two = code[-2:] if len(code) >= 2 else ""

		name = (
			frappe.db.get_value("Banco Siesa", {"description": bank_name}, "name")
			or frappe.db.get_value("Banco Siesa", {"code": code}, "name")
			or frappe.db.get_value("Banco Siesa", {"code": bank_name}, "name")
		)

		if name:
			doc = frappe.get_doc("Banco Siesa", name)
			doc.code = code
			doc.description = bank_name
			doc.codigo_bancolombia = code
			doc.ultimos_dos_digitos = last_two
			doc.enabled = 1
			doc.save(ignore_permissions=True)
			continue

		doc = frappe.get_doc(
			{
				"doctype": "Banco Siesa",
				"code": code,
				"description": bank_name,
				"codigo_bancolombia": code,
				"ultimos_dos_digitos": last_two,
				"enabled": 1,
			}
		)
		doc.insert(ignore_permissions=True)


def _repoint_link_values(doctype, fieldname, old_values, new_value):
	for old_value in {str(v).strip() for v in old_values if str(v or "").strip()}:
		rows = frappe.get_all(doctype, filters={fieldname: old_value}, fields=["name"])
		for row in rows:
			frappe.db.set_value(doctype, row.name, fieldname, new_value, update_modified=False)


def ensure_official_cargo_matrix():
	for raw_code, title in OFFICIAL_CARGOS:
		code = normalize_code_for_doctype("Cargo", raw_code)
		title = str(title or "").strip()
		if not code or not title:
			continue

		canonical = frappe.db.get_value("Cargo", {"codigo": code}, "name")
		if canonical:
			doc = frappe.get_doc("Cargo", canonical)
			if (doc.nombre or "") != title or int(doc.activo or 0) != 1:
				doc.nombre = title
				doc.activo = 1
				doc.save(ignore_permissions=True)
			continue

		legacy = frappe.db.get_value("Cargo", {"nombre": title}, "name")
		if legacy:
			new_doc = frappe.get_doc({"doctype": "Cargo", "codigo": code, "nombre": title, "activo": 1})
			new_doc.insert(ignore_permissions=True)

			legacy_doc = frappe.get_doc("Cargo", legacy)
			_repoint_link_values("Candidato", "cargo_postulado", [legacy_doc.name, legacy_doc.codigo, legacy_doc.nombre], new_doc.name)
			_repoint_link_values("Datos Contratacion", "cargo_postulado", [legacy_doc.name, legacy_doc.codigo, legacy_doc.nombre], new_doc.name)
			_repoint_link_values("Contrato", "cargo", [legacy_doc.name, legacy_doc.codigo, legacy_doc.nombre], new_doc.name)

			legacy_doc.activo = 0
			legacy_doc.descripcion = (legacy_doc.descripcion or "") + "\nMigrado a código SIESA oficial: " + code
			legacy_doc.save(ignore_permissions=True)
			continue

		frappe.get_doc({"doctype": "Cargo", "codigo": code, "nombre": title, "activo": 1}).insert(ignore_permissions=True)


def sync_reference_masters():
	for doctype in OFFICIAL_SIESA_CATALOGS:
		ensure_reference_catalog(doctype)
	ensure_social_security_reference_catalogs()
	ensure_official_ccf_catalog(strict_disable_others=True)
	ensure_official_unidad_negocio_catalog(strict_disable_others=True)
	ensure_official_centro_trabajo_catalog(strict_disable_others=True)
	ensure_official_nivel_educativo_catalog(strict_disable_others=True)
	ensure_banco_reference_catalog()
	ensure_official_cargo_matrix()
	frappe.db.commit()
