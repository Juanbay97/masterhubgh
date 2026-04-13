import io
import json
import unicodedata
from difflib import get_close_matches
from datetime import datetime

import frappe
from frappe.utils import getdate

from hubgh.hubgh.contratacion_service import get_or_create_affiliation, validar_candidato_para_siesa
from hubgh.hubgh.siesa_reference_matrix import normalize_code_for_doctype


EMPLOYEE_EXPORT_HEADERS = [
	"ID DEL TERCERO (Obligatorio)",
	"ID DEL TIPO DE IDENTIFICACIÓN   C: CEDULA E: EXTRANJERIA P: PASAPORTE X:DOCUMENTO EXTRANJERO T: TARJETA DE IDENTIDAD(Obligatorio)",
	"APELLIDOS 1 (Obligatorio)",
	"APELLIDOS 2 (Obligatorio)",
	"NOMBRES (Obligatorio)",
	"ID DE LA SUCURSAL DEL CLIENTE (No obligatorio)",
	"ID DE LA SUCURSAL DEL PROVEEDOR (No obligatorio)",
	"ID DE LA COMPAÑIA (Obligatorio)",
	"FECHA INGRESO (YYYYMMDD, Obligatorio)",
	"FECHA NACIMIENTO (YYYYMMDD, Obligatorio)",
	"ID PAIS NACIMIENTO (Obligatorio)",
	"ID DEPTO NACIMIENTO (Obligatorio)",
	"ID CIUDAD NACIMIENTO (Obligatorio)",
	"FECHA EXPEDICION IDENTIFICACION (YYYYMMDD, Obligatorio)",
	"ID PAIS EXPEDICION IDENTIFICACION (Obligatorio)",
	"ID DEPTO EXPEDICION IDENTIFICACION (Obligatorio)",
	"ID CIUDAD EXPEDICION IDENTIFICACION (Obligatorio)",
	"ID NIVEL EDUCATIVO (Obligatorio)",
	"INDICADOR GENERO (Obligatorio, (0=M,1=F))",
	"INDICADOR ESTADO CIVIL (Obligatorio, (0=Ninguno, 1=Soltero, 2=Casado, 3=Viudo, 4=Divorciado, 5=Unión libre))",
	"INDICADOR EXTRANJERO (Obligatorio, (0=No, 1=Si))",
	"RAZON SOCIAL DEL CONTACTO (No obligatorio)",
	"DIRECCION 1 (No obligatorio)",
	"DIRECCION 2 (No obligatorio)",
	"DIRECCION 3 (No obligatorio  )",
	"ID PAIS DEL CONTACTO (No obligatorio)",
	"ID DEPTO DEL CONTACTO (No obligatorio)",
	"ID CIUDAD DEL CONTACTO (No obligatorio)",
	"ID BARRIO DEL CONTACTO (No obligatorio)",
	"TELEFONO DEL CONTACTO (Obligatorio)",
	"FAX DEL CONTACTO (No obligatorio   )",
	"CODIGO POSTAL DEL CONTACTO (No obligatorio)",
	"CORREO ELECTRONICO DEL CONTACTO (No obligatorio)",
	"INDICADOR SI ES EMPLEADO (Art. 329, Obligatorio, (0=No, 1=Si))",
	"INDICADOR SI ES DECLARANTE (Art. 329, Obligatorio, (0=No, 1=Si))",
	"NOTAS DEL CONTACTO (No obligatorio)",
	"NUMERO PASAPORTE (No Obligatorio - Alfanumérico maximo 20 caracteres)",
	"ID PAGO EXTRANJERO",
]


