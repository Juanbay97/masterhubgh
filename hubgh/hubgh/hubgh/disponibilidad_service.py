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

import unicodedata
from collections import namedtuple
from datetime import timedelta


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
