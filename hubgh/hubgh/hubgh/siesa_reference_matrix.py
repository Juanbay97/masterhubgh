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
		("890900842", "CCF COMFENALCO ANTIOQUIA"),
		("890102002", "CCF COMBARRANQUILLA"),
		("860066942", "CCF COMPENSAR"),
		("890480023", "CCF COMFENALCO CARTAGENA"),
		("999999999", "SIN CAJA"),
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
		("02", "BÁSICA PRIMARIA (1° - 5°)"),
		("03", "BÁSICA SECUNDARIA (6° - 9°)"),
		("04", "MEDIA (10° - 13°)"),
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
		("830113831", "ALIANSALUD EPS"),
		("800130907", "EPS SALUD TOTAL"),
		("800251440", "SANITAS EPS"),
		("860066942", "COMPENSAR EPS"),
		("800088702", "EPS SURA"),
		("830003564", "FAMISANAR EPS"),
		("900604350", "ALIANZA MEDELLIN ANTIOQUIA EPS SAS"),
		("900298372", "RECAUDO SGP CAPITAL SALUD"),
		("806008394", "EPS-S MUTUAL SER"),
		("800249241", "EPS COOSALUD"),
		("804002105", "Cooperativa de Salud Comunitaria Comparta"),
		("860045904", "Comfacundi - CCF de Cundinamarca"),
		("900462447", "Fondo de Solidaridad y Garantia Fosyga"),
		("818000140", "Asociacion Mutual Barrios Unidos de Quibdo E.S.S. AMBUQ"),
		("8300396705", "SANIDAD MILITAR"),
		("901093846", "ECOOPSOS EPS SAS"),
		("892115006", "COMFAMILIAR GUAJIRA"),
		("824001398", "ASOCIACION DE CABILDOS INDIGENAS DEL CESAR Y GUAJIRA DUSAKA"),
		("805001157", "ENTIDAD PROMOTORA DE SALUD SERVICIO OCCIDENTAL DE SALUD S.A."),
		("800249241-0", "EPS COOSALUD MOVIL"),
		("890500675", "CAJA DE COMPENSACION DEL ORIENTE COLOMBIANO COMFAORIENTE"),
		("837000084", "ENTIDAD PROMOTORA DE SALUD MALLAMAS EPSI"),
		("899999107", "EPS-S CONVIDA"),
		("901097473", "MEDIMAS EPS"),
		("830009783", "CRUZ BLANCA EPS"),
		("805000427", "COOMEVA EPS"),
		("891080005", "EPS-S COMFACOR"),
		("900156264", "NUEVA EPS"),
		("900156264-2", "NUEVA EPS S.A. MOVILIDAD"),
		("901543761", "EPS FAMILIAR DE COLOMBIA S A S"),
		("901037916", "Fosyga Regimen de Excepcion"),
		("890102044", "EPS CAJACOPI"),
		("900226715", "COOSALUD ENTIDAD PROMOTORA DE SALUD S A"),
	],
	"Entidad AFP Siesa": [
		("800229739", "AFP PROTECCION (ING + PROTECCION)"),
		("800224808", "AFP PORVENIR"),
		("800227940", "AFP COLFONDOS"),
		("900336004", "AFP COLPENSIONES"),
		("999999999", "SIN AFP"),
		("8001485142", "Skandia Administradora De Fondos De Pensiones Y Cesantias"),
	],
	"Entidad Cesantias Siesa": [
		("999999999", "SIN FONDO DE CESANTIAS"),
		("800170494", "PROTECCION"),
		("899999284", "FNA"),
		("800198644", "COLFONDOS"),
		("800170043", "PORVENIR"),
		("8001485142", "Skandia Administradora De Fondos De Pensiones Y Cesantias"),
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


# Catálogo combinado oficial: cada banco con su nombre canonical (matching plantilla SIESA),
# código ACH y código Bancolombia. None cuando el banco no aparece en alguna de las dos tablas.
# Tupla: (description_canonical, codigo_ach, codigo_bancolombia)
OFFICIAL_BANCO_CATALOG = [
	("BANCAMIA S.A", "1059", "1059"),
	("BANCO AGRARIO", "1040", "1040"),
	("BANCO AV VILLAS", "1052", "6013677"),
	("BANCO BTG PACTUAL", "1805", "1805"),
	("BANCO CAJA SOCIAL BCSC SA", "1032", "5600829"),
	("BANCO CONTACTAR S.A.", None, "1819"),
	("BANCO COOPERATIVO COOPCENTRAL", "1066", "1066"),
	("BANCO CREDIFINANCIERA SA.", "1558", "1558"),
	("BANCO DAVIVIENDA SA", "1051", "5895142"),
	("BANCO DE BOGOTA", "1001", "5600010"),
	("BANCO DE OCCIDENTE", "1023", "5600230"),
	("BANCO FALABELLA S.A.", "1062", "1062"),
	("BANCO FINANDINA S.A.", "1063", "1063"),
	("BANCO GNB SUDAMERIS", "1012", "5600120"),
	("BANCO J.P. MORGAN COLOMBIA S.A", "1071", "1071"),
	("BANCO MUNDO MUJER", "1047", "1047"),
	("BANCO NU", "1809", "1809"),
	("BANCO PICHINCHA", "1060", "1060"),
	("BANCO POPULAR", "1002", "5600023"),
	("BANCO SANTANDER DE NEGOCIOS COLOMBIA S.A", "1065", "1065"),
	("BANCO SERFINANZA S.A", "1069", "1069"),
	("BANCO UNION S.A", None, "1303"),
	("BANCO W S.A", "1053", "1053"),
	("BANCOLDEX S.A.", "1031", "1031"),
	("BANCOLOMBIA", "1007", "5600078"),
	("BANCOOMEVA", "1061", "1061"),
	("BBVA COLOMBIA", "1013", "5600133"),
	("BOLD CF", None, "1808"),
	("CITIBANK", "1009", "5600094"),
	("COINK", "1812", "1812"),
	("COLTEFINANCIERA S.A", "1370", "1370"),
	("CONFIAR COOPERATIVA FINANCIERA", "1292", "1292"),
	("COOPERATIVA FINANCIERA DE ANTIOQUIA", "1283", "1283"),
	("COOTRAFA COOPERATIVA FINANCIERA", "1289", "1289"),
	("DAVIPLATA", "1551", "1551"),
	("DING TECNIPAGOS SA", "1802", "1802"),
	("FINANCIERA JURISCOOP S.A. COMPAÑIA DE FINANCIAMIENTO", "1121", "1121"),
	("GLOBAL66", None, "1814"),
	("IRIS", "1637", "1637"),
	("ITAU", "1014", "5600146"),
	("ITAU antes Corpbanca", "1006", "5600065"),
	("JFK COOPERATIVA FINANCIERA", "1286", "1286"),
	("LULO BANK S.A.", "1070", "1070"),
	("MIBANCO S.A.", "1067", "1067"),
	("MOVII", "1801", "1801"),
	("NEQUI", "1507", "1507"),
	("PIBANK", "1560", "1560"),
	("POWWI", "1803", "1803"),
	("RAPPIPAY", "1811", "1811"),
	("RIA MONEY TRANSFER COLOMBIA S.", None, "1817"),
	("SCOTIABANK COLPATRIA S.A", "1019", "5600191"),
	("UALA", "1804", "1804"),
	# Solo ACH (no en Bancolombia)
	("ASOPAGOS S.A.S", "1086", None),
	("COOFINEP COOPERATIVA FINANCIERA", "1291", None),
	("SANTANDER CONSUMER", "1813", None),
]


# Aliases: nombres alternativos del mismo banco que aparecen en datos viejos
# o en el catálogo Bancolombia con texto truncado/diferente.
BANCO_NAME_ALIASES = {
	"BANCO DE LAS MICROFINANZAS - BANCAMIA S.A.": "BANCAMIA S.A",
	"BAN100 S.A": "BANCO CREDIFINANCIERA SA.",
	"BANCO W": "BANCO W S.A",
	"BANCO SANTANDER DE NEGOCIOS CO": "BANCO SANTANDER DE NEGOCIOS COLOMBIA S.A",
	"COOPERATIVA FINANCIERA DE ANTI": "COOPERATIVA FINANCIERA DE ANTIOQUIA",
	"COOTRAFA COOPERATIVA FINANCIER": "COOTRAFA COOPERATIVA FINANCIERA",
	"FINANCIERA JURISCOOP S.A. COMP": "FINANCIERA JURISCOOP S.A. COMPAÑIA DE FINANCIAMIENTO",
	"BANCO J.P. MORGAN COLOMBIA S.A.": "BANCO J.P. MORGAN COLOMBIA S.A",
	"NU": "BANCO NU",
	"Ualá": "UALA",
	"BANCO BBVA": "BBVA COLOMBIA",
}


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


def _get_official_codes_for_doctype(doctype):
	rows = OFFICIAL_SIESA_CATALOGS.get(doctype) or SOCIAL_SECURITY_REFERENCE_CATALOGS.get(doctype) or []
	return {code for code, _ in rows}


def ensure_catalog_for_doctype(doctype):
	rows = OFFICIAL_SIESA_CATALOGS.get(doctype) or SOCIAL_SECURITY_REFERENCE_CATALOGS.get(doctype) or []
	for code, description in rows:
		_upsert_reference_row(doctype, code, description)


def ensure_official_ccf_catalog(strict_disable_others=True):
	"""Normaliza catálogo CCF a códigos oficiales y opcionalmente deshabilita el resto."""
	doctype = "Entidad CCF Siesa"
	ensure_reference_catalog(doctype)
	_repoint_to_official_catalog(
		doctype,
		[
			("Contrato", "entidad_ccf_siesa"),
			("Candidato", "ccf_siesa"),
			("Datos Contratacion", "ccf_siesa"),
			("Ficha Empleado", "ccf_siesa"),
		],
		fallback_code="999999999",
	)

	if not strict_disable_others:
		return

	official_codes = _get_official_codes_for_doctype(doctype)
	rows = frappe.get_all(doctype, fields=["name", "code", "enabled"])
	for row in rows:
		code = str(row.get("code") or "").strip()
		if code in official_codes:
			continue
		if int(row.get("enabled") or 0) == 1:
			frappe.db.set_value(doctype, row["name"], "enabled", 0, update_modified=False)


def ensure_official_eps_catalog(strict_disable_others=True):
	doctype = "Entidad EPS Siesa"
	ensure_catalog_for_doctype(doctype)
	_repoint_to_official_catalog(
		doctype,
		[
			("Contrato", "entidad_eps_siesa"),
			("Candidato", "eps_siesa"),
			("Datos Contratacion", "eps_siesa"),
			("Ficha Empleado", "eps_siesa"),
		],
		fallback_code=None,
	)

	if not strict_disable_others:
		return

	official_codes = _get_official_codes_for_doctype(doctype)
	for row in frappe.get_all(doctype, fields=["name", "code", "enabled"]):
		code = str(row.get("code") or "").strip()
		if code not in official_codes and int(row.get("enabled") or 0) == 1:
			frappe.db.set_value(doctype, row["name"], "enabled", 0, update_modified=False)


def ensure_official_afp_catalog(strict_disable_others=True):
	doctype = "Entidad AFP Siesa"
	ensure_catalog_for_doctype(doctype)
	_repoint_to_official_catalog(
		doctype,
		[
			("Contrato", "entidad_afp_siesa"),
			("Candidato", "afp_siesa"),
			("Datos Contratacion", "afp_siesa"),
			("Ficha Empleado", "afp_siesa"),
		],
		fallback_code="999999999",
	)

	if not strict_disable_others:
		return

	official_codes = _get_official_codes_for_doctype(doctype)
	for row in frappe.get_all(doctype, fields=["name", "code", "enabled"]):
		code = str(row.get("code") or "").strip()
		if code not in official_codes and int(row.get("enabled") or 0) == 1:
			frappe.db.set_value(doctype, row["name"], "enabled", 0, update_modified=False)


def ensure_official_cesantias_catalog(strict_disable_others=True):
	doctype = "Entidad Cesantias Siesa"
	ensure_catalog_for_doctype(doctype)
	_repoint_to_official_catalog(
		doctype,
		[
			("Contrato", "entidad_cesantias_siesa"),
			("Candidato", "cesantias_siesa"),
			("Datos Contratacion", "cesantias_siesa"),
			("Ficha Empleado", "cesantias_siesa"),
		],
		fallback_code="999999999",
	)

	if not strict_disable_others:
		return

	official_codes = _get_official_codes_for_doctype(doctype)
	for row in frappe.get_all(doctype, fields=["name", "code", "enabled"]):
		code = str(row.get("code") or "").strip()
		if code not in official_codes and int(row.get("enabled") or 0) == 1:
			frappe.db.set_value(doctype, row["name"], "enabled", 0, update_modified=False)


def _normalize_text(value):
	return " ".join(str(value or "").strip().lower().split())


def _repoint_to_official_catalog(doctype, references, fallback_code):
	rows = frappe.get_all(doctype, fields=["name", "code", "description", "enabled"])
	official_codes = _get_official_codes_for_doctype(doctype)

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
	"""Pobla Banco Siesa con códigos ACH + Bancolombia oficiales.

	Para cada banco del catálogo combinado:
	- code y codigo_ach = código ACH (lo que SIESA quiere para ID BANCO EMPLEADO)
	- codigo_bancolombia = código bancolombia interno (para columna NOTAS)
	- ultimos_dos_digitos = últimos 2 del ACH
	- description = nombre canonical

	Los registros existentes con descripción matcheable se actualizan in-place;
	los Link fields se repuntan vía rename si el code cambia.
	"""
	for canonical_name, codigo_ach, codigo_bancolombia in OFFICIAL_BANCO_CATALOG:
		ach = _str(codigo_ach)
		bancolombia = _str(codigo_bancolombia)
		last_two = ach[-2:] if len(ach) >= 2 else ""

		# code en Banco Siesa = ACH cuando exista; si no, bancolombia (fallback).
		target_code = ach or bancolombia
		if not target_code or not canonical_name:
			continue

		# Buscar registro existente por description (canonical o alias) o por
		# cualquier code/codigo_ach/codigo_bancolombia conocido.
		candidate_descriptions = [canonical_name] + [
			alias for alias, official in BANCO_NAME_ALIASES.items() if official == canonical_name
		]
		name = None
		for desc in candidate_descriptions:
			name = frappe.db.get_value("Banco Siesa", {"description": desc}, "name")
			if name:
				break
		if not name:
			for code_candidate in (ach, bancolombia):
				if code_candidate:
					name = frappe.db.get_value("Banco Siesa", {"code": code_candidate}, "name")
					if name:
						break
		if not name and ach:
			name = frappe.db.get_value("Banco Siesa", {"codigo_ach": ach}, "name")

		updates = {
			"description": canonical_name,
			"codigo_ach": ach,
			"codigo_bancolombia": bancolombia,
			"ultimos_dos_digitos": last_two,
			"enabled": 1,
		}

		if name:
			# Si el code actual difiere del target, renombrar el doc — esto
			# repunta automáticamente todos los Link fields que apuntan al name.
			if name != target_code:
				try:
					frappe.rename_doc("Banco Siesa", name, target_code, force=True, merge=False)
					name = target_code
				except Exception:
					frappe.logger("hubgh.siesa_export").warning(
						"No se pudo renombrar Banco Siesa", extra={"from": name, "to": target_code}
					)
			updates["code"] = target_code
			frappe.db.set_value("Banco Siesa", name, updates, update_modified=False)
			continue

		doc = frappe.get_doc(
			dict(doctype="Banco Siesa", code=target_code, **updates)
		)
		doc.insert(ignore_permissions=True)


def _str(value):
	return "" if value is None else str(value).strip()


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