CONTRACT_EXPORT_HEADERS = [
	"ID CIA (Obligatorio)",
	"ID TERCERO (Obligatorio)",
	"NRO DEL CONTRATO   (Obligatorio)",
	"ID CO   (Obligatorio)",
	"ID PRORROGA   (No obligatorio)",
	"ID DEL BANCO   (No obligatorio)",
	"ID TIPO DE COTIZANTE   (Obligatorio)",
	"IND COMPENSACION FLEXIBLE   (No obligatorio,_x000D_\n(1 =activo, 0= inactivo),_x000D_\nVacío asume inactivo)",
	"ID PROYECTO   (Obligatorio)",
	"ID UNIDAD DE NEGOCIO   (Obligatorio)",
	"ID SUCURSAL AUTOLIQUIDACION   (Obligatorio)",
	"ID MOTIVO DE RETIRO   (No obligatorio   )",
	"ID TURNO   (No obligatorio)",
	"ID GRUPO DE EMPLEADOS   (Obligatorio)",
	"ID CCOSTO   (Obligatorio)",
	"ID CENTRO DE TRABAJO   (Obligatorio)",
	"ID TIPO DE NOMINA   (Obligatorio)",
	"ID TIEMPO BASICO   (No obligatorio)",
	"ID ENTIDAD PENSION   (No obligatorio)",
	"ID ENTIDAD EPS   (No obligatorio)",
	"ID ENTIDAD CESANTIAS   (No obligatorio)",
	"ID ENTIDAD CAJA COMPENSACION   (No obligatorio)",
	"ID ENTIDAD ARL   (No obligatorio)",
	"ID ENTIDAD SENA   (No obligatorio)",
	"ID ENTIDAD ICBF   (No obligatorio)",
	"FECHA DE INGRESO   (YYYYMMDD, Obligatorio)",
	"FECHA DE INGRESO LEY 50   (YYYYMMDD, Obligatorio)",
	"FECHA DE RETIRO   (YYYYMMDD, No obligatorio,_x000D_\nDebe ser vacío para contratos activos)",
	"FECHA DE CONTRATO HASTA   (YYYYMMDD, No obligatorio,_x000D_\nVacío para contratos a termino indefinido)",
	"FECHA DE PRIMA HASTA   (YYYYMMDD, Obligatorio  )",
	"FECHA DE VACACIONES HASTA   (_x000D_\nYYYYMMDD, Obligatorio,_x000D_\nse debe diligenciar con la _x000D_\nfecha de inicio del contrato)",
	"FECHA DE ULTIMO AUMENTO   (YYYYMMDD, Obligatorio  )",
	"FECHA DE ULTIMAS VACACIONES   (_x000D_\nYYYYMMDD, Obligatorio,_x000D_\nse debe diligenciar con _x000D_\nla fecha de inicio del contrato)",
	"FECHA DE ULTIMA PENSION   (YYYYMMDD, Obligatorio  )",
	"FECHA DE ULTIMA CESANTIAS   (YYYYMMDD, No obligatorio)",
	"SALARIO   (Puede recibir dos decimales con separador punto (.), Obligatorio  )",
	"SALARIO ANTERIOR   (Puede recibir dos decimales con separador punto (.), Obligatorio  )",
	"VALOR DEDUCIBLE RETEFUENTE   (Puede recibir dos decimales con separador punto (.), Obligatorio  )",
	"VALOR CESANTIAS CONGELADAS   (Puede recibir dos decimales con separador punto (.), Obligatorio  )",
	"VALOR CESANTIAS RETIRADAS   (Puede recibir dos decimales con separador punto (.), Obligatorio  )",
	"VALOR OTROS SALUD   (Puede recibir dos decimales con separador punto (.), Obligatorio  ) PREPAGADA",
	"VALOR DE SALUD OBLIGATORIO   (Puede recibir seis decimales con separador punto (.), Obligatorio  )",
	"CANTIDAD HORAS TRABAJADAS AL MES   (Puede recibir seis decimales con separador punto (.), Obligatorio  )",
	"PORCENTAJE DE RETEFUENTE   (Puede recibir seis decimales con separador punto (.), Obligatorio  )",
	"PORCENTAJE DE TIEMPO LABORADO   (Puede recibir seis decimales con separador punto (.), Obligatorio  )",
	"DIAS PAGADOS DE VACACIONES   (Puede recibir seis decimales con separador punto (.), Obligatorio  )",
	"CONSECUTIVO DEL CONTRATO   (No obligatorio)",
	"NUMERO DE PERSONAS A CARGO   (Obligatorio)",
	"CUENTA BANCARIA   (Obligatorio)",
	"IND FORMA PAGO   (Obligatorio,\n(0=Efectivo, \n1=Cheque,\n2=Consignación))",
	"IND REGIMEN LABORAL   (Obligatorio,\n(0=Antes de Ley 50,\n1=Ley 50,\n2=Jubilado, \n3=Otros))",
	"IND AUXILIO TRANSPORTE   (Obligatorio,\n(0=No,\n1= En dinero,\n2=En especie,\n3=Menor a 2 SMLMV))",
	"IND PROCEDIMIENTO RETENCION   (Obligatorio,_x000D_\n(1=Valor Tabla,_x000D_\n2=Porcentaje Fijo))",
	"IND PACTO COLECTIVO   (Obligatorio, (0=No, 1=Si))",
	"IND DE SUBSIDIO FAMILIAR   (Obligatorio, (0=No, 1=Si))",
	"IND DE POLIZA HUC   (Obligatorio, (0=No, 1=Si))",
	"IND DEDUCIBLE   (_x000D_\nObligatorio,_x000D_\n(0=No,_x000D_\n1=Salud - Educación,_x000D_\n2=Interes Vivienda))",
	"IND OTROS SALUD   (_x000D_\nObligatorio,_x000D_\n(0=Ninguno,_x000D_\n1 = U.P.C,  _x000D_\n2=Prepagada))",
	"IND ETIQUETA   (Obligatorio, (0=No, 1=Si))",
	"IND SALARIO INTEGRAL   (Obligatorio, (0=No, 1=Si))",
	"IND LEY 789   (Obligatorio, (0=No, 1=Si))",
	"IND SUBTIPO COTIZANTE   (Obligatorio, \n(0=No aplica, \n1=Dependiente pensionado por vejez activo,\n2=Independiente pensionado por Vejez Activo, \n3=Cotizante no Obligado a Cotizar a Pensiones por Edad, \n4=Cotizante con Requisitos Cumplidos para Pensión,\n5=Cotizante con Indemnización Sustitutiva  o devolución de saldos, \n6=Cotizante a Régimen Exceptuado Pensión o Entidad Autorizada))",
	"IND EXTRANJERO PENSION   (Obligatorio, (0=No, 1=Si))",
	"IND DE CONTINUIDAD   (Obligatorio, (0=No, 1=Si)) DOCENTES",
	"IND TIPO DE CUENTA   (Obligatorio,\n(1=Ahorro, \n2=Corriente, \n3=Tarjeta Prepago))",
	"IND CLASE DE CONTRATO   (Obligatorio,\n(0=Normal,\n1=Labor contratada,\n2 =Docentes))",
	"IND TERMINO CONTRATO   (Obligatorio, (0=No, 1=Si))",
	"IND ESTADO   (Obligatorio,\n(0=Pendiente,\n1=Activo(no permitido), \n2=Retirado,\n3=Cancelado,\n4=Liquidado,\n5=transitoriamente retirado))",
	"ID CARGO   (Obligatorio)",
	"VALOR DE SALUD PREPAGADA   (Obligatorio)",
	"VALOR DEPENDIENTES   (Obligatorio)",
	"IND CONSOLIDA RETENCION   (Obligatorio,(0=No, 1=Si))",
	"NOTAS   (No obligatorio)",
	"ADICIONAL NUMERICO 1   (No obligatorio,_x000D_\nValor máximo hasta 2147483647 )",
	"ADICIONAL NUMERICO 2   (No obligatorio,_x000D_\nValor máximo hasta 2147483647 )",
	"ADICIONAL NUMERICO 3   (No obligatorio,_x000D_\nValor máximo hasta 2147483647 )",
	"ADICIONAL NUMERICO 4   (No obligatorio,_x000D_\nValor máximo hasta 2147483647 )",
	"ADICIONAL ALFANUMERICO 1   (No obligatorio)",
	"ADICIONAL ALFANUMERICO 2   (No obligatorio)",
	"ADICIONAL ALFANUMERICO 3   (No obligatorio)",
	"ADICIONAL ALFANUMERICO 4   (No obligatorio)",
	"FECHA SUSTITUCION   (YYYYMMDD, No obligatorio)",
	"IND BASE SALARIAL AL 100% CF   (No obligatorio,_x000D_\n(0=No,_x000D_\n1=Si),_x000D_\nVacío asume sueldo basico como _x000D_\nneto en compensación flexible)",
	"TIPO DE SALARIO (No obligatorio, (vacío o 0=Fijo, 1=Variable))",
	"ID BANCO EMPLEADO (No Obligatorio - Alfanumérico maximo 10 caracteres)",
]


