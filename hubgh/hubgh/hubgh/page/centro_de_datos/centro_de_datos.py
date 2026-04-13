import csv
import os
import re
import uuid
import zipfile
from copy import deepcopy
from datetime import datetime, timezone
from io import BytesIO, StringIO

import frappe
from frappe import _
from frappe.utils import getdate, validate_email_address
from frappe.utils.file_manager import save_file

from hubgh.hubgh.document_service import upload_person_document
from hubgh.person_identity import normalize_document, reconcile_person_identity


DEFAULT_IMPORT_CHUNK_SIZE = 50
MAX_IMPORT_ERRORS = 200
IMPORT_STATUS_TTL_SEC = 60 * 60 * 24
_IMPORT_STATUS_FALLBACK = {}

ALLOWED_BULK_DOCTYPES = {
	"Documentos Empleado": "bulk_upload_employee_documents",
	"Punto de Venta": "create_punto",
	"Ficha Empleado": "create_empleado",
	"Actualización Empleado": "update_empleado",
	"Novedad SST": "create_novedad",
	"Estado SST Empleado": "upsert_employee_sst_status",
	"User": "create_user",
}

EXPECTED_CSV_COLUMNS = {
	"Documentos Empleado": {"cedula", "document_type", "archivo"},
	"Punto de Venta": {"nombre_pdv"},
	"Ficha Empleado": {"cedula", "pdv"},
	"Actualización Empleado": {"cedula"},
	"Novedad SST": {"cedula_empleado", "tipo_novedad", "fecha_inicio", "fecha_fin"},
	"Estado SST Empleado": {"cedula_empleado", "tipo_novedad", "fecha_inicio", "fecha_fin"},
	"User": {"email"},
}

ZIP_BULK_DOCTYPES = {"Documentos Empleado"}


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


def _utcnow_iso():
	return datetime.now(timezone.utc).isoformat()


def _coerce_chunk_size(value):
	try:
		chunk_size = int(value or DEFAULT_IMPORT_CHUNK_SIZE)
	except (TypeError, ValueError):
		chunk_size = DEFAULT_IMPORT_CHUNK_SIZE
	return max(10, min(chunk_size, 200))


def _get_import_status_key(import_id):
	return f"hubgh:centro_de_datos:import:{import_id}"


def _get_cache():
	cache_factory = getattr(frappe, "cache", None)
	if not callable(cache_factory):
		return None
	try:
		return cache_factory()
	except Exception:
		return None


def _save_import_status(import_id, payload):
	state = deepcopy(payload)
	cache = _get_cache()
	if cache and hasattr(cache, "set_value"):
		cache.set_value(_get_import_status_key(import_id), state, expires_in_sec=IMPORT_STATUS_TTL_SEC)
		return
	_IMPORT_STATUS_FALLBACK[import_id] = state


def _load_import_status(import_id):
	cache = _get_cache()
	if cache and hasattr(cache, "get_value"):
		state = cache.get_value(_get_import_status_key(import_id))
		if state:
			return state
	return deepcopy(_IMPORT_STATUS_FALLBACK.get(import_id))


def _empty_import_counts():
	return {
		"processed": 0,
		"created": 0,
		"updated": 0,
		"skipped": 0,
		"errors": 0,
	}


def _new_import_status(import_id, doctype, file_url, total_rows, chunk_size):
	return {
		"import_id": import_id,
		"doctype": doctype,
		"file_url": file_url,
		"status": "queued",
		"message": "Carga encolada correctamente.",
		"created_at": _utcnow_iso(),
		"started_at": None,
		"finished_at": None,
		"chunk_size": chunk_size,
		"total_rows": total_rows,
		"processed_rows": 0,
		"progress": 0,
		"counts": _empty_import_counts(),
		"errors": [],
		"supported_doctypes": get_supported_doctypes(),
	}


