"""Disponibilidad de personal: contrato de columnas + formateo de horas + row builder.

Fuente única de verdad para las 13 columnas del reporte de disponibilidad
(bandeja + export Excel, próximas slices) y para el mapeo día-de-semana con
tolerancia a tildes.

Slice 1 (este archivo, por ahora): solo funciones puras, sin lectura a base de
datos ni endpoints whitelisted. Las slices 2/3 agregan el gate de rol, los
lectores bulk (Ficha Empleado / Candidato / Candidato Disponibilidad), el
deduplicado por cédula, la exclusión de empleados retirados y la bandeja/export.
La columna ESTADO se deja genérica a propósito en esta slice: no se asume que
las filas retiradas aparezcan ni que estén ausentes — ese filtro es responsabilidad
de los lectores de la slice 2.
"""

import base64
import logging
import unicodedata
from collections import namedtuple
from datetime import timedelta
from io import BytesIO

import frappe

from hubgh.hubgh.candidate_states import is_candidate_status
from hubgh.hubgh.display_labels import get_punto_name_map
from hubgh.hubgh.role_matrix import user_has_any_role

ColumnSpec = namedtuple("ColumnSpec", ["key", "label"])

# Fuente única de verdad: 13 columnas ordenadas del reporte de disponibilidad.
DISPONIBILIDAD_COLUMNS = (
	ColumnSpec("nombre", "NOMBRE"),
	ColumnSpec("cedula", "CÉDULA"),
	ColumnSpec("punto_de_venta", "PUNTO DE VENTA"),
	ColumnSpec("vinculacion", "VINCULACIÓN"),
	ColumnSpec("estado", "ESTADO"),
	ColumnSpec("fecha_ingreso", "FECHA DE INGRESO"),
	ColumnSpec("lunes", "LUNES"),
	ColumnSpec("martes", "MARTES"),
	ColumnSpec("miercoles", "MIÉRCOLES"),
	ColumnSpec("jueves", "JUEVES"),
	ColumnSpec("viernes", "VIERNES"),
	ColumnSpec("sabado", "SÁBADO"),
	ColumnSpec("domingo", "DOMINGO"),
)

DaySpec = namedtuple("DaySpec", ["key", "label", "dia"])

# Fuente única de verdad: 7-tupla congelada día-de-semana, en el orden de columna.
# `dia` es el valor exacto de la opción Select viva en Candidato Disponibilidad.dia.
DAY_COLUMNS = (
	DaySpec("lunes", "LUNES", "Lunes"),
	DaySpec("martes", "MARTES", "Martes"),
	DaySpec("miercoles", "MIÉRCOLES", "Miércoles"),
	DaySpec("jueves", "JUEVES", "Jueves"),
	DaySpec("viernes", "VIERNES", "Viernes"),
	DaySpec("sabado", "SÁBADO", "Sábado"),
	DaySpec("domingo", "DOMINGO", "Domingo"),
)


def _normalize_day(value):
	"""Normaliza un valor de día a minúsculas, sin espacios extremos y sin tildes
	(NFKD + drop de marcas combinantes), la misma técnica de
	`seleccion_cruce_service._normalize_match_text`. Reimplementada localmente
	(no se importa el símbolo privado de otro módulo); la duplicación queda
	cubierta por el drift-guard de `test_disponibilidad_column_contract.py`."""
	if value is None:
		return ""
	raw = str(value).strip().lower()
	raw = "".join(ch for ch in unicodedata.normalize("NFKD", raw) if not unicodedata.combining(ch))
	return raw


_DAY_LOOKUP = {_normalize_day(d.dia): d.key for d in DAY_COLUMNS}