def _xlsx_library():
	try:
		import openpyxl  # type: ignore

		return openpyxl
	except Exception:
		frappe.throw("La librería openpyxl no está instalada en el entorno.")


def _safe_ymd(value):
	if not value:
		return ""
	if hasattr(value, "strftime"):
		return value.strftime("%Y%m%d")
	try:
		return getdate(value).strftime("%Y%m%d")
	except Exception:
		return str(value)


def _is_blank(value):
	return value is None or (isinstance(value, str) and not value.strip())


def _first(*values):
	for value in values:
		if not _is_blank(value):
			return value
	return None


def _str(value):
	if value is None:
		return ""
	return str(value).strip()


def _digits_only(value):
	return "".join(ch for ch in _str(value) if ch.isdigit())


def _last_two_digits(value):
	digits = _digits_only(value)
	return digits[-2:] if len(digits) >= 2 else ""


def _normalize_catalog_lookup_key(value):
	text = unicodedata.normalize("NFKD", _str(value)).encode("ascii", "ignore").decode("ascii")
	text = text.lower().replace("_", " ").replace("-", " ")
	stopwords = {
		"siesa",
		"entidad",
		"eps",
		"afp",
		"afc",
		"ces",
		"cesantia",
		"cesantias",
		"fondo",
	}
	tokens = [token for token in text.split() if token and token not in stopwords]
	return "".join(tokens)


def _resolve_catalog_code_by_alias(doctype, raw):
	normalized_raw = _normalize_catalog_lookup_key(raw)
	if not normalized_raw:
		return ""

	rows = frappe.get_all(doctype, fields=["name", "code", "description"], ignore_permissions=True)
	if not rows:
		return ""

	alias_to_code = {}
	for row in rows:
		code = normalize_code_for_doctype(doctype, _str(getattr(row, "code", None) or row.get("code") or getattr(row, "name", None) or row.get("name")))
		for candidate in (
			getattr(row, "name", None) or row.get("name"),
			getattr(row, "code", None) or row.get("code"),
			getattr(row, "description", None) or row.get("description"),
		):
			alias = _normalize_catalog_lookup_key(candidate)
			if alias:
				alias_to_code.setdefault(alias, code)

	exact = alias_to_code.get(normalized_raw)
	if exact:
		return exact

	closest = get_close_matches(normalized_raw, list(alias_to_code.keys()), n=1, cutoff=0.75)
	if closest:
		return alias_to_code.get(closest[0], "")

	return ""


def _get_banco_siesa_snapshot(bank_name):
	if _is_blank(bank_name) or not frappe.db.exists("Banco Siesa", bank_name):
		return {}
	return (
		frappe.db.get_value(
			"Banco Siesa",
			bank_name,
			["name", "code", "description", "ultimos_dos_digitos", "codigo_bancolombia"],
			as_dict=True,
		)
		or {}
	)