def _append_import_error(state, row_index, exc):
	state["counts"]["errors"] += 1
	if len(state["errors"]) < MAX_IMPORT_ERRORS:
		state["errors"].append({"row": row_index, "code": "row_validation", "message": str(exc)})


def _record_handler_result(state, result):
	result = result or {}
	action = result.get("action") or "skipped"
	state["counts"]["processed"] += 1
	if action == "created":
		state["counts"]["created"] += 1
	elif action == "updated":
		state["counts"]["updated"] += 1
	else:
		state["counts"]["skipped"] += 1


def _row_is_effectively_empty(row):
	if not row:
		return True
	for key, value in row.items():
		if key is None:
			continue
		if str(value or "").strip():
			return False
	return True


def _read_csv_rows(doctype, file_url):
	if doctype not in ALLOWED_BULK_DOCTYPES:
		frappe.throw(_stable_error("unsupported_doctype", doctype))

	file_doc = frappe.get_doc("File", {"file_url": file_url})
	content = file_doc.get_content()
	if not content:
		frappe.throw(_(_stable_error("empty_file")))

	content = _decode_csv_content(content)
	reader = _build_csv_reader(content)
	columns_error = _validate_expected_columns(doctype, reader.fieldnames)
	if columns_error:
		frappe.throw(columns_error)

	return [(index, row) for index, row in enumerate(reader, start=2) if not _row_is_effectively_empty(row)]


def _read_bulk_rows(doctype, file_url):
	if doctype in ZIP_BULK_DOCTYPES:
		return _read_zip_rows(doctype, file_url)
	return _read_csv_rows(doctype, file_url)


def _read_uploaded_file(file_url):
	file_doc = frappe.get_doc("File", {"file_url": file_url})
	content = file_doc.get_content()
	if not content:
		frappe.throw(_(_stable_error("empty_file")))
	return file_doc, content


def _normalize_zip_member_name(value):
	return str(value or "").strip().replace("\\", "/").lstrip("/")


def _resolve_manifest_name(zip_file):
	candidates = []
	for info in zip_file.infolist():
		if info.is_dir():
			continue
		member_name = _normalize_zip_member_name(info.filename)
		if not member_name.lower().endswith(".csv"):
			continue
		base_name = member_name.rsplit("/", 1)[-1].lower()
		priority = 0 if base_name in {"documentos.csv", "manifest.csv", "manifest_documentos.csv"} else 1
		candidates.append((priority, len(member_name.split("/")), member_name))
	if not candidates:
		frappe.throw("El ZIP debe incluir un manifest CSV (por ejemplo documentos.csv o manifest.csv).")
	return sorted(candidates)[0][2]


def _read_zip_rows(doctype, file_url):
	if doctype not in ALLOWED_BULK_DOCTYPES:
		frappe.throw(_stable_error("unsupported_doctype", doctype))

	_file_doc, content = _read_uploaded_file(file_url)
	buffer = BytesIO(content if isinstance(content, bytes) else str(content).encode("utf-8"))
	try:
		archive = zipfile.ZipFile(buffer)
	except zipfile.BadZipFile:
		frappe.throw("La carga masiva documental debe venir en un archivo ZIP válido.")

	with archive:
		manifest_name = _resolve_manifest_name(archive)
		manifest_content = _decode_csv_content(archive.read(manifest_name))
		reader = _build_csv_reader(manifest_content)
		columns_error = _validate_expected_columns(doctype, reader.fieldnames)
		if columns_error:
			frappe.throw(columns_error)

		available_files = {
			_normalize_zip_member_name(info.filename): info
			for info in archive.infolist()
			if not info.is_dir() and _normalize_zip_member_name(info.filename) != manifest_name
		}
		rows = []
		for index, row in enumerate(reader, start=2):
			if _row_is_effectively_empty(row):
				continue
			attachment_name = _normalize_zip_member_name(row.get("archivo"))
			if not attachment_name:
				raise Exception(f"Fila {index}: el campo 'archivo' es obligatorio para documentos masivos.")
			zip_info = available_files.get(attachment_name)
			if not zip_info:
				raise Exception(f"Fila {index}: archivo '{attachment_name}' no encontrado dentro del ZIP.")
			row_payload = dict(row)
			row_payload["__attachment_name"] = attachment_name
			row_payload["__attachment_filename"] = os.path.basename(attachment_name)
			row_payload["__attachment_content"] = archive.read(zip_info)
			rows.append((index, row_payload))
		return rows