def _format_hora(value):
	"""Formatea una hora Frappe `Time` a `HH:MM`.

	CRÍTICO: `frappe.get_all` devuelve columnas `Time` de MariaDB como
	`datetime.timedelta` (confirmado en vivo contra hubgh.local:
	`type(hora_inicio) is datetime.timedelta`), NO como `datetime.time` ni `str`.
	Un formateador ingenuo que solo maneje `hasattr(value, "hour")` (como
	`candidato.py:200-214`) deja en blanco silenciosamente cada celda de
	disponibilidad. Esta función acepta las tres formas y retorna "" para
	cualquier valor no parseable (None, timedelta negativo, texto basura).
	"""
	if value is None:
		return ""
	if isinstance(value, timedelta):
		total_seconds = int(value.total_seconds())
		if total_seconds < 0:
			return ""
		hours, remainder = divmod(total_seconds, 3600)
		minutes = remainder // 60
		return f"{hours:02d}:{minutes:02d}"
	if hasattr(value, "hour") and hasattr(value, "minute"):
		return f"{value.hour:02d}:{value.minute:02d}"
	text = str(value).strip()
	parts = text.split(":")
	if len(parts) < 2:
		return ""
	try:
		hours = int(parts[0])
		minutes = int(parts[1])
	except ValueError:
		return ""
	return f"{hours:02d}:{minutes:02d}"


def _format_ranges(rows):
	"""Formatea filas de un mismo día a `HH:MM - HH:MM`, unidas por `" / "` en
	orden ascendente de `idx`. Lista vacía -> "" (nunca el literal "No disponible")."""
	ordered = sorted(rows, key=lambda r: r.get("idx") or 0)
	ranges = []
	for row in ordered:
		inicio = _format_hora(row.get("hora_inicio"))
		fin = _format_hora(row.get("hora_fin"))
		if not inicio and not fin:
			continue
		ranges.append(f"{inicio} - {fin}")
	return " / ".join(ranges)


def build_disponibilidad_row(person, disponibilidad_rows=None):
	"""Construye una fila del reporte (dict keyed por `ColumnSpec.key`).

	`person` es un dict/`_dict` ya resuelto con los 6 campos no-día (`nombre`,
	`cedula`, `punto_de_venta`, `vinculacion`, `estado`, `fecha_ingreso`) — la
	resolución por población (Ficha Empleado vs Candidato: fallback de nombre,
	mapa de PDV, dedupe, exclusión de retirados) es responsabilidad de los
	lectores de la slice 2, no de esta función pura.

	`disponibilidad_rows` es una lista de dicts con `dia`/`hora_inicio`/
	`hora_fin`/`idx` (en cualquier orden de entrada; se ordenan aquí por `idx`
	ascendente antes de unir rangos del mismo día).

	Función pura: sin lectura a base de datos.
	"""
	disponibilidad_rows = disponibilidad_rows or []
	by_day_key = {spec.key: [] for spec in DAY_COLUMNS}
	for row in disponibilidad_rows:
		day_key = _DAY_LOOKUP.get(_normalize_day(row.get("dia")))
		if day_key is None:
			continue
		by_day_key[day_key].append(row)

	row = {
		"nombre": person.get("nombre") or "",
		"cedula": person.get("cedula") or "",
		"punto_de_venta": person.get("punto_de_venta") or "",
		"vinculacion": person.get("vinculacion") or "",
		"estado": person.get("estado") or "",
		"fecha_ingreso": person.get("fecha_ingreso") or "",
	}
	for spec in DAY_COLUMNS:
		row[spec.key] = _format_ranges(by_day_key[spec.key])
	return row


# ---------------------------------------------------------------------------
# Slice 2 — gate, lectores bulk, dedupe, bandeja/export, auditoria
# ---------------------------------------------------------------------------

# A diferencia de CRUCE_ROLES (seleccion_cruce_service.py:90-97), "System
# Manager" vive en la propia tupla, no solo en el JSON de la Page (evita el
# bug del molde: un System Manager no-Administrator quedaba sin acceso).
DISPONIBILIDAD_ROLES = (
	"GH - RRLL",
	"Gerente GH",
	"Gestión Humana",
	"HR Labor Relations",
	"Relaciones Laborales Jefe",
	"System Manager",
)