def _normalize_banco_siesa_record(bank_name):
	"""Normaliza registros mal cargados de Banco Siesa (code/description invertidos)."""
	snapshot = _get_banco_siesa_snapshot(bank_name)
	if not snapshot:
		return snapshot

	code = _str(snapshot.get("code"))
	description = _str(snapshot.get("description"))
	ultimos = _str(snapshot.get("ultimos_dos_digitos"))

	updates = {}
	code_digits = _digits_only(code)
	description_digits = _digits_only(description)

	if (not code_digits or len(code_digits) < 2) and len(description_digits) >= 2:
		updates["code"] = description
		if not _is_blank(code):
			updates["description"] = code

	if _is_blank(ultimos):
		next_code = updates.get("code", code)
		next_description = updates.get("description", description)
		derived = _last_two_digits(next_code) or _last_two_digits(next_description)
		if derived:
			updates["ultimos_dos_digitos"] = derived

	if updates:
		frappe.db.set_value("Banco Siesa", bank_name, updates, update_modified=False)
		frappe.logger("hubgh.siesa_export").info(
			"Banco Siesa normalizado para exportación",
			extra={
				"bank": bank_name,
				"updates": updates,
				"previous": {
					"code": code,
					"description": description,
					"ultimos_dos_digitos": ultimos,
				},
			},
		)

		refreshed = _get_banco_siesa_snapshot(bank_name)
		return refreshed or snapshot

	return snapshot


def _resolve_id_banco_empleado(bank_name):
	snapshot = _normalize_banco_siesa_record(bank_name)
	if not snapshot:
		return "", ""

	bank_code = _str(snapshot.get("ultimos_dos_digitos"))
	if _is_blank(bank_code):
		bank_code = _last_two_digits(snapshot.get("description")) or _last_two_digits(snapshot.get("code"))

	notas_banco = _digits_only(snapshot.get("codigo_bancolombia")) or _digits_only(snapshot.get("code"))

	if _is_blank(bank_code):
		frappe.logger("hubgh.siesa_export").warning(
			"No fue posible resolver ID BANCO EMPLEADO",
			extra={
				"bank": bank_name,
				"snapshot": {
					"code": _str(snapshot.get("code")),
					"description": _str(snapshot.get("description")),
					"ultimos_dos_digitos": _str(snapshot.get("ultimos_dos_digitos")),
					"codigo_bancolombia": notas_banco,
				},
			},
		)

	return _str(bank_code), _str(notas_banco)


def _catalog_code(doctype, value):
	if _is_blank(value):
		return ""
	raw = normalize_code_for_doctype(doctype, _str(value))
	if frappe.db.exists(doctype, raw):
		code = frappe.db.get_value(doctype, raw, "code")
		return normalize_code_for_doctype(doctype, _str(code or raw))

	name = frappe.db.get_value(doctype, {"code": raw}, "name")
	if name:
		code = frappe.db.get_value(doctype, name, "code")
		return normalize_code_for_doctype(doctype, _str(code or name))

	name = frappe.db.get_value(doctype, {"description": raw}, "name")
	if name:
		code = frappe.db.get_value(doctype, name, "code")
		return normalize_code_for_doctype(doctype, _str(code or name))

	alias_code = _resolve_catalog_code_by_alias(doctype, raw)
	if alias_code:
		return alias_code

	return normalize_code_for_doctype(doctype, raw)


def _tipo_documento_siesa(tipo_documento):
	return {
		"Cedula": "C",
		"Cedula de extranjeria": "E",
		"Pasaporte": "P",
		"PPT": "B",
		"Tarjeta de identidad": "T",
	}.get(_str(tipo_documento), "")


def _genero_siesa(genero):
	return {"Masculino": "0", "Femenino": "1"}.get(_str(genero), "")


def _estado_civil_siesa(estado_civil):
	return {
		"": "0",
		"Soltero": "1",
		"Casado": "2",
		"Viudo": "3",
		"Divorciado": "4",
		"Unión Libre": "5",
	}.get(_str(estado_civil), "")


def _yes_no_flag(value):
	return "1" if int(value or 0) else "0"


def _tipo_cuenta_bancaria_ind(value):
	return {
		"Ahorros": "1",
		"Corriente": "2",
		"Tarjeta Prepago": "3",
	}.get(_str(value), "")


def _resolve_retirement_export_context(contrato):
	if not contrato or (getattr(contrato, "estado_contrato", "") or "") != "Retirado":
		return {"fecha_retiro": "", "id_motivo_retiro": "", "ind_estado": "0"}

	retirement_date = ""
	if getattr(contrato, "empleado", None) and frappe.db.exists("DocType", "Payroll Liquidation Case"):
		retirement_date = frappe.db.get_value(
			"Payroll Liquidation Case",
			{"employee": contrato.empleado, "status": ["not in", ["Cancelado"]]},
			"retirement_date",
		) or ""
	if not retirement_date:
		retirement_date = getattr(contrato, "fecha_fin_contrato", None) or ""
	return {
		"fecha_retiro": _safe_ymd(retirement_date),
		"id_motivo_retiro": "",
		"ind_estado": "1",
	}