def _chunked(rows, chunk_size):
	for offset in range(0, len(rows), chunk_size):
		yield rows[offset: offset + chunk_size]


def _set_bulk_import_flag(enabled):
	flags = getattr(frappe, "flags", None)
	if flags is None:
		class _Flags:
			pass

		flags = _Flags()
		frappe.flags = flags
	flags.hubgh_centro_datos_bulk_import = enabled


def _finalize_bulk_side_effects(state):
	if state["counts"]["created"] + state["counts"]["updated"] <= 0:
		return
	from hubgh.user_groups import sync_all_user_groups

	sync_all_user_groups()


def _run_import_rows(rows, doctype, *, chunk_size):
	handler = globals()[ALLOWED_BULK_DOCTYPES[doctype]]
	import_id = uuid.uuid4().hex
	state = _new_import_status(import_id, doctype, None, len(rows), chunk_size)
	state["status"] = "running"
	state["started_at"] = _utcnow_iso()
	_save_import_status(import_id, state)
	previous_bulk_flag = getattr(getattr(frappe, "flags", None), "hubgh_centro_datos_bulk_import", False)
	_set_bulk_import_flag(True)
	try:
		for chunk in _chunked(rows, chunk_size):
			for row_index, row in chunk:
				try:
					result = handler(row)
				except Exception as exc:
					_append_import_error(state, row_index, exc)
					state["counts"]["processed"] += 1
				else:
					_record_handler_result(state, result)
				state["processed_rows"] += 1
			if hasattr(frappe.db, "commit"):
				frappe.db.commit()
			state["progress"] = int((state["processed_rows"] / max(state["total_rows"], 1)) * 100)
			state["message"] = f"Procesadas {state['processed_rows']} de {state['total_rows']} filas."
			_save_import_status(import_id, state)
		_finalize_bulk_side_effects(state)
		state["status"] = "completed"
		state["finished_at"] = _utcnow_iso()
		state["progress"] = 100
		state["message"] = "Carga finalizada."
		_save_import_status(import_id, state)
		return state
	except Exception as exc:
		state["status"] = "failed"
		state["finished_at"] = _utcnow_iso()
		state["message"] = str(exc)
		_save_import_status(import_id, state)
		raise
	finally:
		_set_bulk_import_flag(previous_bulk_flag)


@frappe.whitelist()
def get_supported_doctypes():
	return sorted(ALLOWED_BULK_DOCTYPES.keys())


@frappe.whitelist()
def start_upload_data(doctype, file_url, chunk_size=DEFAULT_IMPORT_CHUNK_SIZE):
	rows = _read_bulk_rows(doctype, file_url)
	chunk_size = _coerce_chunk_size(chunk_size)
	import_id = uuid.uuid4().hex
	state = _new_import_status(import_id, doctype, file_url, len(rows), chunk_size)
	_save_import_status(import_id, state)
	enqueue = getattr(frappe, "enqueue", None)
	if callable(enqueue):
		enqueue(
			"hubgh.hubgh.page.centro_de_datos.centro_de_datos.process_upload_data_job",
			queue="long",
			timeout=60 * 60,
			job_name=f"centro-de-datos:{doctype}:{import_id}",
			import_id=import_id,
			doctype=doctype,
			file_url=file_url,
			chunk_size=chunk_size,
		)
	else:
		process_upload_data_job(import_id=import_id, doctype=doctype, file_url=file_url, chunk_size=chunk_size)
	return _load_import_status(import_id)