HIRED_FIELDS = ["name", "cedula", "nombres", "apellidos", "pdv", "cargo", "estado", "fecha_ingreso"]
CANDIDATE_FIELDS = [
	"name", "numero_documento", "nombres", "apellidos",
	"primer_apellido", "segundo_apellido", "pdv_destino", "fecha_tentativa_ingreso", "estado_proceso",
]


def _has_disponibilidad_read_access(user=None):
	user = user or frappe.session.user
	return user == "Administrator" or user_has_any_role(user, *DISPONIBILIDAD_ROLES)


def validate_disponibilidad_read_access():
	"""Gate de solo lectura RRLL, ANTES de cualquier lectura DB."""
	if not _has_disponibilidad_read_access():
		frappe.throw("No autorizado para consultar la disponibilidad de personal.")


def _normalize_cedula(value):
	return str(value or "").strip()


def _base_population_filters(*, date_field, pdv_field, search_field, fecha_desde=None, fecha_hasta=None, search=None, pdv=None):
	filters = {}
	if pdv:
		filters[pdv_field] = pdv
	if fecha_desde and fecha_hasta:
		filters[date_field] = ["between", [fecha_desde, fecha_hasta]]
	elif fecha_desde:
		filters[date_field] = [">=", fecha_desde]
	elif fecha_hasta:
		filters[date_field] = ["<=", fecha_hasta]
	if search:
		filters[search_field] = ["like", f"%{search}%"]
	return filters


def _base_hired_filters(fecha_desde=None, fecha_hasta=None, search=None, pdv=None):
	filters = _base_population_filters(
		date_field="fecha_ingreso", pdv_field="pdv", search_field="cedula",
		fecha_desde=fecha_desde, fecha_hasta=fecha_hasta, search=search, pdv=pdv,
	)
	filters["estado"] = ["!=", "Retirado"]  # decisión vinculante: excluye retirados
	return filters


def _base_candidate_filters(fecha_desde=None, fecha_hasta=None, search=None, pdv=None):
	return _base_population_filters(
		date_field="fecha_tentativa_ingreso", pdv_field="pdv_destino", search_field="numero_documento",
		fecha_desde=fecha_desde, fecha_hasta=fecha_hasta, search=search, pdv=pdv,
	)


def _read_hired_rows(fecha_desde=None, fecha_hasta=None, search=None, pdv=None):
	filters = _base_hired_filters(fecha_desde=fecha_desde, fecha_hasta=fecha_hasta, search=search, pdv=pdv)
	return frappe.get_all("Ficha Empleado", filters=filters, fields=HIRED_FIELDS)


def _read_candidate_rows(fecha_desde=None, fecha_hasta=None, search=None, pdv=None):
	filters = _base_candidate_filters(fecha_desde=fecha_desde, fecha_hasta=fecha_hasta, search=search, pdv=pdv)
	rows = frappe.get_all("Candidato", filters=filters, fields=CANDIDATE_FIELDS)
	return [r for r in rows if not is_candidate_status(r.get("estado_proceso"), "Rechazado", "Contratado")]


def _read_disponibilidad_rows(candidato_names):
	"""Lee `Candidato Disponibilidad` DIRECTO (nunca `frappe.get_doc("Candidato")`):
	`Candidato.disponibilidad` es permlevel 1 (candidato.json:421-427) y los roles
	RRLL puros no tienen NINGUNA fila de permiso sobre Candidato (candidato.json:
	438-521); `get_doc` blanquearía la tabla hija para ellos (ADR-3)."""
	if not candidato_names:
		return []
	return frappe.get_all(
		"Candidato Disponibilidad",
		filters={"parent": ["in", candidato_names], "parenttype": "Candidato", "parentfield": "disponibilidad"},
		fields=["parent", "dia", "hora_inicio", "hora_fin", "idx"],
		order_by="parent asc, idx asc",
	)