def _build_employee_context(data):
	candidato = frappe.get_doc("Candidato", data.candidato) if data.candidato else None
	contrato = frappe.get_doc("Contrato", data.contrato) if data.contrato and frappe.db.exists("Contrato", data.contrato) else None

	primer_ap, segundo_ap = _split_apellidos(data)
	tipo_doc = _tipo_documento_siesa(_first(data.tipo_documento, getattr(candidato, "tipo_documento", None)))
	genero = _genero_siesa(_first(data.genero, getattr(candidato, "genero", None)))
	estado_civil = _estado_civil_siesa(_first(data.estado_civil, getattr(candidato, "estado_civil", None)))

	ctx = {
		"id": _str(_first(data.numero_documento, getattr(candidato, "numero_documento", None))),
		"tipo_documento": tipo_doc,
		"primer_apellido": _str(primer_ap),
		"segundo_apellido": _str(segundo_ap),
		"nombres": _str(_first(data.nombres, getattr(candidato, "nombres", None))),
		"sucursal_cliente": "001",
		"sucursal_proveedor": "001",
		"id_compania": "4",
		"fecha_ingreso": _safe_ymd(_first(getattr(data, "fecha_ingreso", None), getattr(data, "fecha_tentativa_ingreso", None))),
		"fecha_nacimiento": _safe_ymd(_first(data.fecha_nacimiento, getattr(candidato, "fecha_nacimiento", None))),
		"pais_nacimiento": _str(data.pais_nacimiento_siesa),
		"departamento_nacimiento": _str(data.departamento_nacimiento_siesa),
		"ciudad_nacimiento": _str(data.ciudad_nacimiento_siesa),
		"fecha_expedicion": _safe_ymd(_first(data.fecha_expedicion, getattr(candidato, "fecha_expedicion", None))),
		"pais_expedicion": _str(data.pais_expedicion_siesa),
		"departamento_expedicion": _str(data.departamento_expedicion_siesa),
		"ciudad_expedicion": _str(data.ciudad_expedicion_siesa),
		"nivel_educativo": _catalog_code(
			"Nivel Educativo Siesa",
			_first(data.nivel_educativo_siesa, getattr(candidato, "nivel_educativo_siesa", None)),
		),
		"genero": genero,
		"estado_civil": estado_civil,
		"es_extranjero": _yes_no_flag(_first(data.es_extranjero, getattr(candidato, "es_extranjero", 0))),
		"razon_social_contacto": "",
		"direccion_1": _str(_first(data.direccion, getattr(candidato, "direccion", None))),
		"direccion_2": "",
		"direccion_3": "",
		"pais_contacto": _str(_first(data.pais_residencia_siesa, data.pais_nacimiento_siesa)),
		"departamento_contacto": _str(_first(data.departamento_residencia_siesa, data.departamento_nacimiento_siesa)),
		"ciudad_contacto": _str(_first(data.ciudad_residencia_siesa, data.ciudad_nacimiento_siesa, data.ciudad)),
		"barrio_contacto": _str(data.barrio),
		"telefono_contacto": _str(_first(data.telefono_contacto_siesa, data.celular, getattr(candidato, "celular", None))),
		"fax_contacto": "",
		"codigo_postal_contacto": "",
		"correo_contacto": _str(_first(data.email, getattr(candidato, "email", None))),
		"es_empleado": "1",
		"es_declarante": "1",
		"notas_contacto": "",
		"numero_pasaporte": "",
		"id_pago_extranjero": _str(data.prefijo_cuenta_extranjero) or "NO APLICA",
	}

	if contrato and _is_blank(ctx["fecha_ingreso"]):
		ctx["fecha_ingreso"] = _safe_ymd(contrato.fecha_ingreso)

	required = {
		"ID DEL TERCERO": ctx["id"],
		"TIPO DOCUMENTO": ctx["tipo_documento"],
		"PRIMER APELLIDO": ctx["primer_apellido"],
		"SEGUNDO APELLIDO": ctx["segundo_apellido"],
		"NOMBRES": ctx["nombres"],
		"FECHA INGRESO": ctx["fecha_ingreso"],
		"FECHA NACIMIENTO": ctx["fecha_nacimiento"],
		"PAIS NACIMIENTO": ctx["pais_nacimiento"],
		"DEPTO NACIMIENTO": ctx["departamento_nacimiento"],
		"CIUDAD NACIMIENTO": ctx["ciudad_nacimiento"],
		"FECHA EXPEDICION": ctx["fecha_expedicion"],
		"PAIS EXPEDICION": ctx["pais_expedicion"],
		"DEPTO EXPEDICION": ctx["departamento_expedicion"],
		"CIUDAD EXPEDICION": ctx["ciudad_expedicion"],
		"NIVEL EDUCATIVO": ctx["nivel_educativo"],
		"GENERO": ctx["genero"],
		"ESTADO CIVIL": ctx["estado_civil"],
		"DIRECCION": ctx["direccion_1"],
		"PAIS CONTACTO": ctx["pais_contacto"],
		"DEPTO CONTACTO": ctx["departamento_contacto"],
		"CIUDAD CONTACTO": ctx["ciudad_contacto"],
		"TELEFONO CONTACTO": ctx["telefono_contacto"],
	}
	missing = [label for label, value in required.items() if _is_blank(value)]
	return ctx, missing