@frappe.whitelist()
def get_upload_status(import_id):
	status = _load_import_status(import_id)
	if not status:
		frappe.throw("No encontramos esa carga masiva o ya expiró su estado.")
	return status


def process_upload_data_job(import_id, doctype, file_url, chunk_size=DEFAULT_IMPORT_CHUNK_SIZE):
	rows = _read_bulk_rows(doctype, file_url)
	state = _load_import_status(import_id) or _new_import_status(import_id, doctype, file_url, len(rows), _coerce_chunk_size(chunk_size))
	state["status"] = "running"
	state["started_at"] = state.get("started_at") or _utcnow_iso()
	state["message"] = "Procesando archivo en background."
	state["total_rows"] = len(rows)
	state["chunk_size"] = _coerce_chunk_size(chunk_size)
	_save_import_status(import_id, state)
	handler = globals()[ALLOWED_BULK_DOCTYPES[doctype]]
	previous_bulk_flag = getattr(getattr(frappe, "flags", None), "hubgh_centro_datos_bulk_import", False)
	_set_bulk_import_flag(True)
	try:
		for chunk in _chunked(rows, state["chunk_size"]):
			for row_index, row in chunk:
				try:
					result = handler(row)
				except Exception as exc:
					_append_import_error(state, row_index, exc)
					state["counts"]["processed"] += 1
				else:
					_record_handler_result(state, result)
				state["processed_rows"] += 1
			if hasattr(frappe.db, "commit"):
				frappe.db.commit()
			state["progress"] = int((state["processed_rows"] / max(state["total_rows"], 1)) * 100)
			state["message"] = f"Procesadas {state['processed_rows']} de {state['total_rows']} filas."
			_save_import_status(import_id, state)
		_finalize_bulk_side_effects(state)
		state["status"] = "completed"
		state["finished_at"] = _utcnow_iso()
		state["progress"] = 100
		state["message"] = "Carga finalizada."
		_save_import_status(import_id, state)
		return state
	except Exception as exc:
		state["status"] = "failed"
		state["finished_at"] = _utcnow_iso()
		state["message"] = str(exc)
		_save_import_status(import_id, state)
		raise
	finally:
		_set_bulk_import_flag(previous_bulk_flag)


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

	try:
		rows = _read_bulk_rows(doctype, file_url)
	except Exception as exc:
		return {
			"success": 0,
			"committed": 0,
			"errors": [str(exc)],
			"supported_doctypes": get_supported_doctypes(),
		}

	success_count = 0
	errors = []
	if hasattr(frappe.db, "sql"):
		frappe.db.sql("SAVEPOINT centro_de_datos_upload")

	for index, row in rows:
		try:
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


def _update_value(doc, fieldname, value, changed_fields):
	if getattr(doc, fieldname, None) == value:
		return
	setattr(doc, fieldname, value)
	changed_fields.append(fieldname)


def _first_present(row, *fieldnames):
	for fieldname in fieldnames:
		value = row.get(fieldname)
		if value is None:
			continue
		if isinstance(value, str):
			trimmed = value.strip()
			if trimmed:
				return trimmed
			continue
		return value
	return None


def _coerce_bool(value, *, default=None):
	if value in (None, ""):
		return default
	if isinstance(value, bool):
		return int(value)
	text = str(value).strip().lower()
	if text in {"1", "si", "sí", "s", "true", "x", "yes"}:
		return 1
	if text in {"0", "no", "n", "false"}:
		return 0
	raise Exception(f"Valor booleano inválido: {value}. Usá Sí/No, 1/0 o True/False.")


def _coerce_date_value(value):
	if value in (None, ""):
		return None
	return getdate(str(value).strip())


def _coerce_int_value(value, *, default=None):
	if value in (None, ""):
		return default
	return int(str(value).strip())