def _join_name(nombres, apellidos):
	return " ".join(p for p in [nombres or "", apellidos or ""] if p).strip()


def _resolve_hired_person(row):
	return {
		"nombre": _join_name(row.get("nombres"), row.get("apellidos")),
		"cedula": row.get("cedula") or row.get("name") or "",
		"_pdv_code": row.get("pdv") or "",
		"vinculacion": "Contratado",
		"estado": row.get("estado") or "",
		"fecha_ingreso": row.get("fecha_ingreso") or "",
	}


def _resolve_candidate_person(row):
	apellidos = row.get("apellidos") or _join_name(row.get("primer_apellido"), row.get("segundo_apellido"))
	return {
		"nombre": _join_name(row.get("nombres"), apellidos),
		"cedula": row.get("numero_documento") or row.get("name") or "",
		"_pdv_code": row.get("pdv_destino") or "",
		"vinculacion": "En proceso",
		"estado": row.get("estado_proceso") or "",
		"fecha_ingreso": row.get("fecha_tentativa_ingreso") or "",
	}


def _dedupe_by_cedula(hired_cedulas, candidate_entries):
	"""Descarta candidatos cuya cédula ya está en `hired_cedulas` (ADR-6: gana el contratado)."""
	return [(p, name) for p, name in candidate_entries if _normalize_cedula(p.get("cedula")) not in hired_cedulas]


def _build_row_set(fecha_desde=None, fecha_hasta=None, search=None, pdv=None, poblacion=None):
	"""`[(person, disponibilidad_rows), ...]` deduplicado; <=5 `frappe.get_all` (<=4 si `poblacion` excluye una) — AC-12."""
	include_hired = poblacion != "en_proceso"
	include_en_proceso = poblacion != "contratados"

	hired_raw = _read_hired_rows(fecha_desde, fecha_hasta, search, pdv) if include_hired else []
	candidate_raw = _read_candidate_rows(fecha_desde, fecha_hasta, search, pdv) if include_en_proceso else []

	hired_entries = [(_resolve_hired_person(row), None) for row in hired_raw]
	hired_cedulas = {_normalize_cedula(p["cedula"]) for p, _ in hired_entries if p["cedula"]}

	candidato_name_by_cedula = {}
	if hired_cedulas:  # Q3: cédula -> nombre de Candidato, resistente a rename
		lookup_rows = frappe.get_all(
			"Candidato", filters={"numero_documento": ["in", sorted(hired_cedulas)]}, fields=["name", "numero_documento"]
		)
		candidato_name_by_cedula = {_normalize_cedula(r.get("numero_documento")): r.get("name") for r in lookup_rows}
	hired_entries = [(p, candidato_name_by_cedula.get(_normalize_cedula(p["cedula"]))) for p, _ in hired_entries]

	candidate_entries = [(_resolve_candidate_person(row), row.get("name")) for row in candidate_raw]
	candidate_entries = _dedupe_by_cedula(hired_cedulas, candidate_entries)
	all_entries = hired_entries + candidate_entries

	pdv_name_map = get_punto_name_map([p.get("_pdv_code") for p, _ in all_entries])
	for person, _ in all_entries:
		code = person.pop("_pdv_code", "")
		person["punto_de_venta"] = pdv_name_map.get(code, code) if code else ""

	availability_names = sorted({name for _, name in all_entries if name})
	availability_rows = _read_disponibilidad_rows(availability_names) if availability_names else []
	availability_by_parent = {}
	for row in availability_rows:
		availability_by_parent.setdefault(row.get("parent"), []).append(row)

	return [(person, availability_by_parent.get(name, [])) for person, name in all_entries]


# ADR-7: compact tray summary (DÍAS column). "X" for Miércoles avoids the
# Martes/Miércoles "M" collision (the usual Spanish L M X J V S D calendar
# convention).
_DAY_INITIALS = {
	"lunes": "L",
	"martes": "M",
	"miercoles": "X",
	"jueves": "J",
	"viernes": "V",
	"sabado": "S",
	"domingo": "D",
}