def _build_contract_context(data):
	candidato = frappe.get_doc("Candidato", data.candidato) if data.candidato else None
	afiliacion = get_or_create_affiliation(data.candidato) if data.candidato else None
	if not data.contrato or not frappe.db.exists("Contrato", data.contrato):
		frappe.throw(f"El candidato {data.candidato} no tiene contrato asociado para exportar.")
	contrato = frappe.get_doc("Contrato", data.contrato)
	ccf_value = _first(
		getattr(contrato, "entidad_ccf_siesa", None),
		getattr(data, "ccf_siesa", None),
		getattr(candidato, "ccf_siesa", None),
	)
	if _is_blank(getattr(contrato, "entidad_ccf_siesa", None)) and not _is_blank(ccf_value):
		frappe.db.set_value("Contrato", contrato.name, "entidad_ccf_siesa", ccf_value, update_modified=False)
		contrato.entidad_ccf_siesa = ccf_value

	id_co = _str(frappe.db.get_value("Punto de Venta", contrato.pdv_destino, "codigo") or contrato.pdv_destino)
	id_cargo = _str(frappe.db.get_value("Cargo", contrato.cargo, "codigo") or contrato.cargo)
	id_banco_empleado, notas_banco = _resolve_id_banco_empleado(contrato.banco_siesa)
	retirement_ctx = _resolve_retirement_export_context(contrato)

	tipo_contrato = _str(contrato.tipo_contrato)
	es_lectiva = tipo_contrato == "Aprendizaje Lectiva"
	es_fijo = tipo_contrato == "Fijo"
	es_extranjero = int(_first(getattr(data, "es_extranjero", None), getattr(candidato, "es_extranjero", 0)) or 0)

	ctx = {
		"id_cia": "4",
		"id_tercero": _str(contrato.numero_documento),
		"numero_contrato": _str(contrato.numero_contrato or data.numero_contrato or 1),
		"id_co": id_co,
		"id_prorroga": "",
		"id_banco": "07",
		"id_tipo_cotizante": _catalog_code("Tipo Cotizante Siesa", contrato.tipo_cotizante_siesa),
		"ind_comp_flexible": "",
		"id_proyecto": "NM",
		"id_unidad_negocio": _catalog_code("Unidad Negocio Siesa", contrato.unidad_negocio_siesa),
		"id_sucursal_autoliquidacion": "001",
		"id_motivo_retiro": retirement_ctx["id_motivo_retiro"],
		"id_turno": "",
		"id_grupo_empleados": _catalog_code("Grupo Empleados Siesa", contrato.grupo_empleados_siesa),
		"id_ccosto": _catalog_code("Centro Costos Siesa", contrato.centro_costos_siesa),
		"id_centro_trabajo": _catalog_code("Centro Trabajo Siesa", contrato.centro_trabajo_siesa),
		"id_tipo_nomina": "M",
		"id_tiempo_basico": "",
		"id_entidad_pension": _catalog_code("Entidad AFP Siesa", contrato.entidad_afp_siesa),
		"id_entidad_eps": _catalog_code("Entidad EPS Siesa", contrato.entidad_eps_siesa),
		"id_entidad_cesantias": _catalog_code("Entidad Cesantias Siesa", contrato.entidad_cesantias_siesa),
		"id_entidad_ccf": _catalog_code("Entidad CCF Siesa", ccf_value),
		"id_entidad_arl": _str(_first(data.arl_codigo_siesa, getattr(afiliacion, "arl_numero_afiliacion", None))),
		"id_entidad_sena": "899999034",
		"id_entidad_icbf": "899999239",
		"fecha_ingreso": _safe_ymd(contrato.fecha_ingreso),
		"fecha_ingreso_ley50": _safe_ymd(contrato.fecha_ingreso),
		"fecha_retiro": retirement_ctx["fecha_retiro"],
		"fecha_contrato_hasta": _safe_ymd(contrato.fecha_fin_contrato),
		"fecha_prima_hasta": _safe_ymd(contrato.fecha_ingreso),
		"fecha_vacaciones_hasta": _safe_ymd(contrato.fecha_ingreso),
		"fecha_ultimo_aumento": _safe_ymd(contrato.fecha_ingreso),
		"fecha_ultimas_vacaciones": _safe_ymd(contrato.fecha_ingreso),
		"fecha_ultima_pension": _safe_ymd(contrato.fecha_ingreso),
		"fecha_ultima_cesantias": _safe_ymd(contrato.fecha_ingreso),
		"salario": str(int(float(contrato.salario or 0))),
		"salario_anterior": str(int(float(contrato.salario or 0))),
		"valor_deducible_retefuente": "0",
		"valor_cesantias_congeladas": "0",
		"valor_cesantias_retiradas": "0",
		"valor_otros_salud": "0",
		"valor_salud_obligatorio": "0",
		"horas_mes": str(contrato.horas_trabajadas_mes or 220),
		"porc_retefuente": "0",
		"porc_tiempo_laborado": "100",
		"dias_vacaciones": "0",
		"consecutivo_contrato": "1",
		"personas_cargo": str(int(_first(getattr(candidato, "personas_a_cargo", None), 0) or 0)),
		"cuenta_bancaria": _str(contrato.cuenta_bancaria),
		"ind_forma_pago": "2",
		"ind_regimen_laboral": "3" if es_lectiva else "1",
		"ind_auxilio_transporte": _str(_first(data.aplica_auxilio_transporte, "3")) or "3",
		"ind_procedimiento_retencion": "1",
		"ind_pacto_colectivo": "0",
		"ind_subsidio_familiar": "0",
		"ind_poliza_huc": "0",
		"ind_deducible": "0",
		"ind_otros_salud": "0",
		"ind_etiqueta": "0",
		"ind_salario_integral": "0",
		"ind_ley_789": "1" if es_lectiva else "0",
		"ind_subtipo_cotizante": "0",
		"ind_extranjero_pension": "1" if es_extranjero else "0",
		"ind_continuidad": "0",
		"ind_tipo_cuenta": _tipo_cuenta_bancaria_ind(contrato.tipo_cuenta_bancaria),
		"ind_clase_contrato": "0",
		"ind_termino_contrato": "1" if (es_fijo or not _is_blank(contrato.fecha_fin_contrato)) else "0",
		"ind_estado": retirement_ctx["ind_estado"],
		"id_cargo": id_cargo,
		"valor_salud_prepagada": "0",
		"valor_dependientes": "0",
		"ind_consolida_retencion": "1",
		"notas": notas_banco,
		"ad_num_1": "",
		"ad_num_2": "",
		"ad_num_3": "",
		"ad_num_4": "",
		"ad_alf_1": "",
		"ad_alf_2": "",
		"ad_alf_3": "",
		"ad_alf_4": "",
		"fecha_sustitucion": "",
		"ind_base_salarial_cf": "",
		"tipo_salario": "0",
		"id_banco_empleado": id_banco_empleado,
	}

	required = {
		"ID TERCERO": ctx["id_tercero"],
		"NUMERO CONTRATO": ctx["numero_contrato"],
		"ID CO": ctx["id_co"],
		"ID TIPO COTIZANTE": ctx["id_tipo_cotizante"],
		"ID UNIDAD NEGOCIO": ctx["id_unidad_negocio"],
		"ID GRUPO EMPLEADOS": ctx["id_grupo_empleados"],
		"ID CCOSTO": ctx["id_ccosto"],
		"ID CENTRO TRABAJO": ctx["id_centro_trabajo"],
		"ID ENTIDAD PENSION": ctx["id_entidad_pension"],
		"ID ENTIDAD EPS": ctx["id_entidad_eps"],
		"ID ENTIDAD CESANTIAS": ctx["id_entidad_cesantias"],
		"ID ENTIDAD CCF": ctx["id_entidad_ccf"],
		"ID ENTIDAD ARL": ctx["id_entidad_arl"],
		"FECHA INGRESO": ctx["fecha_ingreso"],
		"SALARIO": ctx["salario"],
		"HORAS MES": ctx["horas_mes"],
		"CUENTA BANCARIA": ctx["cuenta_bancaria"],
		"IND TIPO CUENTA": ctx["ind_tipo_cuenta"],
		"ID CARGO": ctx["id_cargo"],
		"ID BANCO EMPLEADO": ctx["id_banco_empleado"],
	}
	missing = [label for label, value in required.items() if _is_blank(value)]
	return ctx, missing