def _resolve_pdv_name(pdv_nombre, *, cedula=None, required=False):
	pdv_nombre = (pdv_nombre or "").strip()
	if not pdv_nombre:
		if required:
			raise Exception(f"Empleado {cedula or ''}: el campo 'pdv' es requerido.".strip())
		return None
	pdv_name = frappe.db.get_value("Punto de Venta", {"nombre_pdv": pdv_nombre}, "name") or (
		pdv_nombre if frappe.db.exists("Punto de Venta", pdv_nombre) else None
	)
	if not pdv_name:
		raise Exception(
			f"Empleado {cedula}: Punto de Venta '{pdv_nombre}' no encontrado. "
			"Cargá los Puntos de Venta antes de los Empleados."
		)
	return pdv_name


def _apply_employee_payload(doc, row, *, is_new=False):
	changed_fields = []
	for fieldname in ("nombres", "apellidos", "cargo", "email", "tipo_jornada"):
		value = (row.get(fieldname) or "").strip()
		if value or is_new:
			_update_value(doc, fieldname, value, changed_fields)

	estado = (row.get("estado") or ("Activo" if is_new else "")).strip()
	if estado:
		_update_value(doc, "estado", estado, changed_fields)

	fecha_raw = (row.get("fecha_ingreso") or "").strip()
	if fecha_raw:
		_update_value(doc, "fecha_ingreso", getdate(fecha_raw), changed_fields)

	pdv_name = _resolve_pdv_name(row.get("pdv"), cedula=(row.get("cedula") or "").strip(), required=is_new)
	if pdv_name:
		_update_value(doc, "pdv", pdv_name, changed_fields)

	return changed_fields