def _build_dias_resumen(row):
	"""Compact tray summary derived STRICTLY from the same `build_disponibilidad_row()`
	output dict `row` — never from a second traversal of the raw child rows
	(ADR-7 anti-drift rule, AC-14). Empty string when there is no availability
	(never the literal "No disponible", same rule as the day columns themselves)."""
	present = [spec.key for spec in DAY_COLUMNS if row.get(spec.key)]
	if not present:
		return ""
	initials = " ".join(_DAY_INITIALS[key] for key in present)
	return f"{initials} · {len(present)}/7"


AUDIT_LOGGER_NAME = "hubgh.disponibilidad"


def _get_audit_logger():
	"""Forzado a nivel INFO: sin `setLevel` el `.info(...)` se descarta en silencio."""
	logger = frappe.logger(AUDIT_LOGGER_NAME, allow_site=True)
	logger.setLevel(logging.INFO)
	return logger


@frappe.whitelist()
def list_disponibilidad(fecha_desde=None, fecha_hasta=None, search=None, pdv=None, poblacion=None):
	"""Bandeja RRLL: contratados (excluye Retirado) + en proceso (excluye
	Rechazado/Contratado), deduplicados por cédula."""
	validate_disponibilidad_read_access()
	rows = _build_row_set(fecha_desde=fecha_desde, fecha_hasta=fecha_hasta, search=search, pdv=pdv, poblacion=poblacion)
	result = []
	for person, availability_rows in rows:
		built = build_disponibilidad_row(person, availability_rows)
		built["dias_resumen"] = _build_dias_resumen(built)
		result.append(built)
	return result


@frappe.whitelist()
def export_disponibilidad_xlsx(filters=None):
	"""Excel de 13 columnas fijas. Gate antes de leer DB. Audita user/timestamp/
	count/filters en cada llamada, incluso `count == 0` (workbook solo-encabezados).
	Returns: {"filename", "content_b64", "count"}."""
	validate_disponibilidad_read_access()

	import openpyxl
	from openpyxl.styles import Alignment, Font, PatternFill

	filters = frappe.parse_json(filters) if filters else {}
	rows = _build_row_set(
		fecha_desde=filters.get("fecha_desde"), fecha_hasta=filters.get("fecha_hasta"),
		search=filters.get("search"), pdv=filters.get("pdv"), poblacion=filters.get("poblacion"),
	)

	wb = openpyxl.Workbook()
	ws = wb.active
	ws.title = "Disponibilidad"
	headers = [column.label for column in DISPONIBILIDAD_COLUMNS]
	ws.append(headers)

	header_fill = PatternFill(start_color="1D4ED8", end_color="1D4ED8", fill_type="solid")
	header_font = Font(bold=True, color="FFFFFF")
	for col_idx in range(1, len(headers) + 1):
		cell = ws.cell(row=1, column=col_idx)
		cell.fill = header_fill
		cell.font = header_font
		cell.alignment = Alignment(horizontal="center", vertical="center")

	for person, availability_rows in rows:
		built = build_disponibilidad_row(person, availability_rows)
		ws.append([built.get(column.key, "") for column in DISPONIBILIDAD_COLUMNS])

	for idx in range(1, len(headers) + 1):
		ws.column_dimensions[ws.cell(row=1, column=idx).column_letter].width = 16

	output = BytesIO()
	wb.save(output)
	count = len(rows)

	_get_audit_logger().info({
		"user": frappe.session.user,
		"timestamp": frappe.utils.now(),
		"count": count,
		"filters": filters,
	})

	return {
		"filename": f"disponibilidad_personal_{frappe.utils.nowdate()}.xlsx",
		"content_b64": base64.b64encode(output.getvalue()).decode("ascii"),
		"count": count,
	}