def _split_apellidos(row):
	primer_ap = (getattr(row, "primer_apellido", None) or "").strip()
	segundo_ap = (getattr(row, "segundo_apellido", None) or "").strip()

	if primer_ap and segundo_ap:
		return primer_ap, segundo_ap

	apellidos_raw = (getattr(row, "apellidos", None) or "").strip()
	partes_apellidos = [p.strip() for p in apellidos_raw.split() if p and p.strip()]

	if not primer_ap and len(partes_apellidos) >= 1:
		primer_ap = partes_apellidos[0]
	if not segundo_ap and len(partes_apellidos) >= 2:
		segundo_ap = " ".join(partes_apellidos[1:]).strip()

	return primer_ap, segundo_ap


def _parse_candidates(candidatos):
	if not candidatos:
		return []
	if isinstance(candidatos, (list, tuple)):
		return list(candidatos)
	try:
		parsed = json.loads(candidatos)
		if isinstance(parsed, list):
			return parsed
	except Exception:
		pass
	return []


def _validated_candidate_data(candidatos):
	rows = []
	for candidate in _parse_candidates(candidatos):
		validation = validar_candidato_para_siesa(candidate)
		if not validation["ok"]:
			frappe.throw(f"Candidato {candidate} no está listo para SIESA: {', '.join(validation['errors'])}")
		datos = frappe.get_doc("Datos Contratacion", validation["datos"])
		rows.append(datos)
	return rows


@frappe.whitelist()
def exportar_conector_empleados(fecha_desde=None, fecha_hasta=None, candidatos=None):
	openpyxl = _xlsx_library()

	validated = _validated_candidate_data(candidatos)
	if not validated:
		frappe.throw("No se enviaron candidatos válidos para generar el conector de empleados.")

	wb = openpyxl.Workbook()
	ws = wb.active
	ws.title = "DATOS"
	ws.append(EMPLOYEE_EXPORT_HEADERS)

	for row in validated:
		ctx, missing = _build_employee_context(row)
		if missing:
			frappe.throw(f"El candidato {row.candidato} no está listo para conector de empleados. Faltan: {', '.join(missing)}")

		ws.append([
			ctx["id"],
			ctx["tipo_documento"],
			ctx["primer_apellido"],
			ctx["segundo_apellido"],
			ctx["nombres"],
			ctx["sucursal_cliente"],
			ctx["sucursal_proveedor"],
			ctx["id_compania"],
			ctx["fecha_ingreso"],
			ctx["fecha_nacimiento"],
			ctx["pais_nacimiento"],
			ctx["departamento_nacimiento"],
			ctx["ciudad_nacimiento"],
			ctx["fecha_expedicion"],
			ctx["pais_expedicion"],
			ctx["departamento_expedicion"],
			ctx["ciudad_expedicion"],
			ctx["nivel_educativo"],
			ctx["genero"],
			ctx["estado_civil"],
			ctx["es_extranjero"],
			ctx["razon_social_contacto"],
			ctx["direccion_1"],
			ctx["direccion_2"],
			ctx["direccion_3"],
			ctx["pais_contacto"],
			ctx["departamento_contacto"],
			ctx["ciudad_contacto"],
			ctx["barrio_contacto"],
			ctx["telefono_contacto"],
			ctx["fax_contacto"],
			ctx["codigo_postal_contacto"],
			ctx["correo_contacto"],
			ctx["es_empleado"],
			ctx["es_declarante"],
			ctx["notas_contacto"],
			ctx["numero_pasaporte"],
			ctx["id_pago_extranjero"],
		])

	buf = io.BytesIO()
	wb.save(buf)
	buf.seek(0)

	filename = f"Conector_Empleados_Nuevos_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
	frappe.response["filename"] = filename
	frappe.response["filecontent"] = buf.read()
	frappe.response["type"] = "binary"