def _upsert_novedad_for_employee(employee_name, row, *, optional=False):
	tipo_novedad = _first_present(row, "tipo_novedad", "novedad_tipo") or ""
	fecha_inicio = _first_present(row, "fecha_inicio", "novedad_fecha_inicio") or ""
	fecha_fin = _first_present(row, "fecha_fin", "novedad_fecha_fin") or ""
	descripcion = _first_present(row, "descripcion", "novedad_descripcion") or ""

	if optional and not any([tipo_novedad, fecha_inicio, fecha_fin, descripcion]):
		return None

	if not (tipo_novedad and fecha_inicio and fecha_fin):
		raise Exception("Para registrar una novedad debés enviar tipo_novedad/novedad_tipo, fecha_inicio/novedad_fecha_inicio y fecha_fin/novedad_fecha_fin.")

	fecha_inicio_value = getdate(fecha_inicio)
	fecha_fin_value = getdate(fecha_fin)
	novedad_payload = {
		"descripcion": descripcion,
		"titulo_resumen": _first_present(row, "titulo_resumen"),
		"descripcion_resumen": _first_present(row, "descripcion_resumen"),
		"estado": _first_present(row, "estado_novedad", "novedad_estado", "estado"),
		"prioridad": _first_present(row, "prioridad"),
		"estado_destino": _first_present(row, "estado_destino", "novedad_estado_destino"),
		"tipo_alerta": _first_present(row, "tipo_alerta"),
		"frecuencia_alerta": _first_present(row, "frecuencia_alerta"),
		"causa_evento": _first_present(row, "causa_evento"),
		"causa_raiz": _first_present(row, "causa_raiz"),
		"origen_incapacidad": _first_present(row, "origen_incapacidad"),
		"diagnostico_corto": _first_present(row, "diagnostico_corto"),
		"recomendaciones_detalle": _first_present(row, "recomendaciones_detalle"),
		"aforado_motivo": _first_present(row, "aforado_motivo"),
		"categoria_seguimiento": _first_present(row, "categoria_seguimiento"),
	}
	for fieldname, raw_value in {
		"fecha_accidente": _first_present(row, "fecha_accidente"),
		"aforado_desde": _first_present(row, "aforado_desde"),
		"proxima_alerta_fecha": _first_present(row, "proxima_alerta_fecha"),
	}.items():
		novedad_payload[fieldname] = _coerce_date_value(raw_value)
	for fieldname, raw_value in {
		"es_accidente_trabajo": _first_present(row, "es_accidente_trabajo"),
		"accidente_tuvo_incapacidad": _first_present(row, "accidente_tuvo_incapacidad"),
		"reportado_arl": _first_present(row, "reportado_arl"),
		"en_radar": _first_present(row, "en_radar"),
		"alerta_activa": _first_present(row, "alerta_activa"),
		"crear_alerta": _first_present(row, "crear_alerta"),
		"impacta_estado": _first_present(row, "impacta_estado"),
	}.items():
		value = _coerce_bool(raw_value, default=None)
		if value is not None:
			novedad_payload[fieldname] = value
	for fieldname, raw_value in {
		"dias_para_alerta": _first_present(row, "dias_para_alerta"),
		"dias_alerta_post_incapacidad": _first_present(row, "dias_alerta_post_incapacidad"),
	}.items():
		value = _coerce_int_value(raw_value, default=None)
		if value is not None:
			novedad_payload[fieldname] = value
	if novedad_payload.get("estado_destino") and "impacta_estado" not in novedad_payload:
		novedad_payload["impacta_estado"] = 1
	if _first_present(row, "evidencia_incapacidad"):
		novedad_payload["evidencia_incapacidad"] = _first_present(row, "evidencia_incapacidad")
	existing_name = frappe.db.get_value(
		"Novedad SST",
		{
			"empleado": employee_name,
			"tipo_novedad": tipo_novedad,
			"fecha_inicio": fecha_inicio_value,
			"fecha_fin": fecha_fin_value,
		},
		"name",
	)
	if existing_name:
		doc = frappe.get_doc("Novedad SST", existing_name)
		changed_fields = []
		for fieldname, value in novedad_payload.items():
			if value in (None, ""):
				continue
			_update_value(doc, fieldname, value, changed_fields)
		if changed_fields:
			doc.save(ignore_permissions=True)
			return {"action": "updated", "name": existing_name}
		return {"action": "skipped", "name": existing_name}

	doc = frappe.new_doc("Novedad SST")
	doc.empleado = employee_name
	doc.tipo_novedad = tipo_novedad
	doc.fecha_inicio = fecha_inicio_value
	doc.fecha_fin = fecha_fin_value
	for fieldname, value in novedad_payload.items():
		if value in (None, ""):
			continue
		setattr(doc, fieldname, value)
	doc.insert()
	return {"action": "created", "name": doc.name}


def _resolve_employee_by_cedula(cedula):
	cedula = (cedula or "").strip()
	if not cedula:
		raise Exception("El campo 'cedula' o 'cedula_empleado' es requerido.")
	emp_name = frappe.db.get_value("Ficha Empleado", {"cedula": cedula}, "name")
	if not emp_name:
		raise Exception(f"Empleado con cédula {cedula} no encontrado.")
	return emp_name


def bulk_upload_employee_documents(row):
	emp_name = _resolve_employee_by_cedula(_first_present(row, "cedula", "cedula_empleado"))
	document_type = _first_present(row, "document_type", "tipo_documento")
	if not document_type:
		raise Exception("El campo 'document_type' es requerido para documentos masivos.")
	attachment_content = row.get("__attachment_content")
	attachment_filename = row.get("__attachment_filename")
	if not attachment_content or not attachment_filename:
		raise Exception("No encontramos el archivo adjunto para esta fila documental.")

	resolved_document_type = document_type.strip()
	existing_name = frappe.db.get_value(
		"Person Document",
		{"employee": emp_name, "document_type": resolved_document_type},
		"name",
	)
	file_doc = save_file(attachment_filename, attachment_content, "Ficha Empleado", emp_name, is_private=1)
	doc = upload_person_document(
		person_type="Empleado",
		person=emp_name,
		document_type=resolved_document_type,
		file_url=file_doc.file_url,
		notes=_first_present(row, "notes", "notas"),
	)
	issue_date = _coerce_date_value(_first_present(row, "issue_date", "fecha_emision"))
	valid_until = _coerce_date_value(_first_present(row, "valid_until", "fecha_vencimiento"))
	changed_fields = []
	if issue_date is not None:
		_update_value(doc, "issue_date", issue_date, changed_fields)
	if _first_present(row, "valid_until", "fecha_vencimiento") is not None:
		_update_value(doc, "valid_until", valid_until, changed_fields)
	if changed_fields:
		doc.save(ignore_permissions=True)
	return {
		"action": "updated" if existing_name else "created",
		"employee": emp_name,
		"document": doc.name,
		"file_url": file_doc.file_url,
	}