@frappe.whitelist()
def exportar_conector_contratos(fecha_desde=None, fecha_hasta=None, candidatos=None):
	openpyxl = _xlsx_library()

	validated = _validated_candidate_data(candidatos)
	if not validated:
		frappe.throw("No se enviaron candidatos válidos para generar el conector de contratos.")

	wb = openpyxl.Workbook()
	ws = wb.active
	ws.title = "DATOS"
	ws.append(CONTRACT_EXPORT_HEADERS)

	for data in validated:
		ctx, missing = _build_contract_context(data)
		if missing:
			frappe.throw(f"El candidato {data.candidato} no está listo para conector de contratos. Faltan: {', '.join(missing)}")

		ws.append([
			ctx["id_cia"],
			ctx["id_tercero"],
			ctx["numero_contrato"],
			ctx["id_co"],
			ctx["id_prorroga"],
			ctx["id_banco"],
			ctx["id_tipo_cotizante"],
			ctx["ind_comp_flexible"],
			ctx["id_proyecto"],
			ctx["id_unidad_negocio"],
			ctx["id_sucursal_autoliquidacion"],
			ctx["id_motivo_retiro"],
			ctx["id_turno"],
			ctx["id_grupo_empleados"],
			ctx["id_ccosto"],
			ctx["id_centro_trabajo"],
			ctx["id_tipo_nomina"],
			ctx["id_tiempo_basico"],
			ctx["id_entidad_pension"],
			ctx["id_entidad_eps"],
			ctx["id_entidad_cesantias"],
			ctx["id_entidad_ccf"],
			ctx["id_entidad_arl"],
			ctx["id_entidad_sena"],
			ctx["id_entidad_icbf"],
			ctx["fecha_ingreso"],
			ctx["fecha_ingreso_ley50"],
			ctx["fecha_retiro"],
			ctx["fecha_contrato_hasta"],
			ctx["fecha_prima_hasta"],
			ctx["fecha_vacaciones_hasta"],
			ctx["fecha_ultimo_aumento"],
			ctx["fecha_ultimas_vacaciones"],
			ctx["fecha_ultima_pension"],
			ctx["fecha_ultima_cesantias"],
			ctx["salario"],
			ctx["salario_anterior"],
			ctx["valor_deducible_retefuente"],
			ctx["valor_cesantias_congeladas"],
			ctx["valor_cesantias_retiradas"],
			ctx["valor_otros_salud"],
			ctx["valor_salud_obligatorio"],
			ctx["horas_mes"],
			ctx["porc_retefuente"],
			ctx["porc_tiempo_laborado"],
			ctx["dias_vacaciones"],
			ctx["consecutivo_contrato"],
			ctx["personas_cargo"],
			ctx["cuenta_bancaria"],
			ctx["ind_forma_pago"],
			ctx["ind_regimen_laboral"],
			ctx["ind_auxilio_transporte"],
			ctx["ind_procedimiento_retencion"],
			ctx["ind_pacto_colectivo"],
			ctx["ind_subsidio_familiar"],
			ctx["ind_poliza_huc"],
			ctx["ind_deducible"],
			ctx["ind_otros_salud"],
			ctx["ind_etiqueta"],
			ctx["ind_salario_integral"],
			ctx["ind_ley_789"],
			ctx["ind_subtipo_cotizante"],
			ctx["ind_extranjero_pension"],
			ctx["ind_continuidad"],
			ctx["ind_tipo_cuenta"],
			ctx["ind_clase_contrato"],
			ctx["ind_termino_contrato"],
			ctx["ind_estado"],
			ctx["id_cargo"],
			ctx["valor_salud_prepagada"],
			ctx["valor_dependientes"],
			ctx["ind_consolida_retencion"],
			ctx["notas"],
			ctx["ad_num_1"],
			ctx["ad_num_2"],
			ctx["ad_num_3"],
			ctx["ad_num_4"],
			ctx["ad_alf_1"],
			ctx["ad_alf_2"],
			ctx["ad_alf_3"],
			ctx["ad_alf_4"],
			ctx["fecha_sustitucion"],
			ctx["ind_base_salarial_cf"],
			ctx["tipo_salario"],
			ctx["id_banco_empleado"],
		])

	buf = io.BytesIO()
	wb.save(buf)
	buf.seek(0)

	filename = f"Conector_Contratos_Nuevos_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
	frappe.response["filename"] = filename
	frappe.response["filecontent"] = buf.read()
	frappe.response["type"] = "binary"