def upsert_employee_sst_status(row):
	emp_name = _resolve_employee_by_cedula(_first_present(row, "cedula_empleado", "cedula"))
	result = _upsert_novedad_for_employee(emp_name, row)
	return {"action": result.get("action", "skipped"), "employee": emp_name, "novedad": result.get("name")}


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

	existing_name = frappe.db.get_value("Punto de Venta", {"nombre_pdv": nombre}, "name")
	if existing_name:
		doc = frappe.get_doc("Punto de Venta", existing_name)
		changed_fields = []
		for fieldname, value in {
			"zona": (row.get("zona") or "").strip(),
			"ciudad": (row.get("ciudad") or "").strip(),
			"departamento": (row.get("departamento") or "").strip(),
			"planta_autorizada": int(row.get("planta_autorizada") or 0),
		}.items():
			if value or isinstance(value, int):
				_update_value(doc, fieldname, value, changed_fields)
		if changed_fields:
			doc.save(ignore_permissions=True)
			return {"action": "updated", "punto": doc.name}
		return {"action": "skipped", "punto": doc.name}

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
	return {"action": "created", "punto": doc.name}


def create_empleado(row):
	cedula = (row.get("cedula") or "").strip()
	if not cedula:
		raise Exception("El campo 'cedula' es requerido.")

	existing_name = frappe.db.get_value("Ficha Empleado", {"cedula": cedula}, "name")
	if existing_name:
		doc = frappe.get_doc("Ficha Empleado", existing_name)
		changed_fields = _apply_employee_payload(doc, row, is_new=False)
		if changed_fields:
			doc.save(ignore_permissions=True)
			action = "updated"
		else:
			action = "skipped"
	else:
		doc = frappe.new_doc("Ficha Empleado")
		doc.cedula = cedula
		_apply_employee_payload(doc, row, is_new=True)
		doc.insert()
		action = "created"

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
	return {"action": action, "employee": doc.name, "user": identity.user}


def update_empleado(row):
	cedula = (row.get("cedula") or "").strip()
	if not cedula:
		raise Exception("El campo 'cedula' es requerido.")

	existing_name = frappe.db.get_value("Ficha Empleado", {"cedula": cedula}, "name")
	if not existing_name:
		raise Exception(f"Empleado con cédula {cedula} no encontrado para actualización.")

	doc = frappe.get_doc("Ficha Empleado", existing_name)
	changed_fields = _apply_employee_payload(doc, row, is_new=False)
	if changed_fields:
		doc.save(ignore_permissions=True)

	novedad_result = _upsert_novedad_for_employee(doc.name, row, optional=True)
	identity = reconcile_person_identity(
		employee=doc,
		document=cedula,
		email=(doc.email or "").strip() or None,
		allow_create_user=True,
		user_defaults={
			"first_name": doc.nombres or "Empleado",
			"last_name": doc.apellidos or "",
			"enabled": 1,
			"send_welcome_email": 0,
		},
		user_roles=["Empleado"],
	)
	_log_identity_state("centro_de_datos:update_empleado:identity_reconciled", identity)
	if changed_fields or (novedad_result and novedad_result.get("action") in {"created", "updated"}):
		return {"action": "updated", "employee": doc.name, "user": identity.user}
	return {"action": "skipped", "employee": doc.name, "user": identity.user}


def create_novedad(row):
	emp_name = frappe.db.get_value("Ficha Empleado", {"cedula": row["cedula_empleado"]}, "name")
	if not emp_name:
		raise Exception(f"Empleado con cédula {row['cedula_empleado']} no encontrado.")
	result = _upsert_novedad_for_employee(emp_name, row)
	return {"action": result.get("action", "skipped"), "employee": emp_name, "novedad": result.get("name")}


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

	return {"action": "updated" if identity.user else "created", "user": user.name, "employee": identity.employee}


def _xlsx_library():
	try:
		import openpyxl  # type: ignore

		return openpyxl
	except ImportError:
		frappe.throw("La librería openpyxl no está instalada en el entorno.")


def _build_employee_report_rows():
	employees = frappe.get_all(
		"Ficha Empleado",
		fields=["name", "cedula", "nombres", "apellidos", "email", "estado", "pdv", "cargo", "tipo_jornada", "fecha_ingreso"],
	)
	pdv_rows = frappe.get_all("Punto de Venta", fields=["name", "nombre_pdv"])
	pdv_map = {row.get("name"): row.get("nombre_pdv") for row in pdv_rows}
	user_rows = frappe.get_all("User", fields=["name", "employee", "enabled"])
	user_map = {row.get("employee"): row for row in user_rows if row.get("employee")}
	novedades = frappe.get_all(
		"Novedad SST",
		fields=["empleado", "tipo_novedad", "fecha_inicio", "fecha_fin", "descripcion"],
	)
	novedades_map = {}
	for row in novedades:
		novedades_map.setdefault(row.get("empleado"), []).append(row)

	def _latest_novedad(rows):
		if not rows:
			return None
		return sorted(rows, key=lambda item: (str(item.get("fecha_inicio") or ""), str(item.get("fecha_fin") or "")), reverse=True)[0]

	report_rows = []
	for employee in employees:
		emp_novedades = novedades_map.get(employee.get("name"), [])
		latest = _latest_novedad(emp_novedades)
		user_row = user_map.get(employee.get("name"), {})
		report_rows.append(
			[
				employee.get("cedula") or "",
				employee.get("nombres") or "",
				employee.get("apellidos") or "",
				employee.get("email") or "",
				pdv_map.get(employee.get("pdv"), employee.get("pdv") or ""),
				employee.get("cargo") or "",
				employee.get("estado") or "",
				employee.get("tipo_jornada") or "",
				str(employee.get("fecha_ingreso") or ""),
				user_row.get("name") or "",
				"Sí" if user_row.get("enabled") else "No",
				len(emp_novedades),
				(latest or {}).get("tipo_novedad") or "",
				str((latest or {}).get("fecha_inicio") or ""),
				str((latest or {}).get("fecha_fin") or ""),
				(latest or {}).get("descripcion") or "",
			]
		)
	return report_rows


@frappe.whitelist()
def download_employee_master_report():
	openpyxl = _xlsx_library()
	wb = openpyxl.Workbook()
	ws = wb.active
	ws.title = "Empleados"
	ws.append(
		[
			"cedula",
			"nombres",
			"apellidos",
			"email",
			"punto_de_venta",
			"cargo",
			"estado",
			"tipo_jornada",
			"fecha_ingreso",
			"user",
			"user_enabled",
			"total_novedades",
			"ultima_novedad",
			"ultima_novedad_inicio",
			"ultima_novedad_fin",
			"ultima_novedad_descripcion",
		]
	)
	for row in _build_employee_report_rows():
		ws.append(row)

	buf = BytesIO()
	wb.save(buf)
	buf.seek(0)
	frappe.response["filename"] = f"Reporte_Empleados_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
	frappe.response["filecontent"] = buf.read()
	frappe.response["type"] = "binary"


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
